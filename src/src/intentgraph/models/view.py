"""View — a named set of visible nodes over an IntentGraph.

A View is the minimal carrier for agent-text serialization (§2 of
SERIALIZATION_FORMAT.md) and context assembly: a name, a set of node uids,
and an optional lean-detail subset.

A View enforces **no antichain invariant** — the Lens owns view semantics.
The only validation is that every uid exists in the graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator

from intentgraph.errors import NodeNotFoundError

if TYPE_CHECKING:
    from intentgraph.models.graph import IntentGraph


@dataclass(frozen=True, eq=False)
class View:
    """A named set of visible intentnodes — a working view of the graph.

    Parameters
    ----------
    graph : IntentGraph
        The graph this view selects from.
    name : str
        Human-readable name (e.g. "auth subsystem").
    node_uids : frozenset[str]
        The selected intentnode uids. Every uid must exist in the graph.
    scope : str or None
        Optional description of the region this view covers.
    lean_uids : frozenset[str]
        Optional subset of ``node_uids`` to serialize in lean form
        (uid / name / intent / epistemic_state only).
    """

    graph: IntentGraph
    name: str
    node_uids: frozenset[str]
    scope: str | None = None
    lean_uids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        for uid in self.node_uids:
            if uid not in self.graph.nodes:
                raise NodeNotFoundError(
                    f"View node '{uid}' does not exist in the graph"
                )

    def __len__(self) -> int:
        return len(self.node_uids)

    def __contains__(self, uid: str) -> bool:
        return uid in self.node_uids

    def __iter__(self) -> Iterator[str]:
        return iter(self.node_uids)

    def __repr__(self) -> str:
        return (
            f"View(name={self.name!r}, "
            f"nodes={len(self.node_uids)}, "
            f"scope={self.scope!r})"
        )

    # ------------------------------------------------------------------ #
    #  Construction helpers                                               #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_node_set(
        cls,
        graph: IntentGraph,
        name: str,
        node_uids: set[str] | frozenset[str],
        scope: str | None = None,
        *,
        lean_uids: set[str] | frozenset[str] | None = None,
    ) -> View:
        """Build a view from an explicit set of node uids."""
        return cls(
            graph,
            name,
            frozenset(node_uids),
            scope,
            frozenset(lean_uids or ()),
        )

    @classmethod
    def from_depth(
        cls,
        graph: IntentGraph,
        name: str,
        depth: int,
        root_uid: str | None = None,
    ) -> View:
        """Build a view at a uniform depth from a root.

        Nodes at the target depth are included. If a branch is shallower than
        the target depth, its leaf is included instead.

        Parameters
        ----------
        depth : int
            0 = root only, 1 = root's children, etc.
        root_uid : str or None
            Start from this node. Defaults to the graph's single root.
        """
        if root_uid is None:
            roots = graph.roots()
            if len(roots) != 1:
                raise ValueError(
                    f"from_depth requires exactly one root (found {len(roots)}). "
                    f"Specify root_uid explicitly."
                )
            root_uid = roots[0].uid

        selected: set[str] = set()

        def _collect(uid: str, current_depth: int) -> None:
            node = graph.get_node(uid)
            if current_depth == depth or node.is_leaf:
                selected.add(uid)
            else:
                for child in graph.children(uid):
                    _collect(child.uid, current_depth + 1)

        _collect(root_uid, 0)
        return cls(graph, name, frozenset(selected))
