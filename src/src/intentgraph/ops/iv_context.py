"""IV-context helpers — target adjacency and detail-tier partitioning.

Provide target-adjacency queries used by the Navigator and the context
assembly layer: given a working view and a target node, decide which nodes
get full detail and which get lean detail (uid / name / intent /
epistemic_state only).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intentgraph.models.graph import IntentGraph
    from intentgraph.models.view import View

IV_CONTEXT_MODE_FULL = "full"
IV_CONTEXT_MODE_LEAN = "lean"
_IV_CONTEXT_MODES = frozenset({IV_CONTEXT_MODE_FULL, IV_CONTEXT_MODE_LEAN})


def _validate_iv_context_mode(mode: str) -> None:
    if mode not in _IV_CONTEXT_MODES:
        raise ValueError(
            f"Unknown iv_context_mode='{mode}'. "
            f"Expected one of: {sorted(_IV_CONTEXT_MODES)}"
        )


def target_neighbor_uids(graph: IntentGraph, target_uid: str) -> set[str]:
    """Return the UIDs of all direct neighbors of *target_uid*.

    Direct neighbors are the union of:
    - ``parent(target)``
    - ``children(target)``
    - endpoints of intentlinks whose ``src`` or ``dst`` is *target_uid*

    The target itself is **excluded** from the returned set.
    This is a pure graph query — it does not reference any view.
    """
    neighbors: set[str] = set()

    parent = graph.parent(target_uid)
    if parent is not None:
        neighbors.add(parent.uid)

    neighbors.update(c.uid for c in graph.children(target_uid))

    for link in graph.iter_links():
        if link.src == target_uid:
            neighbors.add(link.dst)
        elif link.dst == target_uid:
            neighbors.add(link.src)

    neighbors.discard(target_uid)
    return neighbors


def build_iv_context_profile(
    graph: IntentGraph,
    view: View,
    *,
    target_uid: str,
    iv_context_mode: str = IV_CONTEXT_MODE_FULL,
) -> dict:
    """Partition view nodes into full-detail and lean-detail tiers.

    The node *set* stays unchanged (view membership is not altered).
    Only the **detail level** per node changes:

    - **full** mode: every view node gets full detail.
    - **lean** mode: only the target and its direct neighbors (within the
      view) get full detail; all other view nodes are lean
      (uid / name / intent / epistemic_state only).

    Returns a dict with keys:
        target_uid, mode, direct_neighbor_uids,
        full_detail_uids, lean_detail_uids, node_count.
    """
    _validate_iv_context_mode(iv_context_mode)

    if target_uid not in view.node_uids:
        raise ValueError(
            f"target_uid '{target_uid}' is not part of view '{view.name}'"
        )

    view_uids = set(view.node_uids)
    neighbors = target_neighbor_uids(graph, target_uid)
    neighbors_in_view = neighbors & view_uids

    if iv_context_mode == IV_CONTEXT_MODE_FULL:
        full_detail_uids = set(view_uids)
        lean_detail_uids: set[str] = set()
    else:
        full_detail_uids = {target_uid} | neighbors_in_view
        lean_detail_uids = view_uids - full_detail_uids

    return {
        "target_uid": target_uid,
        "mode": iv_context_mode,
        "direct_neighbor_uids": sorted(neighbors_in_view),
        "full_detail_uids": sorted(full_detail_uids),
        "lean_detail_uids": sorted(lean_detail_uids),
        "node_count": len(view_uids),
    }
