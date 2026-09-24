"""Regression tests for Bug 1: `apply --batch` ignoring
`--role` so history was never stamped.

Two independent layers, both covered here:

1. `cmd_apply` used to hand-build a synthetic `argparse.Namespace` for
   `cmd_batch` that omitted the `role` field entirely, silently dropping
   `--role` before batch execution even ran.
2. `cmd_batch` executed `node.create` / `node.set` via direct
   `graph.add_node()` / `graph.update_node()` calls, bypassing
   `apply_edits()` — the only code path that stamped `HistoryEntry`
   provenance. Even with the flag threaded through, nothing consumed it.

These tests call `cmd_apply` (the real dispatch entrypoint used by the
`apply --batch` CLI surface) directly with a built `argparse.Namespace`,
matching the pattern in test_cli_tree.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from ig_agents.cli import cmd_apply
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import load_graph, save_graph


def _build_graph(tmp_path: Path) -> Path:
    g = IntentGraph(meta={"name": "test"})
    g.add_node("ROOT", "Root", "root intent")
    g.add_node_under("A", "A", "A intent", parent_uid="ROOT")

    path = tmp_path / "graph.json"
    save_graph(g, path)
    return path


def _apply_args(
    graph_path: Path,
    batch_path: Path,
    output_path: Path,
    role: str | None,
) -> argparse.Namespace:
    return argparse.Namespace(
        command="apply",
        graph=str(graph_path),
        input=None,
        batch=str(batch_path),
        output=str(output_path),
        role=role,
        dry_run=False,
    )


class TestApplyBatchRoleStampsHistoryOnCreate:
    """node.create via `apply --batch --role <role>` must stamp history."""

    def test_history_entry_stamped(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        batch_path = tmp_path / "batch.yaml"
        batch_path.write_text(yaml.dump({
            "operations": [
                {
                    "op": "node.create",
                    "uid": "B",
                    "name": "B",
                    "intent": "B intent",
                    "parent": "ROOT",
                },
            ],
        }))
        out_path = tmp_path / "updated.json"

        cmd_apply(_apply_args(graph_path, batch_path, out_path, role="steward"))

        updated = load_graph(str(out_path))
        node = updated.get_node("B")
        assert node.history, "expected a history entry to be stamped"
        assert any(h.who == "agent:steward" for h in node.history), (
            f"expected who='agent:steward' in history, got: {node.history}"
        )

    def test_no_role_means_no_history(self, tmp_path: Path):
        """Without --role, provenance is still captured at the write boundary,
        attributed to the resolved human actor (never an agent:* who)."""
        graph_path = _build_graph(tmp_path)
        batch_path = tmp_path / "batch.yaml"
        batch_path.write_text(yaml.dump({
            "operations": [
                {
                    "op": "node.create",
                    "uid": "C",
                    "name": "C",
                    "intent": "C intent",
                    "parent": "ROOT",
                },
            ],
        }))
        out_path = tmp_path / "updated_norole.json"

        cmd_apply(_apply_args(graph_path, batch_path, out_path, role=None))

        updated = load_graph(str(out_path))
        node = updated.get_node("C")
        assert node.history, "write-boundary provenance must stamp every save"
        assert all(not h.who.startswith("agent:") for h in node.history), (
            f"no --role means a human actor, got: {node.history}"
        )


class TestApplyBatchRoleStampsHistoryOnUpdate:
    """node.set via `apply --batch --role <role>` must stamp history."""

    def test_history_entry_stamped(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        batch_path = tmp_path / "batch.yaml"
        batch_path.write_text(yaml.dump({
            "operations": [
                {
                    "op": "node.set",
                    "uid": "A",
                    "intent": "Updated A intent",
                },
            ],
        }))
        out_path = tmp_path / "updated.json"

        cmd_apply(_apply_args(graph_path, batch_path, out_path, role="extractor"))

        updated = load_graph(str(out_path))
        node = updated.get_node("A")
        assert node.history, "expected a history entry to be stamped"
        assert any(h.who == "agent:extractor" for h in node.history), (
            f"expected who='agent:extractor' in history, got: {node.history}"
        )
        assert node.intent == "Updated A intent"
