"""IntentGraph (IG) — the enforcing container.

Owns all intentnodes, treearcs (as adjacency), and intentlinks.
Every structural mutation enforces invariants T1 (tree property) and T3
(ilink well-formedness) before committing the change.

Implements the query operators from VOCABULARY_AND_FORMALISM.md section 3.2
(parent, children, anc, desc, is_above, is_leaf, siblings).
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any, Iterator

from intentgraph.errors import (
    DuplicateLinkError,
    DuplicateNodeError,
    IntentGraphError,
    LinkInvariantViolation,
    LinkNotFoundError,
    NodeNotFoundError,
    TreeInvariantViolation,
)
from intentgraph.models.link import IntentLink, InterIntentLink
from intentgraph.models.node import IntentNode, validate_uid_format

# Forward reference — imported inside methods to avoid circular imports.
# LensConfig lives in models/lens_config.py which imports IntentGraph from
# this module; the TYPE_CHECKING guard breaks the cycle.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intentgraph.models.lens_config import LensConfig

logger = logging.getLogger(__name__)


class IntentGraph:
    """The complete IntentGraph artifact — the single source of truth.

    ``IG = (inodes, tarcs, ilinks)``

    Treearcs are stored as adjacency on nodes (parent_uid / children_uids)
    for O(1) navigation.  On serialization they are emitted as an explicit
    list of ``{parent, child}`` pairs per the formalism schema.

    All structural mutations go through methods on this class, which enforce
    T1 (tree property) and T3 (ilink well-formedness).
    """

    def __init__(self, meta: dict[str, Any] | None = None) -> None:
        self._nodes: dict[str, IntentNode] = {}
        self._links: dict[str, IntentLink] = {}
        self._inter_links: dict[str, InterIntentLink] = {}
        self.meta: dict[str, Any] = meta or {}
        # Internal lens configurations (Spec §5.1, §11).
        # Each entry maps lens name → LensConfig (UIDs + LOD assignments).
        # Populated by ``add_lens``; serialized by ``graph_to_dict``.
        self.lenses: dict[str, "LensConfig"] = {}

    # ------------------------------------------------------------------ #
    #  Node access (read-only)                                            #
    # ------------------------------------------------------------------ #

    @property
    def nodes(self) -> dict[str, IntentNode]:
        """All nodes keyed by uid (read-only view)."""
        return self._nodes

    @property
    def links(self) -> dict[str, IntentLink]:
        """All intentlinks keyed by uid (read-only view)."""
        return self._links

    def node_count(self) -> int:
        return len(self._nodes)

    def link_count(self) -> int:
        return len(self._links)

    @property
    def inter_links(self) -> dict[str, InterIntentLink]:
        """All inter intentlinks keyed by uid (read-only view)."""
        return self._inter_links

    def inter_link_count(self) -> int:
        return len(self._inter_links)

    # ------------------------------------------------------------------ #
    #  Query operators  (formalism section 3.2)                           #
    # ------------------------------------------------------------------ #

    def get_node(self, uid: str) -> IntentNode:
        """Return node by uid or raise ``NodeNotFoundError``."""
        try:
            return self._nodes[uid]
        except KeyError:
            raise NodeNotFoundError(f"Node '{uid}' does not exist")

    def get_node_or_none(self, uid: str) -> IntentNode | None:
        return self._nodes.get(uid)

    def parent(self, uid: str) -> IntentNode | None:
        """``parent(n)`` — the unique parent of *n*, or ``None`` if root."""
        node = self.get_node(uid)
        if node.parent_uid is None:
            return None
        return self._nodes.get(node.parent_uid)

    def children(self, uid: str) -> list[IntentNode]:
        """``children(n)`` — all direct children of *n*."""
        node = self.get_node(uid)
        return [self._nodes[c] for c in node.children_uids if c in self._nodes]

    def anc(self, uid: str) -> set[str]:
        """``anc(n)`` — all ancestor uids of *n* (transitive parent closure)."""
        ancestors: set[str] = set()
        current = self.get_node(uid)
        while current.parent_uid is not None:
            ancestors.add(current.parent_uid)
            current = self._nodes[current.parent_uid]
        return ancestors

    def desc(self, uid: str) -> set[str]:
        """``desc(n)`` — all descendant uids of *n* (transitive children closure)."""
        descendants: set[str] = set()
        stack = list(self.get_node(uid).children_uids)
        while stack:
            cid = stack.pop()
            if cid in descendants:
                continue
            descendants.add(cid)
            child = self._nodes.get(cid)
            if child:
                stack.extend(child.children_uids)
        return descendants

    def is_above(self, n: str, m: str) -> bool:
        """``is_above(n, m)`` — True iff *n* is an ancestor of *m*, or ``n == m``."""
        if n == m:
            return True
        return n in self.anc(m)

    def is_leaf(self, uid: str) -> bool:
        return self.get_node(uid).is_leaf

    def siblings(self, uid: str) -> list[IntentNode]:
        """``siblings(n)`` — children of n's parent, excluding n itself."""
        node = self.get_node(uid)
        if node.parent_uid is None:
            return []
        return [
            self._nodes[c]
            for c in self._nodes[node.parent_uid].children_uids
            if c != uid and c in self._nodes
        ]

    def roots(self) -> list[IntentNode]:
        """All root nodes (nodes with no parent)."""
        return [n for n in self._nodes.values() if n.parent_uid is None]

    def iter_nodes(self) -> Iterator[IntentNode]:
        return iter(self._nodes.values())

    def iter_nodes_bfs(self) -> Iterator[IntentNode]:
        """Yield nodes in breadth-first order: root(s) first, then each level.

        Roots are sorted by uid; within each level children are in
        parent's children_uids order. Used for stable serialization (e.g. JSON/YAML).
        """
        roots = sorted(self.roots(), key=lambda r: r.uid)
        seen: set[str] = set()
        queue: deque[IntentNode] = deque(roots)
        while queue:
            node = queue.popleft()
            if node.uid in seen:
                continue
            seen.add(node.uid)
            yield node
            for child_uid in node.children_uids:
                if child_uid not in seen and child_uid in self._nodes:
                    queue.append(self._nodes[child_uid])

    def iter_links(self) -> Iterator[IntentLink]:
        return iter(self._links.values())

    def iter_inter_links(self) -> Iterator[InterIntentLink]:
        return iter(self._inter_links.values())

    # ------------------------------------------------------------------ #
    #  Node mutation                                                      #
    # ------------------------------------------------------------------ #

    def add_node(
        self,
        uid: str,
        name: str,
        intent: str,
        *,
        epistemic_state: str | None = None,
        constraints: list[str] | None = None,
        examples: list[str] | None = None,
        design_notes: str | None = None,
        effort: str | None = None,
        impl_pointers: list[str] | None = None,
        history: list[dict] | None = None,
        data_registry: dict | None = None,
    ) -> IntentNode:
        """Create an **unattached** node (no treearc yet).

        Use ``attach()`` to place it in the tree after creation.
        """
        if uid in self._nodes:
            raise DuplicateNodeError(f"Node '{uid}' already exists")

        from intentgraph.models.node import HistoryEntry

        node = IntentNode(
            uid=uid,
            name=name,
            intent=intent,
            epistemic_state=epistemic_state,
            constraints=constraints or [],
            examples=examples or [],
            design_notes=design_notes,
            effort=effort,
            impl_pointers=impl_pointers or [],
            history=[HistoryEntry(**h) for h in (history or [])],
            data_registry=data_registry,
        )
        self._nodes[uid] = node
        return node

    def attach(self, parent_uid: str, child_uid: str, skip_uid_validation: bool = False) -> None:
        """Create a treearc ``parent → child``.  Enforces T1.

        Preconditions checked:
        - Both nodes exist.
        - Child has no existing parent (at most one parent).
        - Attaching would not create a cycle (child is not an ancestor of parent).
        - Child UID follows format conventions for its level (unless skip_uid_validation=True).

        Args:
            parent_uid: UID of the parent node.
            child_uid: UID of the child node.
            skip_uid_validation: If True, skip UID format validation. Used for reparenting
                existing nodes where the UID is stable and should not be changed.
        """
        parent = self.get_node(parent_uid)
        child = self.get_node(child_uid)

        # Validate UID format conventions (pass grandparent so validator knows parent's level)
        # Skip validation if requested (e.g., for reparenting existing nodes)
        if not skip_uid_validation:
            grandparent_uid = parent.parent_uid
            validate_uid_format(child_uid, parent_uid, grandparent_uid)

        # T1: at most one parent
        if child.parent_uid is not None:
            raise TreeInvariantViolation(
                f"Node '{child_uid}' already has parent '{child.parent_uid}'. "
                f"Detach first before re-attaching."
            )

        # T1: no cycles — child must not be an ancestor of parent
        if self.is_above(child_uid, parent_uid):
            raise TreeInvariantViolation(
                f"Attaching '{child_uid}' under '{parent_uid}' would create a cycle "
                f"('{child_uid}' is an ancestor of '{parent_uid}')."
            )

        # Commit
        child.parent_uid = parent_uid
        if child_uid not in parent.children_uids:
            parent.children_uids.append(child_uid)

        logger.debug(
            "T4 check recommended: review coherence of '%s' with new child '%s'",
            parent_uid,
            child_uid,
        )

    def detach(self, parent_uid: str, child_uid: str) -> None:
        """Remove the treearc ``parent → child``.

        The child becomes unattached (orphan).  Caller is responsible for
        re-attaching or removing it.
        """
        parent = self.get_node(parent_uid)
        child = self.get_node(child_uid)

        if child.parent_uid != parent_uid:
            raise TreeInvariantViolation(
                f"Node '{child_uid}' is not a child of '{parent_uid}'."
            )

        child.parent_uid = None
        parent.children_uids = [c for c in parent.children_uids if c != child_uid]

    def remove_node(self, uid: str, *, cascade: bool = False) -> None:
        """Remove a node.  Enforces T3 (cleans up referencing ilinks).

        If ``cascade=True``, also removes all descendants (leaves first).
        If ``cascade=False`` and the node has children, raises.
        """
        node = self.get_node(uid)

        if node.children_uids and not cascade:
            raise TreeInvariantViolation(
                f"Node '{uid}' has children {node.children_uids}. "
                f"Use cascade=True to delete the entire subtree."
            )

        # Collect uids to delete (subtree, leaves-first for cascade)
        uids_to_delete: list[str]
        if cascade:
            uids_to_delete = self._subtree_leaves_first(uid)
        else:
            uids_to_delete = [uid]

        for del_uid in uids_to_delete:
            self._remove_single_node(del_uid)

    def update_node(self, uid: str, **fields: Any) -> IntentNode:
        """Update content fields on an existing node.

        Structural fields (uid, parent_uid, children_uids) cannot be changed
        through this method — use ``attach`` / ``detach`` / ``remove_node``.
        """
        node = self.get_node(uid)
        forbidden = {"uid", "parent_uid", "children_uids"}
        bad = forbidden & set(fields)
        if bad:
            raise IntentGraphError(
                f"Cannot update structural fields via update_node: {bad}. "
                f"Use attach/detach/remove_node instead."
            )

        from intentgraph.models.node import HistoryEntry, IntentNode

        unknown = set(fields) - set(IntentNode.model_fields)
        if unknown:
            raise IntentGraphError(
                f"Unknown node field(s) in update_node: {sorted(unknown)}. "
                f"Valid content fields: "
                f"{sorted(set(IntentNode.model_fields) - forbidden)}"
            )

        for field, value in fields.items():
            if field == "history" and isinstance(value, list):
                value = [
                    HistoryEntry(**h) if isinstance(h, dict) else h for h in value
                ]
            setattr(node, field, value)

        return node

    def unset_node_fields(self, uid: str, fields: list[str]) -> IntentNode:
        """Clear optional content fields back to their absent value.

        List fields reset to [], scalar fields to None. Only fields listed in
        IntentNode.UNSETTABLE_FIELDS may be cleared.
        """
        from intentgraph.models.node import IntentNode

        node = self.get_node(uid)
        bad = [f for f in fields if f not in IntentNode.UNSETTABLE_FIELDS]
        if bad:
            raise IntentGraphError(
                f"Field(s) cannot be unset: {bad}. "
                f"Unsettable fields: {sorted(IntentNode.UNSETTABLE_FIELDS)}"
            )
        for field in fields:
            setattr(node, field, IntentNode.empty_value(field))
        return node

    # ---- Internal node helpers ----

    def _subtree_leaves_first(self, uid: str) -> list[str]:
        """Return the subtree rooted at uid, ordered leaves-first (post-order)."""
        result: list[str] = []

        def _walk(nid: str) -> None:
            node = self._nodes.get(nid)
            if node:
                for child_uid in list(node.children_uids):
                    _walk(child_uid)
            result.append(nid)

        _walk(uid)
        return result

    def _remove_single_node(self, uid: str) -> None:
        """Remove one node and clean up references."""
        node = self._nodes[uid]

        # Detach from parent
        if node.parent_uid and node.parent_uid in self._nodes:
            parent = self._nodes[node.parent_uid]
            parent.children_uids = [c for c in parent.children_uids if c != uid]

        # T3: remove all ilinks referencing this node
        to_remove = [
            lid for lid, link in self._links.items()
            if link.src == uid or link.dst == uid
        ]
        for lid in to_remove:
            del self._links[lid]

        del self._nodes[uid]

    # ------------------------------------------------------------------ #
    #  Intentlink mutation                                                #
    # ------------------------------------------------------------------ #

    def add_link(
        self,
        src: str,
        dst: str,
        intent: str,
        *,
        uid: str | None = None,
        tag: str | None = None,
        shape: dict[str, Any] | None = None,
        parent: str | None = None,
    ) -> IntentLink:
        """Create an intentlink.  Enforces T3.

        If ``uid`` is not provided, it is derived from ``{src}_{dst}`` (or
        ``{src}_{dst}#{tag}`` if *tag* is given).

        T3 checks:
        - Both endpoints must exist.
        - If *parent* link specified, descendant-rule must hold.
        """
        # T3: endpoints exist
        if src not in self._nodes:
            raise LinkInvariantViolation(f"Source node '{src}' does not exist")
        if dst not in self._nodes:
            raise LinkInvariantViolation(f"Destination node '{dst}' does not exist")

        # Derive uid
        link_uid = uid or IntentLink.derive_uid(src, dst, tag)
        if link_uid in self._links:
            raise DuplicateLinkError(f"IntentLink '{link_uid}' already exists")

        # T3: refinement well-formedness (descendant rule)
        if parent is not None:
            self._check_link_descendant_rule(parent, src, dst)

        link = IntentLink(
            uid=link_uid,
            src=src,
            dst=dst,
            intent=intent,
            shape=shape,
            parent=parent,
        )
        self._links[link_uid] = link
        return link

    def update_link(self, uid: str, **fields: Any) -> IntentLink:
        """Update mutable fields on an existing intentlink.

        Structural fields (uid, src, dst) cannot be changed — delete and
        recreate the link instead.  Mutable fields: ``intent``, ``shape``,
        ``parent``.
        """
        link = self.get_link(uid)
        forbidden = {"uid", "src", "dst"}
        bad = forbidden & set(fields)
        if bad:
            raise IntentGraphError(
                f"Cannot update structural fields via update_link: {bad}. "
                f"Delete and recreate the link instead."
            )
        unknown = set(fields) - set(IntentLink.model_fields)
        if unknown:
            raise IntentGraphError(
                f"Unknown link field(s) in update_link: {sorted(unknown)}. "
                f"Mutable fields: intent, shape, parent."
            )
        for field, value in fields.items():
            setattr(link, field, value)
        return link

    def remove_link(self, uid: str) -> None:
        """Remove an intentlink by uid."""
        if uid not in self._links:
            raise LinkNotFoundError(f"IntentLink '{uid}' does not exist")

        # Orphan child links (clear their parent reference)
        for link in self._links.values():
            if link.parent == uid:
                link.parent = None

        del self._links[uid]

    def get_link(self, uid: str) -> IntentLink:
        try:
            return self._links[uid]
        except KeyError:
            raise LinkNotFoundError(f"IntentLink '{uid}' does not exist")

    # ------------------------------------------------------------------ #
    #  Inter intentlinks (no T3 in-graph; validation via manifest)        #
    # ------------------------------------------------------------------ #

    def add_inter_link(
        self,
        src: str,
        dst: str,
        intent: str,
        *,
        uid: str | None = None,
        shape: dict[str, Any] | None = None,
    ) -> InterIntentLink:
        """Add an inter intentlink (endpoints are graph_id:node_uid).

        No endpoint existence check is performed here; use validation with
        intent_resources to verify endpoints in their respective graphs.
        """
        link_uid = uid or InterIntentLink.derive_uid(src, dst)
        if link_uid in self._inter_links:
            raise DuplicateLinkError(f"InterIntentLink '{link_uid}' already exists")
        link = InterIntentLink(src=src, dst=dst, intent=intent, uid=link_uid, shape=shape)
        # Store with derived or explicit uid (for dict key we use link_uid)
        self._inter_links[link_uid] = link
        return link

    def remove_inter_link(self, uid: str) -> None:
        """Remove an inter intentlink by uid."""
        if uid not in self._inter_links:
            raise LinkNotFoundError(f"InterIntentLink '{uid}' does not exist")
        del self._inter_links[uid]

    def update_inter_link(self, uid: str, **fields: Any) -> InterIntentLink:
        """Update mutable fields on an existing inter intentlink (intent, shape)."""
        link = self.get_inter_link(uid)
        forbidden = {"uid", "src", "dst"}
        bad = forbidden & set(fields)
        if bad:
            raise IntentGraphError(
                f"Cannot update structural fields via update_inter_link: {bad}. "
                f"Delete and recreate the link instead."
            )
        unknown = set(fields) - set(InterIntentLink.model_fields)
        if unknown:
            raise IntentGraphError(
                f"Unknown link field(s) in update_inter_link: {sorted(unknown)}. "
                f"Mutable fields: intent, shape."
            )
        for field, value in fields.items():
            setattr(link, field, value)
        return link

    def get_inter_link(self, uid: str) -> InterIntentLink:
        try:
            return self._inter_links[uid]
        except KeyError:
            raise LinkNotFoundError(f"InterIntentLink '{uid}' does not exist")

    def _check_link_descendant_rule(
        self, parent_link_uid: str, child_src: str, child_dst: str
    ) -> None:
        """T3 refinement: child link endpoints must be descendants of parent link endpoints."""
        if parent_link_uid not in self._links:
            raise LinkInvariantViolation(
                f"Parent link '{parent_link_uid}' does not exist"
            )
        parent_link = self._links[parent_link_uid]
        if not self.is_above(parent_link.src, child_src):
            raise LinkInvariantViolation(
                f"Child link src '{child_src}' is not a descendant of "
                f"parent link src '{parent_link.src}'"
            )
        if not self.is_above(parent_link.dst, child_dst):
            raise LinkInvariantViolation(
                f"Child link dst '{child_dst}' is not a descendant of "
                f"parent link dst '{parent_link.dst}'"
            )

    # ------------------------------------------------------------------ #
    #  Convenience builders                                               #
    # ------------------------------------------------------------------ #

    def add_node_under(
        self,
        uid: str,
        name: str,
        intent: str,
        parent_uid: str,
        **kwargs: Any,
    ) -> IntentNode:
        """Shorthand: add a node and immediately attach it under *parent_uid*."""
        node = self.add_node(uid, name, intent, **kwargs)
        self.attach(parent_uid, uid)
        return node

    # ------------------------------------------------------------------ #
    #  Internal lens (LensConfig) management  (Spec §5.1, §11)           #
    # ------------------------------------------------------------------ #

    def add_lens(self, lens: "LensConfig") -> None:
        """Register an internal lens.

        Spec: ``IntentGraph.add_lens`` — stores ``lens`` under ``lens.name``
        in ``self.lenses``. Replaces any existing lens with the same name.
        """
        self.lenses[lens.name] = lens

    def remove_lens(self, name: str) -> None:
        """Remove an internal lens by name.

        Also clears ``meta.default_lens`` if it pointed to *name*.

        Raises ``KeyError`` if the lens does not exist.
        """
        if name not in self.lenses:
            raise KeyError(f"Lens '{name}' does not exist in this graph")
        del self.lenses[name]
        if self.meta.get("default_lens") == name:
            del self.meta["default_lens"]

    def get_lens(self, name: str) -> "LensConfig":
        """Return a lens by name.

        Raises ``KeyError`` if not found.
        """
        try:
            return self.lenses[name]
        except KeyError:
            raise KeyError(f"Lens '{name}' does not exist in this graph")
