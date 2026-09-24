"""LensConfig — internal lens configuration stored inside an IG file.

A LensConfig is a lightweight named view that records *which nodes are
displayed at what LOD*, and which intentlinks are explicitly included.
It does NOT carry node body copies. It is the peer (not a replacement)
of the agent-I/O ``Lens`` class in ``models/lens.py``.

Design: ``foundation_and_formalism/LENS_REDESIGN_SPEC.md`` §4.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from intentgraph.models.graph import IntentGraph

from intentgraph.errors import ClosureViolation

LOD_LITERAL = Literal["skeleton", "lean", "full"]

# Default LOD assigned to ancestor nodes inserted automatically during add_node
_DEFAULT_ANCESTOR_LOD: LOD_LITERAL = "skeleton"


class Position(BaseModel):
    """Cytoscape node center position, parent-relative.

    Coordinate frame: parent-relative (x, y) offset from parent top-left.
    Stores Cytoscape node CENTER (MVP choice). ROOT is implicit (0, 0) and
    never stored. None on LensNodeEntry means unpinned.

    PIG: LENSSCHEMA.NODESHAPE, PERSISTENCE.POSITIONS
    """

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class LensNodeEntry(BaseModel):
    """Per-node entry in LensConfig.nodes.

    Carries lod and optional position together so the lens is the sole store
    for all user-decidable visual state.

    PIG: LENSSCHEMA.NODESHAPE
    """

    lod: LOD_LITERAL
    position: Optional[Position] = None


class LensConfig(BaseModel):
    """Internal lens configuration stored inside an IG file.

    Carries pointers (UIDs + LOD assignments) only — no node body copies.
    Closure invariants: every node's ancestors are in ``nodes``; every
    link's endpoints are in ``nodes``. Enforced by API methods
    (``add_node``, ``remove_node``, ``add_link``, ``remove_link``,
    ``set_lod``); verified at load-time by ``validate_lenses``.

    Spec: §4 + §6.
    """

    # --- Identity ---
    # Redundant with the dict key; kept for self-documentation and
    # standalone round-trip serialization.
    name: str
    description: str | None = None

    # --- Focus hints ---
    # List of UIDs the viewer should treat as primary focus.
    # Empty list = no specific focus. Does NOT gate rendering.
    target_uids: list[str] = Field(default_factory=list)

    # --- Core display config ---
    # Maps uid → LensNodeEntry. Closure requires ancestors of every displayed
    # node to also be present.
    nodes: dict[str, LensNodeEntry] = Field(default_factory=dict)

    # --- Explicit intentlink inclusion list (UIDs) ---
    # Closure requires both endpoints to be in ``nodes``.
    intentlinks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def name_must_be_nonempty(self) -> "LensConfig":
        if not self.name or not self.name.strip():
            raise ValueError("LensConfig.name must be a non-empty string")
        return self

    # ------------------------------------------------------------------ #
    #  Closure-by-construction API methods (Spec §6)                     #
    # ------------------------------------------------------------------ #

    def add_node(
        self,
        uid: str,
        lod: LOD_LITERAL,
        graph: "IntentGraph",
    ) -> None:
        """Add a node to the lens, auto-inserting all ancestors at skeleton LOD.

        Spec §6 C1 — Ancestor completeness.

        Preconditions:
        - ``uid`` must exist in ``graph``.
        - ``lod`` must be a valid LOD string.

        Postcondition: ``self.nodes[uid] = lod`` and every ancestor of
        ``uid`` is present in ``self.nodes`` (defaulting to ``skeleton``).
        """
        if uid not in graph.nodes:
            raise ValueError(f"Node '{uid}' does not exist in the graph")
        # Insert ancestors not yet present
        for anc_uid in graph.anc(uid):
            if anc_uid not in self.nodes:
                self.nodes[anc_uid] = LensNodeEntry(lod=_DEFAULT_ANCESTOR_LOD)
        # Set the target node's LOD (preserve existing position if present)
        existing = self.nodes.get(uid)
        self.nodes[uid] = LensNodeEntry(
            lod=lod,
            position=existing.position if existing is not None else None,
        )

    def remove_node(
        self,
        uid: str,
        graph: "IntentGraph",
    ) -> None:
        """Remove a node and all its descendants from the lens.

        Spec §6 C2 (descendant purge) + C4 (link purge).

        Preconditions:
        - ``uid`` must be in ``self.nodes``.

        Postcondition: ``uid`` and all its descendants are absent from
        ``self.nodes``; every intentlink whose endpoint touches any
        removed uid is also removed from ``self.intentlinks``.
        """
        if uid not in self.nodes:
            raise ValueError(f"Node '{uid}' is not in the lens")

        # Compute the full removal set: target + all descendants
        removal_set: set[str] = {uid} | graph.desc(uid)

        # Remove nodes
        for r in removal_set:
            self.nodes.pop(r, None)

        # Remove any intentlinks that touch any removed node (C4)
        # For intra links the UID pattern is "{src}_{dst}"; we look them up
        # in the graph to find actual endpoints.
        surviving_links: list[str] = []
        for link_uid in self.intentlinks:
            # Try intra link lookup
            link = graph.links.get(link_uid) or graph.inter_links.get(link_uid)
            if link is None:
                # Stale reference — drop it
                continue
            src = link.src
            dst = link.dst
            # For inter links the src/dst are qualified (graph_id:node_uid);
            # extract the local part for the removal check.
            local_src = src.split(":", 1)[1] if ":" in src else src
            local_dst = dst.split(":", 1)[1] if ":" in dst else dst
            if local_src in removal_set or local_dst in removal_set:
                continue  # drop this link
            surviving_links.append(link_uid)
        self.intentlinks = surviving_links

    def set_lod(self, uid: str, lod: LOD_LITERAL) -> None:
        """Update the LOD of a displayed node.

        Spec §6 C6 — structural-invariant-preserving.

        No ancestor or descendant changes. No link changes.

        Precondition: ``uid`` must be in ``self.nodes``.
        """
        if uid not in self.nodes:
            raise ValueError(f"Node '{uid}' is not in the lens")
        # Preserve existing position (Spec §5 test: set_lod must not alter position)
        existing = self.nodes[uid]
        self.nodes[uid] = LensNodeEntry(lod=lod, position=existing.position)

    def add_link(self, link_uid: str, graph: "IntentGraph") -> None:
        """Add an intentlink to the lens.

        Spec §6 C3 — Link endpoint check.

        Preconditions:
        - ``link_uid`` must exist in ``graph.links`` or ``graph.inter_links``.
        - Both endpoints must be in ``self.nodes``.

        Raises ``ClosureViolation`` if either endpoint is not in the lens.

        Postcondition: ``link_uid`` in ``self.intentlinks``.
        """
        link = graph.links.get(link_uid) or graph.inter_links.get(link_uid)
        if link is None:
            raise ValueError(f"Link '{link_uid}' does not exist in the graph")

        src = link.src
        dst = link.dst
        local_src = src.split(":", 1)[1] if ":" in src else src
        local_dst = dst.split(":", 1)[1] if ":" in dst else dst

        if local_src not in self.nodes:
            raise ClosureViolation(
                f"Cannot add link: endpoint '{local_src}' not in lens. "
                "Add the node first."
            )
        if local_dst not in self.nodes:
            raise ClosureViolation(
                f"Cannot add link: endpoint '{local_dst}' not in lens. "
                "Add the node first."
            )

        if link_uid not in self.intentlinks:
            self.intentlinks.append(link_uid)

    def remove_link(self, link_uid: str) -> None:
        """Remove an intentlink from the lens.

        Spec §6 C5 — unconstrained. No structural side-effects.

        Postcondition: ``link_uid`` not in ``self.intentlinks``.
        """
        self.intentlinks = [uid for uid in self.intentlinks if uid != link_uid]
