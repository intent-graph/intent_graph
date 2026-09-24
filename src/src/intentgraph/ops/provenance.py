"""Write-boundary provenance capture (formalism §4, "Provenance capture").

History is stamped automatically when a graph is saved, never opted into per
command: the saver diffs a baseline snapshot (taken at load) against the
current state and appends one commit-style HistoryEntry to every node whose
content changed — same message on every touched node, like one git commit
spanning several files.

Triviality filter: content fields and structural moves (create, reparent)
stamp; sibling reordering, lens configuration, and ``history`` itself never do.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from intentgraph.models.graph import IntentGraph
from intentgraph.models.node import HistoryEntry

#: Node fields whose change constitutes a non-trivial edit. ``history`` is
#: deliberately absent (no recursion); ``parent_uid`` covers reparenting.
_STAMPED_FIELDS = (
    "name",
    "intent",
    "epistemic_state",
    "constraints",
    "examples",
    "design_notes",
    "effort",
    "impl_pointers",
    "data_registry",
    "parent_uid",
)


def content_snapshot(graph: IntentGraph) -> dict[str, dict[str, Any]]:
    """Per-node signature of the provenance-relevant state.

    Values are deep-copied so in-place mutations of lists/dicts on the live
    node cannot silently alias the baseline and hide from the diff.
    """
    return {
        uid: {f: deepcopy(getattr(node, f)) for f in _STAMPED_FIELDS}
        for uid, node in graph.nodes.items()
    }


def _auto_note(changed: list[str], created: bool) -> str:
    if created:
        return "created"
    parts = [f for f in changed if f != "parent_uid"]
    note = f"updated: {', '.join(parts)}" if parts else ""
    if "parent_uid" in changed:
        note = f"{note}; reparented" if note else "reparented"
    return note


def stamp_provenance(
    graph: IntentGraph,
    baseline: dict[str, dict[str, Any]],
    *,
    who: str,
    note: str | None = None,
    now: str | None = None,
) -> list[str]:
    """Append a HistoryEntry to every node changed relative to ``baseline``.

    ``note`` overrides the auto-generated diff summary (same message on every
    stamped node). Returns the stamped uids. Deleted nodes leave no trace here
    — their absence from the saved file is the record.
    """
    date = now or datetime.now().isoformat(timespec="minutes")
    stamped: list[str] = []
    for uid, node in graph.nodes.items():
        before = baseline.get(uid)
        created = before is None
        changed = (
            []
            if created
            else [f for f in _STAMPED_FIELDS if getattr(node, f) != before[f]]
        )
        if not created and not changed:
            continue
        node.history.append(
            HistoryEntry(who=who, date=date, note=note or _auto_note(changed, created))
        )
        stamped.append(uid)
    return stamped
