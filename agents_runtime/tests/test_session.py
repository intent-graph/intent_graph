"""Tests for session management."""

import pytest
from pathlib import Path

from ig_agents.session import Session, SessionStore, SessionTurn


class TestSession:

    def test_create_session(self):
        s = Session(agent_role="elicitor", graph_path="g.json", view_name="auth")
        assert s.agent_role == "elicitor"
        assert s.status == "active"
        assert s.turn_count == 0
        assert len(s.session_id) == 12

    def test_add_turn(self):
        s = Session(agent_role="elicitor")
        turn = s.add_turn(
            input_summary="Asked about auth",
            output_summary="Proposed children",
            edits_proposed=3,
            edits_accepted=2,
            edits_rejected=1,
        )
        assert s.turn_count == 1
        assert turn.turn_number == 1
        assert turn.agent_role == "elicitor"
        assert turn.edits_proposed == 3

    def test_multiple_turns(self):
        s = Session(agent_role="extractor")
        s.add_turn("input1", "output1", edits_proposed=5)
        s.add_turn("input2", "output2", edits_proposed=3, edits_accepted=3)
        assert s.turn_count == 2
        assert s.total_edits_proposed == 8
        assert s.total_edits_accepted == 3

    def test_complete_and_pause(self):
        s = Session(agent_role="elicitor")
        s.pause()
        assert s.status == "paused"
        s.complete()
        assert s.status == "completed"

    def test_round_trip_serialization(self):
        s = Session(agent_role="critic", graph_path="g.json")
        s.add_turn("review graph", "found 5 issues", edits_proposed=5)
        d = s.to_dict()
        s2 = Session.from_dict(d)
        assert s2.session_id == s.session_id
        assert s2.agent_role == "critic"
        assert s2.turn_count == 1
        assert s2.turns[0].turn_number == 1


class TestSessionStore:

    def test_save_and_load(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions")
        s = Session(agent_role="elicitor", graph_path="test.json")
        s.add_turn("hello", "proposed edit", edits_proposed=1)

        path = store.save(s)
        assert path.exists()

        loaded = store.load(s.session_id)
        assert loaded.session_id == s.session_id
        assert loaded.turn_count == 1

    def test_list_sessions(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions")
        s1 = Session(agent_role="elicitor")
        s2 = Session(agent_role="extractor")
        store.save(s1)
        store.save(s2)

        listing = store.list_sessions()
        assert len(listing) == 2
        roles = {s["agent_role"] for s in listing}
        assert roles == {"elicitor", "extractor"}

    def test_delete_session(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions")
        s = Session(agent_role="elicitor")
        store.save(s)
        assert store.delete(s.session_id) is True
        assert store.delete(s.session_id) is False  # already gone

    def test_load_nonexistent(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions")
        with pytest.raises(FileNotFoundError):
            store.load("nonexistent")

    def test_list_empty_dir(self, tmp_path: Path):
        store = SessionStore(tmp_path / "no_sessions")
        assert store.list_sessions() == []
