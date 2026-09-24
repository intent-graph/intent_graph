"""Structured diff between an Obsidian vault and a reference IntentGraph.

Compares the vault state (as edited by a human in Obsidian) against a
reference graph, producing a field-level diff of all changes.  Does NOT
auto-apply changes — the caller decides what to do.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from intentgraph.models.graph import IntentGraph
from intentgraph.obsidian._import import import_from_obsidian


# ------------------------------------------------------------------ #
#  Diff result models                                                #
# ------------------------------------------------------------------ #

class NodeFieldDiff(BaseModel):
    """A single field-level change on a node."""

    field: str
    old: Any = None
    new: Any = None


class NodeDiff(BaseModel):
    """A modified node with field-level details."""

    uid: str
    changed_fields: list[NodeFieldDiff] = Field(default_factory=list)


class LinkChange(BaseModel):
    """A link that was added, removed, or modified."""

    uid: str
    src: str
    dst: str
    intent: str = ""


class LinkFieldDiff(BaseModel):
    """A single field-level change on a link."""

    field: str
    old: Any = None
    new: Any = None


class LinkDiff(BaseModel):
    """A modified link with field-level details."""

    uid: str
    src: str
    dst: str
    changed_fields: list[LinkFieldDiff] = Field(default_factory=list)


class DiffResult(BaseModel):
    """Structured diff between Obsidian vault and reference graph.

    All lists are empty when the vault and graph are in sync.
    """

    nodes_added: list[str] = Field(
        default_factory=list,
        description="UIDs of nodes present in vault but not in reference graph",
    )
    nodes_deleted: list[str] = Field(
        default_factory=list,
        description="UIDs of nodes present in reference graph but not in vault",
    )
    nodes_modified: list[NodeDiff] = Field(
        default_factory=list,
        description="Nodes with changed fields",
    )
    links_added: list[LinkChange] = Field(
        default_factory=list,
        description="Links present in vault edges.yaml but not in reference graph",
    )
    links_deleted: list[LinkChange] = Field(
        default_factory=list,
        description="Links present in reference graph but not in vault",
    )
    links_modified: list[LinkDiff] = Field(
        default_factory=list,
        description="Links with changed fields",
    )

    @property
    def has_changes(self) -> bool:
        """True if any differences were detected."""
        return bool(
            self.nodes_added
            or self.nodes_deleted
            or self.nodes_modified
            or self.links_added
            or self.links_deleted
            or self.links_modified
        )

    @property
    def summary(self) -> str:
        """Human-readable one-line summary of changes."""
        parts: list[str] = []
        if self.nodes_added:
            parts.append(f"{len(self.nodes_added)} nodes added")
        if self.nodes_deleted:
            parts.append(f"{len(self.nodes_deleted)} nodes deleted")
        if self.nodes_modified:
            parts.append(f"{len(self.nodes_modified)} nodes modified")
        if self.links_added:
            parts.append(f"{len(self.links_added)} links added")
        if self.links_deleted:
            parts.append(f"{len(self.links_deleted)} links deleted")
        if self.links_modified:
            parts.append(f"{len(self.links_modified)} links modified")
        return ", ".join(parts) if parts else "No changes"


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def diff_obsidian_vs_graph(
    vault_dir: str | Path,
    reference_graph: IntentGraph,
) -> DiffResult:
    """Compare an Obsidian vault against a reference IntentGraph.

    Parses the vault, then performs a field-level diff of nodes and links.

    Parameters
    ----------
    vault_dir : str | Path
        Root directory of the Obsidian vault.
    reference_graph : IntentGraph
        The reference graph to compare against.

    Returns
    -------
    DiffResult
        Structured diff with added/deleted/modified nodes and links.
    """
    vault_graph = import_from_obsidian(vault_dir)

    result = DiffResult()

    # --- Node diff ---
    vault_uids = set(vault_graph.nodes.keys())
    ref_uids = set(reference_graph.nodes.keys())

    result.nodes_added = sorted(vault_uids - ref_uids)
    result.nodes_deleted = sorted(ref_uids - vault_uids)

    # Field-level diff for shared nodes
    for uid in sorted(vault_uids & ref_uids):
        vault_node = vault_graph.get_node(uid)
        ref_node = reference_graph.get_node(uid)
        field_diffs = _diff_node_fields(ref_node, vault_node)
        if field_diffs:
            result.nodes_modified.append(
                NodeDiff(uid=uid, changed_fields=field_diffs)
            )

    # --- Link diff ---
    vault_links = {l.uid: l for l in vault_graph.iter_links()}
    ref_links = {l.uid: l for l in reference_graph.iter_links()}

    vault_link_uids = set(vault_links.keys())
    ref_link_uids = set(ref_links.keys())

    for lid in sorted(vault_link_uids - ref_link_uids):
        link = vault_links[lid]
        result.links_added.append(
            LinkChange(uid=lid, src=link.src, dst=link.dst, intent=link.intent)
        )

    for lid in sorted(ref_link_uids - vault_link_uids):
        link = ref_links[lid]
        result.links_deleted.append(
            LinkChange(uid=lid, src=link.src, dst=link.dst, intent=link.intent)
        )

    for lid in sorted(vault_link_uids & ref_link_uids):
        vault_link = vault_links[lid]
        ref_link = ref_links[lid]
        field_diffs = _diff_link_fields(ref_link, vault_link)
        if field_diffs:
            result.links_modified.append(
                LinkDiff(
                    uid=lid,
                    src=vault_link.src,
                    dst=vault_link.dst,
                    changed_fields=field_diffs,
                )
            )

    return result


# ------------------------------------------------------------------ #
#  Internal diff helpers                                             #
# ------------------------------------------------------------------ #

# Node fields to compare (content fields only, not structural)
_NODE_DIFF_FIELDS = [
    "name",
    "intent",
    "epistemic_state",
    "constraints",
    "examples",
    "design_notes",
    "effort",
    "impl_pointers",
    "data_registry",
    "history",
]

# Link fields to compare
_LINK_DIFF_FIELDS = ["intent", "shape", "parent"]


def _diff_node_fields(ref_node: Any, vault_node: Any) -> list[NodeFieldDiff]:
    """Compare content fields of two nodes, returning a list of diffs."""
    diffs: list[NodeFieldDiff] = []
    for field_name in _NODE_DIFF_FIELDS:
        old_val = _normalize_field(getattr(ref_node, field_name, None))
        new_val = _normalize_field(getattr(vault_node, field_name, None))
        if old_val != new_val:
            diffs.append(NodeFieldDiff(field=field_name, old=old_val, new=new_val))
    return diffs


def _diff_link_fields(ref_link: Any, vault_link: Any) -> list[LinkFieldDiff]:
    """Compare content fields of two links, returning a list of diffs."""
    diffs: list[LinkFieldDiff] = []
    for field_name in _LINK_DIFF_FIELDS:
        old_val = _normalize_field(getattr(ref_link, field_name, None))
        new_val = _normalize_field(getattr(vault_link, field_name, None))
        if old_val != new_val:
            diffs.append(LinkFieldDiff(field=field_name, old=old_val, new=new_val))
    return diffs


def _normalize_field(val: Any) -> Any:
    """Normalize a field value for comparison.

    - Strips whitespace from strings.
    - Converts None to None (no default substitution).
    - Converts Pydantic models in lists to dicts for comparison.
    - Handles dicts recursively (for data_registry).
    """
    if val is None:
        return None
    if isinstance(val, str):
        stripped = val.strip()
        return stripped if stripped else None
    if isinstance(val, dict):
        # Recursively normalize dict values for consistent comparison
        normalized: dict[str, Any] = {}
        for k, v in val.items():
            normalized[k] = _normalize_field(v)
        return normalized if normalized else {}
    if isinstance(val, list):
        normalized: list[Any] = []
        for item in val:
            if hasattr(item, "model_dump"):
                normalized.append(item.model_dump())
            elif isinstance(item, str):
                normalized.append(item.strip())
            else:
                normalized.append(item)
        return normalized if normalized else []
    return val
