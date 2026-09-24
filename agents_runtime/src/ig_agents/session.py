"""Session management — multi-turn state for agent conversations.

A session tracks the state of an agent interaction across multiple turns:
which graph is being worked on, which working view is active, what edits
have been proposed and accepted/rejected, and the conversation history.

Primarily used by the Elicitor (multi-turn dialogue) and the Extractor
(iterative refinement loops).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionTurn:
    """A single turn in an agent conversation."""
    turn_number: int
    timestamp: str
    agent_role: str
    input_summary: str
    output_summary: str
    edits_proposed: int = 0
    edits_accepted: int = 0
    edits_rejected: int = 0


@dataclass
class Session:
    """Persistent session state for multi-turn agent interactions.

    Tracks the graph, working view, conversation turns, and edit history.
    Serializable to JSON for persistence across invocations.
    """
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_role: str = ""
    graph_path: str = ""
    view_name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    status: str = "active"  # active, paused, completed
    turns: list[SessionTurn] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_turn(
        self,
        input_summary: str,
        output_summary: str,
        edits_proposed: int = 0,
        edits_accepted: int = 0,
        edits_rejected: int = 0,
    ) -> SessionTurn:
        """Record a new turn in the conversation."""
        turn = SessionTurn(
            turn_number=len(self.turns) + 1,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            agent_role=self.agent_role,
            input_summary=input_summary,
            output_summary=output_summary,
            edits_proposed=edits_proposed,
            edits_accepted=edits_accepted,
            edits_rejected=edits_rejected,
        )
        self.turns.append(turn)
        self.updated_at = turn.timestamp
        return turn

    def complete(self) -> None:
        self.status = "completed"
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def pause(self) -> None:
        self.status = "paused"
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def total_edits_proposed(self) -> int:
        return sum(t.edits_proposed for t in self.turns)

    @property
    def total_edits_accepted(self) -> int:
        return sum(t.edits_accepted for t in self.turns)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Session:
        turns_data = d.pop("turns", [])
        session = cls(**d)
        session.turns = [SessionTurn(**t) for t in turns_data]
        return session


# ================================================================== #
#  Session store — file-based persistence                              #
# ================================================================== #

DEFAULT_SESSION_DIR = ".ig_sessions"


class SessionStore:
    """File-based session persistence.

    Sessions are stored as individual JSON files in a directory.
    """

    def __init__(self, base_dir: str | Path = DEFAULT_SESSION_DIR) -> None:
        self.base_dir = Path(base_dir)

    def save(self, session: Session) -> Path:
        """Save a session to disk. Returns the file path."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"{session.session_id}.json"
        path.write_text(
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def load(self, session_id: str) -> Session:
        """Load a session by ID. Raises FileNotFoundError if not found."""
        path = self.base_dir / f"{session_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session.from_dict(data)

    def list_sessions(self) -> list[dict[str, str]]:
        """List all sessions with basic metadata."""
        if not self.base_dir.exists():
            return []
        sessions = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data.get("session_id", path.stem),
                    "agent_role": data.get("agent_role", ""),
                    "status": data.get("status", ""),
                    "turn_count": len(data.get("turns", [])),
                    "updated_at": data.get("updated_at", ""),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session. Returns True if deleted, False if not found."""
        path = self.base_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
