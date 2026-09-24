"""Tests for I/O logging."""

import json
from pathlib import Path

from ig_agents.logger import AgentLogEntry, AgentLogger


class TestAgentLogEntry:

    def test_defaults(self):
        entry = AgentLogEntry(agent_role="extractor")
        assert entry.agent_role == "extractor"
        assert entry.success is True
        assert entry.edits_count == 0
        assert entry.timestamp  # auto-set

    def test_to_dict(self):
        entry = AgentLogEntry(agent_role="critic", issues_count=5)
        d = entry.to_dict()
        assert d["agent_role"] == "critic"
        assert d["issues_count"] == 5


class TestAgentLogger:

    def test_log_and_read(self, tmp_path: Path):
        logger = AgentLogger(tmp_path / "logs")
        entry = AgentLogEntry(
            agent_role="extractor",
            model="opus",
            input_text="frontier yaml here",
            output_text="edits yaml here",
            edits_count=3,
            duration_seconds=5.2,
        )
        path = logger.log(entry)
        assert path.exists()
        assert path.name == "extractor.jsonl"

        entries = logger.read_log("extractor")
        assert len(entries) == 1
        assert entries[0].edits_count == 3

    def test_multiple_entries(self, tmp_path: Path):
        logger = AgentLogger(tmp_path / "logs")
        for i in range(5):
            logger.log(AgentLogEntry(agent_role="critic", issues_count=i))

        entries = logger.read_log("critic")
        assert len(entries) == 5

    def test_stats(self, tmp_path: Path):
        logger = AgentLogger(tmp_path / "logs")
        logger.log(AgentLogEntry(agent_role="extractor", edits_count=3, duration_seconds=10.0))
        logger.log(AgentLogEntry(agent_role="extractor", edits_count=5, duration_seconds=20.0))
        logger.log(AgentLogEntry(agent_role="extractor", edits_count=2, duration_seconds=5.0, success=False))

        stats = logger.stats("extractor")
        assert stats["count"] == 3
        assert stats["total_edits"] == 10
        assert abs(stats["avg_duration"] - 11.667) < 0.1
        assert abs(stats["success_rate"] - 0.667) < 0.01

    def test_stats_empty(self, tmp_path: Path):
        logger = AgentLogger(tmp_path / "logs")
        stats = logger.stats("nonexistent")
        assert stats == {"count": 0}

    def test_track_context_manager(self, tmp_path: Path):
        logger = AgentLogger(tmp_path / "logs")
        with logger.track("elicitor", model="sonnet", graph_path="g.json") as entry:
            entry.input_text = "some frontier yaml"
            entry.output_text = "proposed edits"
            entry.edits_count = 2

        entries = logger.read_log("elicitor")
        assert len(entries) == 1
        assert entries[0].model == "sonnet"
        assert entries[0].edits_count == 2
        assert entries[0].duration_seconds >= 0  # may be 0.0 if context body runs very fast
        assert entries[0].input_words > 0
        assert entries[0].success is True

    def test_track_records_error(self, tmp_path: Path):
        logger = AgentLogger(tmp_path / "logs")
        try:
            with logger.track("generator") as entry:
                entry.input_text = "frontier"
                raise ValueError("generation failed")
        except ValueError:
            pass

        entries = logger.read_log("generator")
        assert len(entries) == 1
        assert entries[0].success is False
        assert "generation failed" in entries[0].error

    def test_separate_files_per_role(self, tmp_path: Path):
        logger = AgentLogger(tmp_path / "logs")
        logger.log(AgentLogEntry(agent_role="extractor"))
        logger.log(AgentLogEntry(agent_role="critic"))

        assert (tmp_path / "logs" / "extractor.jsonl").exists()
        assert (tmp_path / "logs" / "critic.jsonl").exists()
        assert len(logger.read_log("extractor")) == 1
        assert len(logger.read_log("critic")) == 1
