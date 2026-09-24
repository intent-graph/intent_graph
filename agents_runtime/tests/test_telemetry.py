"""Tests for the CLI telemetry layer (~/.cache/ig-tool/usage.jsonl).

Telemetry must:
  - Default ON: write a record on every invocation
  - Honor `--no-telemetry`: skip the write
  - Honor `IG_TOOL_NO_TELEMETRY=1` env var: skip the write
  - Never crash the CLI (broad except in write_record)
  - Sanitize paths to basenames / `~`-prefixed
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ig_agents import telemetry


@pytest.fixture
def tmp_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect telemetry writes to a temp dir for the duration of the test."""
    log_dir = tmp_path / "ig-tool"
    log_path = log_dir / "usage.jsonl"
    monkeypatch.setattr(telemetry, "LOG_DIR", log_dir)
    monkeypatch.setattr(telemetry, "LOG_PATH", log_path)
    monkeypatch.delenv(telemetry._DISABLE_ENV, raising=False)
    return log_path


class TestWriteRecord:

    def test_creates_log_dir(self, tmp_log: Path):
        telemetry.write_record(
            command="validate",
            action=None,
            exit_code=0,
            duration_ms=42,
            argv=["validate", "-g", "graph.json"],
        )
        assert tmp_log.exists()

    def test_record_has_expected_fields(self, tmp_log: Path):
        telemetry.write_record(
            command="apply",
            action=None,
            exit_code=1,
            duration_ms=120,
            argv=["apply", "-i", "edits.yaml"],
        )
        records = telemetry.read_records()
        assert len(records) == 1
        r = records[0]
        assert r["command"] == "apply"
        assert r["exit_code"] == 1
        assert r["duration_ms"] == 120
        assert "ts" in r
        assert r["argv"] == ["apply", "-i", "edits.yaml"]

    def test_appends_not_overwrites(self, tmp_log: Path):
        for i in range(3):
            telemetry.write_record(
                command=f"cmd{i}",
                action=None,
                exit_code=0,
                duration_ms=10,
                argv=[f"cmd{i}"],
            )
        records = telemetry.read_records()
        assert len(records) == 3
        assert [r["command"] for r in records] == ["cmd0", "cmd1", "cmd2"]


class TestSanitizeArgv:

    def test_absolute_paths_become_basenames(self):
        result = telemetry._sanitize_argv(
            ["validate", "-g", "/abs/path/to/graph.json"]
        )
        assert result == ["validate", "-g", "graph.json"]

    def test_home_paths_become_tilde_prefixed(self):
        home = str(Path.home())
        result = telemetry._sanitize_argv(["-o", f"{home}/file.json"])
        assert result == ["-o", "~/file.json"]

    def test_relative_paths_unchanged(self):
        result = telemetry._sanitize_argv(["query", "-g", "graph.json", "--node", "X"])
        assert result == ["query", "-g", "graph.json", "--node", "X"]


class TestEnvDisable:

    def test_disabled_env_var_returns_true(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(telemetry._DISABLE_ENV, "1")
        assert telemetry.disabled_via_env() is True

    def test_unset_env_returns_false(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv(telemetry._DISABLE_ENV, raising=False)
        assert telemetry.disabled_via_env() is False

    def test_lowercase_truthy_values(self, monkeypatch: pytest.MonkeyPatch):
        for val in ["true", "yes", "on", "1"]:
            monkeypatch.setenv(telemetry._DISABLE_ENV, val)
            assert telemetry.disabled_via_env() is True


class TestReadRecords:

    def test_skips_malformed_lines(self, tmp_log: Path):
        tmp_log.parent.mkdir(parents=True, exist_ok=True)
        tmp_log.write_text(
            '{"command": "ok"}\n'
            "this is not json\n"
            '{"command": "also_ok"}\n'
        )
        records = telemetry.read_records()
        assert len(records) == 2
        assert records[0]["command"] == "ok"
        assert records[1]["command"] == "also_ok"

    def test_limit_returns_last_n(self, tmp_log: Path):
        for i in range(5):
            telemetry.write_record(
                command=f"cmd{i}",
                action=None,
                exit_code=0,
                duration_ms=1,
                argv=[],
            )
        records = telemetry.read_records(limit=2)
        assert len(records) == 2
        assert records[0]["command"] == "cmd3"
        assert records[1]["command"] == "cmd4"


class TestWriteSwallowsErrors:
    """Telemetry must never crash the CLI, even if the disk is full or perms
    are wrong."""

    def test_does_not_raise_on_filesystem_error(self, monkeypatch: pytest.MonkeyPatch):
        # Point LOG_PATH at something `mkdir` will fail on
        bad_path = Path("/proc/cannot-write-here/usage.jsonl")
        monkeypatch.setattr(telemetry, "LOG_DIR", bad_path.parent)
        monkeypatch.setattr(telemetry, "LOG_PATH", bad_path)
        # Should silently swallow, not raise
        telemetry.write_record(
            command="test",
            action=None,
            exit_code=0,
            duration_ms=1,
            argv=[],
        )
