"""Workflow trace — high-level orchestration log.

Records one entry per workflow step transition, showing which step ran,
on which target, by which actor, what happened, and what the outcome was.

This is the **orchestration layer** — separate from ``AgentLogger`` which
captures detailed agent I/O. The trace gives a bird's-eye view of how
a session followed the workflow.

Persistence: JSONL file alongside the workflow state file.
Convention: ``{graph_name}_trace.jsonl``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TraceEntry:
    """A single workflow step execution record."""

    ts: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    step: str = ""  # Step UID, e.g. "DISTILL.EXTRACT" or "DECLARE.REFINE"
    target: str = ""  # Target intentnode UID, e.g. "AUTH"
    actor: str = ""  # Who performed it: orchestrator, navigator, critic, ...
    action: str = ""  # What happened (1-line summary)
    result: str = ""  # What was the outcome (1-line summary)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> TraceEntry:
        return cls(**d)


class WorkflowTrace:
    """Append-only JSONL trace for workflow step transitions.

    Usage::

        trace = WorkflowTrace(Path("example_graph_trace.jsonl"))
        trace.record("DISTILL.PICK", "AUTH", "steward",
                      "recommended AUTH (data-flow: ROOT→AUTH link)",
                      "human confirmed, proceed to DISTILL.SCOPE")
        print(trace.render())
    """

    def __init__(self, trace_path: str | Path) -> None:
        self.trace_path = Path(trace_path)

    def record(
        self,
        step: str,
        target: str,
        actor: str,
        action: str,
        result: str,
    ) -> TraceEntry:
        """Record a workflow step and append to the trace file."""
        entry = TraceEntry(
            step=step,
            target=target,
            actor=actor,
            action=action,
            result=result,
        )
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return entry

    def read(self) -> list[TraceEntry]:
        """Read all trace entries from the file."""
        if not self.trace_path.exists():
            return []
        entries: list[TraceEntry] = []
        for line in self.trace_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(TraceEntry.from_dict(json.loads(line)))
        return entries

    def render(self, *, workflow_name: str = "", graph_name: str = "") -> str:
        """Render the trace as a human-readable timeline.

        Returns a formatted string like::

            === Workflow Trace: example_graph (Distill) ===

            DISTILL.PICK      AUTH    steward       recommended AUTH (data-flow order)
            DISTILL.SCOPE     AUTH    navigator     built target-adj lens
            ...
        """
        entries = self.read()
        if not entries:
            return "(empty trace)\n"

        lines: list[str] = []

        # Header
        header_parts = ["=== Workflow Trace"]
        if graph_name:
            header_parts.append(f": {graph_name}")
        if workflow_name:
            header_parts.append(f" ({workflow_name})")
        header_parts.append(" ===")
        lines.append("".join(header_parts))
        lines.append("")

        # Find column widths for alignment
        max_step = max(len(e.step) for e in entries)
        max_target = max(len(e.target) for e in entries)
        max_actor = max(len(e.actor) for e in entries)

        for entry in entries:
            lines.append(
                f"{entry.step:<{max_step}}  "
                f"{entry.target:<{max_target}}  "
                f"{entry.actor:<{max_actor}}  "
                f"{entry.action}"
            )

        lines.append("")
        return "\n".join(lines)

    def clear(self) -> None:
        """Delete the trace file. Use with caution."""
        if self.trace_path.exists():
            self.trace_path.unlink()
