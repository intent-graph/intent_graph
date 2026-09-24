"""I/O logging — record every agent invocation as potential training data.

Every agent session is logged as a JSONL entry containing:
- Timestamp, agent role, model used
- Input (view text, code paths, task description)
- Output (edits, issues, code files, etc.)
- Metrics (duration, edit count, etc.)

These logs are the primary source of training data for Phase 5
(custom agent training). Log everything.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Generator


DEFAULT_LOG_DIR = ".ig_logs"


@dataclass
class AgentLogEntry:
    """A single agent invocation record."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    agent_role: str = ""
    model: str = ""
    session_id: str | None = None

    # Input
    graph_path: str = ""
    view_name: str = ""
    input_text: str = ""
    task_description: str = ""

    # Output
    output_text: str = ""
    edits_count: int = 0
    issues_count: int = 0
    files_produced: list[str] = field(default_factory=list)

    # Metrics
    duration_seconds: float = 0.0
    input_words: int = 0
    output_words: int = 0
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentLogger:
    """Append-only JSONL logger for agent invocations.

    Each agent role gets its own log file: ``{log_dir}/{role}.jsonl``.
    """

    def __init__(self, log_dir: str | Path = DEFAULT_LOG_DIR) -> None:
        self.log_dir = Path(log_dir)

    def log(self, entry: AgentLogEntry) -> Path:
        """Append a log entry. Returns the log file path."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        role = entry.agent_role or "unknown"
        path = self.log_dir / f"{role}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return path

    def read_log(self, agent_role: str) -> list[AgentLogEntry]:
        """Read all entries for a given agent role."""
        path = self.log_dir / f"{agent_role}.jsonl"
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                data = json.loads(line)
                entries.append(AgentLogEntry(**data))
        return entries

    def stats(self, agent_role: str) -> dict[str, Any]:
        """Compute basic stats for an agent role's log."""
        entries = self.read_log(agent_role)
        if not entries:
            return {"count": 0}

        return {
            "count": len(entries),
            "total_edits": sum(e.edits_count for e in entries),
            "total_issues": sum(e.issues_count for e in entries),
            "avg_duration": sum(e.duration_seconds for e in entries) / len(entries),
            "success_rate": sum(1 for e in entries if e.success) / len(entries),
            "total_files": sum(len(e.files_produced) for e in entries),
        }

    @contextmanager
    def track(
        self,
        agent_role: str,
        *,
        model: str = "",
        session_id: str | None = None,
        graph_path: str = "",
        view_name: str = "",
        task_description: str = "",
    ) -> Generator[AgentLogEntry, None, None]:
        """Context manager that automatically times and logs an agent invocation.

        Usage::

            with logger.track("extractor", model="opus", graph_path="g.json") as entry:
                entry.input_text = view_text
                # ... run the agent ...
                entry.output_text = result
                entry.edits_count = len(edits)

        The entry is automatically logged on exit (even on error).
        """
        entry = AgentLogEntry(
            agent_role=agent_role,
            model=model,
            session_id=session_id,
            graph_path=graph_path,
            view_name=view_name,
            task_description=task_description,
        )
        start = time.monotonic()
        try:
            yield entry
        except Exception as exc:
            entry.success = False
            entry.error = str(exc)
            raise
        finally:
            entry.duration_seconds = round(time.monotonic() - start, 3)
            if entry.input_text:
                entry.input_words = len(entry.input_text.split())
            if entry.output_text:
                entry.output_words = len(entry.output_text.split())
            self.log(entry)
