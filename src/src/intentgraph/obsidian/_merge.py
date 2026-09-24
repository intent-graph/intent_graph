"""Lossless merge: apply Obsidian vault edits back into a canonical IntentGraph.

Merge is content-only: vault modifications to existing nodes are applied,
but structural changes (adding/removing nodes or links) are not permitted.
Conflict detection uses snapshot baseline to distinguish intentional edits
from parallel changes to the canonical graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from intentgraph.models.graph import IntentGraph
from intentgraph.obsidian._diff import diff_obsidian_vs_graph, NodeDiff
from intentgraph.obsidian._snapshot import load_snapshot, node_content_hash


# ---- Result model ----

class MergeReport(BaseModel):
    """Result of a merge operation."""

    applied_nodes: list[str] = Field(
        default_factory=list,
        description="UIDs of nodes successfully updated",
    )
    applied_links: list[str] = Field(
        default_factory=list,
        description="UIDs of links successfully updated",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="UIDs where both vault and canonical changed since export",
    )
    ignored_added: list[str] = Field(
        default_factory=list,
        description="UIDs of vault nodes not in canonical (content-only: not created)",
    )
    ignored_deleted: list[str] = Field(
        default_factory=list,
        description="UIDs of canonical nodes absent from vault (never deleted)",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Error messages (malformed files, etc.)",
    )

    @property
    def has_changes(self) -> bool:
        """True if any nodes or links were applied."""
        return bool(self.applied_nodes or self.applied_links)

    @property
    def summary(self) -> str:
        """Human-readable one-line summary of merge result."""
        parts: list[str] = []
        if self.applied_nodes:
            parts.append(f"{len(self.applied_nodes)} nodes applied")
        if self.applied_links:
            parts.append(f"{len(self.applied_links)} links applied")
        if self.conflicts:
            parts.append(f"{len(self.conflicts)} conflicts (skipped)")
        if self.ignored_added:
            parts.append(f"{len(self.ignored_added)} vault nodes ignored")
        if self.ignored_deleted:
            parts.append(f"{len(self.ignored_deleted)} deletions ignored")
        if self.errors:
            parts.append(f"{len(self.errors)} errors")
        return ", ".join(parts) if parts else "No changes"


# ---- Public API ----

def merge_obsidian_into_graph(
    vault_dir: str | Path,
    graph: IntentGraph,
    *,
    snapshot: dict[str, Any] | None = None,
    on_malformed: Literal["fail", "skip"] = "fail",
    allow_structural: bool = False,
) -> MergeReport:
    """Apply Obsidian vault edits to a canonical IntentGraph.

    Merge is content-only (phase 1): field updates to existing nodes are
    applied; structural changes (add/remove) are logged but not applied.
    Whole-node conflict detection: if snapshot is provided, a node that
    was modified in vault but also changed in canonical is treated as a
    conflict and skipped.

    Parameters
    ----------
    vault_dir : str | Path
        Root directory of Obsidian vault (contains ``nodes/``, ``edges.yaml``).
    graph : IntentGraph
        The canonical graph to merge into (mutated in place).
    snapshot : dict | None
        Optional baseline snapshot from export. When present, used to detect
        conflicts (node changed on both sides). When absent, all vault edits
        are applied (weaker guarantee).
    on_malformed : Literal["fail", "skip"]
        If "fail" (default), halt and return errors on any unparseable node files.
        If "skip", record errors and treat unparseable nodes as unknown.
    allow_structural : bool
        If False (default), structural changes (add/remove) are not applied
        and are logged in ignored_added / ignored_deleted. If True, raises
        NotImplementedError (reserved for future phase 2).

    Returns
    -------
    MergeReport
        Summary of applied changes, conflicts, and errors.
    """
    report = MergeReport()

    if allow_structural:
        raise NotImplementedError(
            "Structural merge (add/remove nodes/links) is not yet implemented."
        )

    # ---- Detect malformed files first ----
    vault_path = Path(vault_dir).resolve()
    nodes_dir = vault_path / "nodes"
    skip_uids: set[str] = set()

    if nodes_dir.is_dir():
        for md_file in sorted(nodes_dir.glob("*.md")):
            # Try parsing; _parse_node_file returns None on failure
            from intentgraph.obsidian._import import _parse_node_file
            parsed = _parse_node_file(md_file)
            if parsed is None:
                error_msg = f"Malformed node file: {md_file.name}"
                report.errors.append(error_msg)
                # Extract uid from filename if possible
                from intentgraph.obsidian._format import uid_from_stem
                try:
                    uid = uid_from_stem(md_file.stem)
                    skip_uids.add(uid)
                except Exception:
                    pass

    # On malformed + fail mode, return early with errors
    if report.errors and on_malformed == "fail":
        return report

    # ---- Compute diff ----
    diff = diff_obsidian_vs_graph(vault_dir, graph)

    # ---- Content-only guardrails ----
    # Nodes added in vault → ignored (not created)
    report.ignored_added = diff.nodes_added

    # Nodes deleted in vault → ignored (never deleted), except skipped files
    # (which are not really deletions, just unreadable)
    report.ignored_deleted = [
        uid for uid in diff.nodes_deleted if uid not in skip_uids
    ]

    # ---- Apply node updates ----
    for node_diff in diff.nodes_modified:
        uid = node_diff.uid
        vault_node = graph.get_node_or_none(uid)
        if vault_node is None:
            continue

        # Conflict detection: if snapshot present, check if canonical changed
        # since export. Compare hashes to detect both-sides-changed.
        if snapshot is not None:
            canonical_hash = node_content_hash(vault_node)
            baseline_hash = snapshot.get("nodes", {}).get(uid)
            if baseline_hash and canonical_hash != baseline_hash:
                # Both sides changed → conflict
                report.conflicts.append(uid)
                continue

        # No conflict → apply all changed fields
        changes: dict[str, Any] = {}
        for field_diff in node_diff.changed_fields:
            changes[field_diff.field] = field_diff.new

        if changes:
            graph.update_node(uid, **changes)
            report.applied_nodes.append(uid)

    # ---- Apply link updates ----
    for link_diff in diff.links_modified:
        uid = link_diff.uid
        changes: dict[str, Any] = {}
        for field_diff in link_diff.changed_fields:
            changes[field_diff.field] = field_diff.new

        if changes:
            graph.update_link(uid, **changes)
            report.applied_links.append(uid)

    return report
