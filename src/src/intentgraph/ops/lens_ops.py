"""Lens operations — build, manipulate, diff, apply.

Implements the Lens concept from foundation_and_formalism/LENS_REDESIGN_SPEC.md.

Core operations:
- build_lens: construct a Lens from an IntentGraph with IV_ LOD assignment
- Focus manipulation: set_lod, promote, demote, focus_on
- Scope manipulation: prune_subtree, expand_subtree, set_budget
- Diff/apply: compute_diff, apply_diff, discard_changes
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from intentgraph.errors import IntentGraphError
from intentgraph.models.lens import Lens, LensMeta, LensNode, LOD
from intentgraph.models.link import IntentLink
from intentgraph.models.node import IntentNode

if TYPE_CHECKING:
    from intentgraph.models.graph import IntentGraph


# ================================================================== #
#  Lens Builder — IV_ LOD assignment + pruning                       #
# ================================================================== #


def build_lens(
    graph: IntentGraph,
    *,
    target_uid: str,
    budget: int = 30,
    source_graph_path: str = "graph.json",
    name: str = "working-lens",
    scope_root: str | None = None,
) -> Lens:
    """Build a Lens from an IntentGraph with IV_ LOD assignment.

    LOD assignment follows the IV_ pattern (§2.4 of design):
    - `_` (full): target + direct neighbors (treearc + intentlink)
    - `I` (lean): all ancestors from target up to root
    - `V` (lean): all L1 nodes (direct children of root)
    - Everything else: skeleton

    Pruning (§2.5):
    - If node count exceeds budget, prune most distant leaves first
    - Pruned nodes are removed; their parent shows `pruned_children` count

    IntentLink visibility (§2.3):
    - Link is present only if both endpoints are at lean LOD or above
    - Link description is shown only if at least one endpoint is at full LOD

    Parameters
    ----------
    graph : IntentGraph
        Source graph
    target_uid : str
        Target node (center of IV_ pattern)
    budget : int
        Maximum node count (triggers pruning if exceeded)
    source_graph_path : str
        Path to source graph file (for metadata tracking)
    name : str
        Lens name
    scope_root : str | None
        Optional subtree root (None = full graph)

    Returns
    -------
    Lens
        A new Lens with IV_ LOD assignment and pruning applied
    """
    # Validate target exists
    target_node = graph.get_node(target_uid)

    # Determine scope (full graph or subtree)
    if scope_root:
        scope_node = graph.get_node(scope_root)
        if not graph.is_above(scope_root, target_uid):
            raise IntentGraphError(
                f"Target '{target_uid}' is not within scope subtree '{scope_root}'"
            )
        scope_uids = {scope_root} | graph.desc(scope_root)
    else:
        # Full graph
        scope_uids = set(graph.nodes.keys())

    # Step 1: Assign LOD using IV_ pattern
    node_lod = _assign_iv_lod(graph, target_uid, scope_uids)

    # Step 2: Prune if over budget
    nodes_to_include = set(node_lod.keys())
    pruned_subtrees: list[str] = []

    if len(nodes_to_include) > budget:
        nodes_to_include, pruned_subtrees = _prune_to_budget(
            graph, target_uid, nodes_to_include, budget
        )

    # Step 3: Deep copy nodes and build metadata
    nodes: dict[str, IntentNode] = {}
    node_metadata: dict[str, LensNode] = {}

    for uid in nodes_to_include:
        node = graph.get_node(uid)
        nodes[uid] = deepcopy(node)

        # Count pruned children
        pruned_children = sum(
            1 for child in node.children_uids
            if child in pruned_subtrees or child not in nodes_to_include
        )

        node_metadata[uid] = LensNode(
            uid=uid,
            lod=node_lod[uid],
            pruned_children=pruned_children,
        )

    # Step 4: Extract treearcs (both endpoints in lens)
    treearcs: list[tuple[str, str]] = []
    for uid in nodes_to_include:
        node = graph.get_node(uid)
        for child_uid in node.children_uids:
            if child_uid in nodes_to_include:
                treearcs.append((uid, child_uid))

    # Step 5: Extract intentlinks with visibility filtering
    intentlinks: dict[str, IntentLink] = {}
    for link in graph.iter_links():
        src_lod = node_lod.get(link.src)
        dst_lod = node_lod.get(link.dst)

        # Visibility rule: both endpoints must be at lean or above
        if src_lod and dst_lod and src_lod >= LOD.lean and dst_lod >= LOD.lean:
            intentlinks[link.uid] = deepcopy(link)

    # Step 6: Construct Lens
    meta = LensMeta(
        name=name,
        target_uid=target_uid,
        budget=budget,
        source_graph=source_graph_path,
        scope_root=scope_root,
    )

    lens = Lens(
        meta=meta,
        nodes=nodes,
        node_metadata=node_metadata,
        treearcs=treearcs,
        intentlinks=intentlinks,
        pruned_subtrees=pruned_subtrees,
    )

    # Snapshot base state for diff tracking
    lens.snapshot_base_state()

    return lens


def _assign_iv_lod(
    graph: IntentGraph,
    target_uid: str,
    scope_uids: set[str],
) -> dict[str, LOD]:
    """Assign LOD to nodes using IV_ pattern.

    - `_` (full): target + direct neighbors (parent, children, intentlink endpoints)
    - `I` (lean): ancestors of target up to root
    - `V` (lean): all L1 nodes (direct children of root)
    - Everything else: skeleton
    """
    lod_map: dict[str, LOD] = {}

    # Default: all nodes in scope get skeleton
    for uid in scope_uids:
        lod_map[uid] = LOD.skeleton

    # V: L1 nodes (direct children of root) get lean
    roots = graph.roots()
    for root in roots:
        for child in graph.children(root.uid):
            if child.uid in scope_uids:
                lod_map[child.uid] = LOD.lean

    # I: Ancestors of target get lean
    current = graph.get_node(target_uid)
    while current.parent_uid is not None:
        if current.parent_uid in scope_uids:
            lod_map[current.parent_uid] = LOD.lean
        current = graph.get_node(current.parent_uid)

    # _: Target + direct neighbors get full
    lod_map[target_uid] = LOD.full

    # Treearc neighbors (parent + children)
    parent = graph.parent(target_uid)
    if parent and parent.uid in scope_uids:
        lod_map[parent.uid] = LOD.full

    for child in graph.children(target_uid):
        if child.uid in scope_uids:
            lod_map[child.uid] = LOD.full

    # Intentlink neighbors
    for link in graph.iter_links():
        if link.src == target_uid and link.dst in scope_uids:
            lod_map[link.dst] = LOD.full
        elif link.dst == target_uid and link.src in scope_uids:
            lod_map[link.src] = LOD.full

    return lod_map


def _prune_to_budget(
    graph: IntentGraph,
    target_uid: str,
    nodes: set[str],
    budget: int,
) -> tuple[set[str], list[str]]:
    """Prune nodes to fit within budget using graph-distance-based leaf removal.

    Algorithm (§2.5):
    1. Compute graph distance from target to every node
    2. Sort by distance (descending)
    3. Remove the most distant leaf subtrees first (leaves-first, recursively)
    4. Stop when under budget

    Returns:
        (nodes_to_keep, pruned_subtree_roots)
    """
    # Compute graph distance from target (BFS)
    distances: dict[str, int] = _compute_graph_distances(graph, target_uid, nodes)

    # Sort nodes by distance (most distant first)
    sorted_by_distance = sorted(nodes, key=lambda uid: distances.get(uid, float('inf')), reverse=True)

    nodes_to_keep = set(nodes)
    pruned_subtrees: list[str] = []

    for uid in sorted_by_distance:
        if len(nodes_to_keep) <= budget:
            break

        # Only prune leaves (or nodes whose descendants have all been pruned)
        node = graph.get_node(uid)
        children_in_lens = [c for c in node.children_uids if c in nodes_to_keep]

        if not children_in_lens:  # Is a leaf in the current lens
            nodes_to_keep.discard(uid)
            pruned_subtrees.append(uid)

    return nodes_to_keep, pruned_subtrees


def _compute_graph_distances(
    graph: IntentGraph,
    target_uid: str,
    scope_uids: set[str],
) -> dict[str, int]:
    """Compute graph distance from target to every node in scope using BFS.

    Distance is the minimum number of edges (treearcs or intentlinks) to reach target.
    """
    from collections import deque

    distances: dict[str, int] = {target_uid: 0}
    queue: deque[str] = deque([target_uid])

    while queue:
        current_uid = queue.popleft()
        current_dist = distances[current_uid]

        # Explore neighbors (parent, children, intentlink endpoints)
        neighbors: set[str] = set()

        parent = graph.parent(current_uid)
        if parent:
            neighbors.add(parent.uid)

        neighbors.update(c.uid for c in graph.children(current_uid))

        for link in graph.iter_links():
            if link.src == current_uid:
                neighbors.add(link.dst)
            elif link.dst == current_uid:
                neighbors.add(link.src)

        for neighbor_uid in neighbors:
            if neighbor_uid in scope_uids and neighbor_uid not in distances:
                distances[neighbor_uid] = current_dist + 1
                queue.append(neighbor_uid)

    return distances


# ================================================================== #
#  LOD Manipulation                                                  #
# ================================================================== #


def promote(lens: Lens, uid: str) -> None:
    """Promote a node's LOD: skeleton → lean, or lean → full."""
    current_lod = lens.get_lod(uid)
    if current_lod == LOD.skeleton:
        lens.set_lod(uid, LOD.lean)
    elif current_lod == LOD.lean:
        lens.set_lod(uid, LOD.full)
    # If already full, no-op


def demote(lens: Lens, uid: str) -> None:
    """Demote a node's LOD: full → lean, or lean → skeleton."""
    current_lod = lens.get_lod(uid)
    if current_lod == LOD.full:
        lens.set_lod(uid, LOD.lean)
    elif current_lod == LOD.lean:
        lens.set_lod(uid, LOD.skeleton)
    # If already skeleton, no-op


def focus_on(lens: Lens, graph: IntentGraph, new_target_uid: str) -> None:
    """Refocus the lens on a new target node, recalculating all LODs via IV_.

    This is a viewport operation (no graph edits), but triggers a full LOD reassignment.
    """
    if new_target_uid not in lens.nodes:
        raise IntentGraphError(f"Node '{new_target_uid}' not in lens")

    # Recompute LOD for all nodes in lens
    scope_uids = set(lens.nodes.keys())
    new_lod_map = _assign_iv_lod(graph, new_target_uid, scope_uids)

    for uid in scope_uids:
        lens.set_lod(uid, new_lod_map[uid])

    lens.meta.target_uid = new_target_uid


# ================================================================== #
#  Scope Manipulation (Prune/Expand)                                 #
# ================================================================== #


def prune_subtree(lens: Lens, uid: str) -> None:
    """Remove a subtree from the lens (viewport operation, no graph edit).

    The subtree root is marked as pruned, and its descendants are removed.
    This reduces node count and may bring the lens under budget.
    """
    if uid not in lens.nodes:
        raise IntentGraphError(f"Node '{uid}' not in lens")

    # Collect subtree (node + all descendants)
    subtree_uids = _collect_subtree(lens, uid)

    # Remove from lens
    for sub_uid in subtree_uids:
        lens.nodes.pop(sub_uid, None)
        lens.node_metadata.pop(sub_uid, None)

    # Remove treearcs involving pruned nodes
    lens.treearcs = [
        (p, c) for p, c in lens.treearcs
        if p not in subtree_uids and c not in subtree_uids
    ]

    # Remove intentlinks involving pruned nodes
    lens.intentlinks = {
        link_uid: link for link_uid, link in lens.intentlinks.items()
        if link.src not in subtree_uids and link.dst not in subtree_uids
    }

    # Mark as pruned
    if uid not in lens.pruned_subtrees:
        lens.pruned_subtrees.append(uid)


def expand_subtree(lens: Lens, graph: IntentGraph, uid: str, depth: int | None = None) -> None:
    """Add a pruned subtree back into the lens from the full graph.

    If the subtree was previously pruned, this restores it. LOD is assigned
    based on distance from current target (skeleton by default, unless within
    IV_ zones).

    Parameters
    ----------
    uid : str
        Root of the subtree to expand
    depth : int | None
        Maximum depth to expand (None = full subtree)
    """
    if uid in lens.nodes:
        # Already in lens, nothing to do
        return

    # Collect subtree from graph
    subtree_uids = _collect_graph_subtree(graph, uid, depth)

    # Assign LOD (default skeleton, unless within IV_ pattern)
    target_uid = lens.meta.target_uid
    scope_uids = set(lens.nodes.keys()) | subtree_uids
    lod_map = _assign_iv_lod(graph, target_uid, scope_uids)

    # Add nodes
    for sub_uid in subtree_uids:
        if sub_uid not in lens.nodes:
            lens.nodes[sub_uid] = deepcopy(graph.get_node(sub_uid))
            lens.node_metadata[sub_uid] = LensNode(
                uid=sub_uid,
                lod=lod_map.get(sub_uid, LOD.skeleton),
                pruned_children=0,
            )

    # Add treearcs
    for sub_uid in subtree_uids:
        node = graph.get_node(sub_uid)
        for child_uid in node.children_uids:
            if child_uid in lens.nodes:
                arc = (sub_uid, child_uid)
                if arc not in lens.treearcs:
                    lens.treearcs.append(arc)

    # Add intentlinks (with visibility filtering)
    for link in graph.iter_links():
        if link.src in lens.nodes and link.dst in lens.nodes:
            src_lod = lens.get_lod(link.src)
            dst_lod = lens.get_lod(link.dst)
            if src_lod >= LOD.lean and dst_lod >= LOD.lean:
                if link.uid not in lens.intentlinks:
                    lens.intentlinks[link.uid] = deepcopy(link)

    # Remove from pruned list
    if uid in lens.pruned_subtrees:
        lens.pruned_subtrees.remove(uid)


def set_budget(lens: Lens, graph: IntentGraph, new_budget: int) -> None:
    """Resize the lens to a new budget, auto-pruning or expanding as needed.

    If new budget < current node count: prune most distant leaves
    If new budget > current node count: attempt to expand pruned subtrees
    """
    current_count = lens.node_count()

    if new_budget < current_count:
        # Need to prune
        nodes_to_keep = set(lens.nodes.keys())
        target_uid = lens.meta.target_uid
        nodes_to_keep, additional_pruned = _prune_to_budget(
            graph, target_uid, nodes_to_keep, new_budget
        )

        # Remove pruned nodes
        for uid in list(lens.nodes.keys()):
            if uid not in nodes_to_keep:
                prune_subtree(lens, uid)

    elif new_budget > current_count and lens.pruned_subtrees:
        # Try to expand pruned subtrees until budget filled
        # Priority: nearest to target first
        target_uid = lens.meta.target_uid
        distances = _compute_graph_distances(graph, target_uid, set(graph.nodes.keys()))

        sorted_pruned = sorted(
            lens.pruned_subtrees,
            key=lambda uid: distances.get(uid, float('inf'))
        )

        for pruned_uid in sorted_pruned:
            if lens.node_count() >= new_budget:
                break
            expand_subtree(lens, graph, pruned_uid)

    lens.meta.budget = new_budget


def _collect_subtree(lens: Lens, root_uid: str) -> set[str]:
    """Collect all nodes in a subtree within the lens (BFS)."""
    subtree: set[str] = {root_uid}
    queue = [root_uid]

    while queue:
        current_uid = queue.pop(0)
        node = lens.nodes.get(current_uid)
        if node:
            for child_uid in node.children_uids:
                if child_uid in lens.nodes and child_uid not in subtree:
                    subtree.add(child_uid)
                    queue.append(child_uid)

    return subtree


def _collect_graph_subtree(graph: IntentGraph, root_uid: str, max_depth: int | None) -> set[str]:
    """Collect all nodes in a subtree from the graph (BFS with depth limit)."""
    subtree: set[str] = {root_uid}
    queue: list[tuple[str, int]] = [(root_uid, 0)]

    while queue:
        current_uid, depth = queue.pop(0)
        node = graph.get_node(current_uid)

        for child_uid in node.children_uids:
            if child_uid not in subtree:
                subtree.add(child_uid)
                if max_depth is None or depth + 1 < max_depth:
                    queue.append((child_uid, depth + 1))

    return subtree


# ================================================================== #
#  Diff and Apply                                                    #
# ================================================================== #


def compute_diff(lens: Lens) -> dict[str, list[dict]]:
    """Compute diff between base state and working state.

    Returns a structured diff with categories:
    - nodes_created: [{uid, name, intent, parent, ...}]
    - nodes_modified: [{uid, field, old_value, new_value}]
    - nodes_deleted: [{uid}]
    - links_created: [{uid, src, dst, intent, ...}]
    - links_modified: [{uid, field, old_value, new_value}]
    - links_deleted: [{uid}]
    - treearcs_modified: [{child_uid, old_parent, new_parent}]

    LOD changes are NOT included (viewport operations).
    """
    if not lens.base_state:
        # No base state yet - treat all as created
        return {
            "nodes_created": [
                {**node.to_serial_dict(), "parent": node.parent_uid}
                for node in lens.nodes.values()
            ],
            "nodes_modified": [],
            "nodes_deleted": [],
            "links_created": [link.to_serial_dict() for link in lens.intentlinks.values()],
            "links_modified": [],
            "links_deleted": [],
            "treearcs_modified": [],
        }

    base_nodes = lens.base_state["nodes"]
    base_treearcs = set(tuple(t) if isinstance(t, list) else t for t in lens.base_state["treearcs"])
    base_links = lens.base_state["intentlinks"]

    working_nodes = {uid: node.model_dump() for uid, node in lens.nodes.items()}
    working_treearcs = set(lens.treearcs)
    working_links = {uid: link.model_dump() for uid, link in lens.intentlinks.items()}

    diff: dict[str, list[dict]] = {
        "nodes_created": [],
        "nodes_modified": [],
        "nodes_deleted": [],
        "links_created": [],
        "links_modified": [],
        "links_deleted": [],
        "treearcs_modified": [],
    }

    # Nodes: created
    for uid in working_nodes:
        if uid not in base_nodes:
            node = lens.nodes[uid]
            diff["nodes_created"].append({
                **node.to_serial_dict(),
                "parent": node.parent_uid,
            })

    # Nodes: deleted
    for uid in base_nodes:
        if uid not in working_nodes:
            diff["nodes_deleted"].append({"uid": uid})

    # Nodes: modified
    for uid in working_nodes:
        if uid in base_nodes:
            base_node = base_nodes[uid]
            working_node = working_nodes[uid]
            for field in working_node:
                if field in {"uid", "parent_uid", "children_uids"}:
                    continue
                old_val = base_node.get(field)
                new_val = working_node.get(field)
                if old_val != new_val:
                    diff["nodes_modified"].append({
                        "uid": uid,
                        "field": field,
                        "old_value": old_val,
                        "new_value": new_val,
                    })

    # Treearcs: parent changes (reparenting)
    base_parent_map = {child: parent for parent, child in base_treearcs}
    working_parent_map = {child: parent for parent, child in working_treearcs}

    for child_uid in working_parent_map:
        old_parent = base_parent_map.get(child_uid)
        new_parent = working_parent_map[child_uid]
        if old_parent and old_parent != new_parent:
            diff["treearcs_modified"].append({
                "child_uid": child_uid,
                "old_parent": old_parent,
                "new_parent": new_parent,
            })

    # Links: created
    for uid in working_links:
        if uid not in base_links:
            diff["links_created"].append(working_links[uid])

    # Links: deleted
    for uid in base_links:
        if uid not in working_links:
            diff["links_deleted"].append({"uid": uid})

    # Links: modified
    for uid in working_links:
        if uid in base_links:
            base_link = base_links[uid]
            working_link = working_links[uid]
            for field in working_link:
                if field in {"uid", "src", "dst"}:
                    continue
                old_val = base_link.get(field)
                new_val = working_link.get(field)
                if old_val != new_val:
                    diff["links_modified"].append({
                        "uid": uid,
                        "field": field,
                        "old_value": old_val,
                        "new_value": new_val,
                    })

    return diff


def apply_diff(lens: Lens, graph: IntentGraph) -> list[str]:
    """Apply lens changes to the source graph.

    Returns a list of human-readable change descriptions.
    Resets the lens base state after applying.
    """
    diff = compute_diff(lens)
    log: list[str] = []

    # Apply node deletions first (leaves first to avoid parent issues)
    for entry in diff["nodes_deleted"]:
        uid = entry["uid"]
        graph.remove_node(uid, cascade=True)
        log.append(f"Deleted node '{uid}'")

    # Apply node creations
    for entry in diff["nodes_created"]:
        uid = entry.pop("uid")
        name = entry.pop("name")
        intent = entry.pop("intent")
        parent = entry.pop("parent", None)

        graph.add_node(uid, name, intent, **entry)
        if parent:
            graph.attach(parent, uid)
        log.append(f"Created node '{uid}'")

    # Apply node modifications
    for entry in diff["nodes_modified"]:
        uid = entry["uid"]
        field = entry["field"]
        new_value = entry["new_value"]
        graph.update_node(uid, **{field: new_value})
        log.append(f"Modified node '{uid}': {field}")

    # Apply treearc modifications (reparenting)
    for entry in diff["treearcs_modified"]:
        child_uid = entry["child_uid"]
        old_parent = entry["old_parent"]
        new_parent = entry["new_parent"]
        graph.detach(old_parent, child_uid)
        # Skip UID validation on reparent: the UID is stable, only the tree structure changes
        graph.attach(new_parent, child_uid, skip_uid_validation=True)
        log.append(f"Reparented '{child_uid}': {old_parent} → {new_parent}")

    # Apply link deletions
    for entry in diff["links_deleted"]:
        uid = entry["uid"]
        graph.remove_link(uid)
        log.append(f"Deleted link '{uid}'")

    # Apply link creations
    for entry in diff["links_created"]:
        uid = entry.pop("uid", None)
        src = entry.pop("src")
        dst = entry.pop("dst")
        intent = entry.pop("intent")
        graph.add_link(src, dst, intent, uid=uid, **entry)
        log.append(f"Created link '{src}' → '{dst}'")

    # Apply link modifications
    for entry in diff["links_modified"]:
        uid = entry["uid"]
        field = entry["field"]
        new_value = entry["new_value"]
        graph.update_link(uid, **{field: new_value})
        log.append(f"Modified link '{uid}': {field}")

    # Reset lens base state
    lens.snapshot_base_state()

    return log


def discard_changes(lens: Lens) -> None:
    """Discard all working changes, resetting to base state.

    This is the 'git checkout -- .' equivalent for the lens.
    """
    if not lens.base_state:
        raise IntentGraphError("No base state to revert to")

    # Restore from base state
    base_nodes = lens.base_state["nodes"]
    base_treearcs = lens.base_state["treearcs"]
    base_links = lens.base_state["intentlinks"]

    lens.nodes = {uid: IntentNode.from_serial_dict(node_dict) for uid, node_dict in base_nodes.items()}
    lens.treearcs = [tuple(t) if isinstance(t, list) else t for t in base_treearcs]
    lens.intentlinks = {uid: IntentLink.from_serial_dict(link_dict) for uid, link_dict in base_links.items()}

    lens.dirty = False
