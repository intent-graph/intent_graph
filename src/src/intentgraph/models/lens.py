"""Lens — a full-tree view of the IntentGraph with variable LOD.

A Lens is a working view of the graph that:
- Contains all nodes and links within its scope (a valid subtree)
- Applies variable Level of Detail (LOD) to each node based on distance from target
- Can have branches pruned to fit within a size budget
- Supports interactive manipulation (focus, promote, demote, prune, expand)
- Tracks changes (diffs) against the source graph for apply/discard

Design: foundation_and_formalism/LENS_REDESIGN_SPEC.md
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from intentgraph.models.link import IntentLink
from intentgraph.models.node import IntentNode


class LOD(str, Enum):
    """Level of Detail for nodes in a Lens.

    Defines a gradient of detail from skeleton to full:
    - skeleton: uid + name only (orientation)
    - lean: + intent + epistemic_state (context)
    - full: all fields (working zone)

    The system is not hard-coded to exactly three levels - more could be added.
    """
    skeleton = "skeleton"
    lean = "lean"
    full = "full"

    def __lt__(self, other: LOD) -> bool:
        """Enable LOD comparison: skeleton < lean < full."""
        order = {"skeleton": 0, "lean": 1, "full": 2}
        return order[self.value] < order[other.value]

    def __le__(self, other: LOD) -> bool:
        order = {"skeleton": 0, "lean": 1, "full": 2}
        return order[self.value] <= order[other.value]

    def __gt__(self, other: LOD) -> bool:
        order = {"skeleton": 0, "lean": 1, "full": 2}
        return order[self.value] > order[other.value]

    def __ge__(self, other: LOD) -> bool:
        order = {"skeleton": 0, "lean": 1, "full": 2}
        return order[self.value] >= order[other.value]


class LensNode(BaseModel):
    """A node within a Lens with its LOD assignment.

    This is a lightweight wrapper around IntentNode that adds LOD metadata.
    The node data itself is stored separately in Lens.nodes.
    """
    uid: str
    lod: LOD
    pruned_children: int = 0  # Number of children pruned from this node


class LensMeta(BaseModel):
    """Metadata for a Lens state file."""
    name: str
    target_uid: str
    budget: int = 30  # Target node count (pruning threshold)
    source_graph: str  # Path to the source graph file
    scope_root: str | None = None  # Optional: subtree root (None = full graph)


class Lens(BaseModel):
    """A Lens — a full-tree view with variable LOD and pruning.

    Structure:
    - meta: configuration and source tracking
    - nodes: dict[uid, IntentNode] — the actual node data (deep copied from graph)
    - node_metadata: dict[uid, LensNode] — LOD and pruning info per node
    - treearcs: list of (parent, child) pairs — tree structure
    - intentlinks: dict[uid, IntentLink] — visible links (both endpoints ≥ lean)
    - pruned_subtrees: list[uid] — subtree roots that have been pruned from view

    Visibility rules:
    - Nodes: all nodes in scope are present (possibly pruned branches)
    - IntentLinks: visible only if both src and dst are at lean LOD or above
    - IntentLink description: shown only if at least one endpoint is at full LOD

    State management:
    - base_state: snapshot of (nodes, treearcs, intentlinks) when lens was last synced with graph
    - working_state: current state (includes all edits made via CLI)
    - dirty: True if working_state != base_state
    """
    meta: LensMeta

    # Node data and metadata
    nodes: dict[str, IntentNode] = Field(default_factory=dict)
    node_metadata: dict[str, LensNode] = Field(default_factory=dict)

    # Tree structure
    treearcs: list[tuple[str, str]] = Field(default_factory=list)

    # Intentlinks (visibility filtered)
    intentlinks: dict[str, IntentLink] = Field(default_factory=dict)

    # Pruning state
    pruned_subtrees: list[str] = Field(default_factory=list)

    # Diff tracking (for apply/discard)
    base_state: dict[str, Any] | None = Field(default=None, exclude=True)
    dirty: bool = Field(default=False, exclude=True)

    def get_lod(self, uid: str) -> LOD:
        """Get the LOD of a node, or raise KeyError if not in lens."""
        return self.node_metadata[uid].lod

    def set_lod(self, uid: str, lod: LOD) -> None:
        """Set the LOD of a node. Marks the lens as dirty if this is a content change.

        Note: LOD changes are viewport operations and don't affect the graph.
        They don't contribute to the diff for apply().
        """
        if uid not in self.node_metadata:
            raise KeyError(f"Node '{uid}' not in lens")
        self.node_metadata[uid].lod = lod

    def is_pruned(self, uid: str) -> bool:
        """Check if a node's subtree has been pruned."""
        return uid in self.pruned_subtrees

    def mark_dirty(self) -> None:
        """Mark the lens as having unsaved changes."""
        self.dirty = True

    def snapshot_base_state(self) -> None:
        """Capture current working state as the base (after sync or apply)."""
        self.base_state = {
            "nodes": {uid: node.model_dump() for uid, node in self.nodes.items()},
            "treearcs": list(self.treearcs),
            "intentlinks": {uid: link.model_dump() for uid, link in self.intentlinks.items()},
        }
        self.dirty = False

    def node_count(self) -> int:
        """Total number of nodes in the lens (excluding pruned subtrees)."""
        return len(self.nodes)

    def lod_stats(self) -> dict[str, int]:
        """Count nodes at each LOD level."""
        stats: dict[str, int] = {"skeleton": 0, "lean": 0, "full": 0}
        for meta in self.node_metadata.values():
            stats[meta.lod.value] += 1
        return stats

    def visible_link_count(self) -> int:
        """Number of intentlinks visible at current LOD settings."""
        return len(self.intentlinks)

    def to_serial_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence.

        Excludes base_state and dirty (runtime-only fields).
        """
        return {
            "lens": self.meta.model_dump(),
            "nodes": {
                uid: {
                    **node.to_serial_dict(),
                    "lod": self.node_metadata[uid].lod.value,
                    **({"pruned_children": self.node_metadata[uid].pruned_children}
                       if self.node_metadata[uid].pruned_children > 0 else {}),
                }
                for uid, node in self.nodes.items()
            },
            "treearcs": [{"parent": p, "child": c} for p, c in self.treearcs],
            "intentlinks": [link.to_serial_dict() for link in self.intentlinks.values()],
            "pruned_subtrees": self.pruned_subtrees,
        }

    @classmethod
    def from_serial_dict(cls, d: dict[str, Any]) -> Lens:
        """Deserialize from persistence dict."""
        meta = LensMeta.model_validate(d["lens"])

        # Parse nodes and extract LOD metadata
        nodes: dict[str, IntentNode] = {}
        node_metadata: dict[str, LensNode] = {}

        for uid, node_dict in d.get("nodes", {}).items():
            lod_str = node_dict.pop("lod", "full")
            pruned_children = node_dict.pop("pruned_children", 0)

            node = IntentNode.from_serial_dict(node_dict)
            nodes[uid] = node
            node_metadata[uid] = LensNode(
                uid=uid,
                lod=LOD(lod_str),
                pruned_children=pruned_children,
            )

        # Rebuild treearc adjacency on nodes
        treearcs: list[tuple[str, str]] = []
        for tarc in d.get("treearcs", []):
            parent_uid = tarc["parent"]
            child_uid = tarc["child"]
            treearcs.append((parent_uid, child_uid))
            if parent_uid in nodes and child_uid in nodes:
                nodes[child_uid].parent_uid = parent_uid
                if child_uid not in nodes[parent_uid].children_uids:
                    nodes[parent_uid].children_uids.append(child_uid)

        # Parse intentlinks
        intentlinks: dict[str, IntentLink] = {}
        for link_dict in d.get("intentlinks", []):
            link = IntentLink.from_serial_dict(link_dict)
            intentlinks[link.uid] = link

        pruned_subtrees = d.get("pruned_subtrees", [])

        lens = cls(
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
