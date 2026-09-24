"""Regression test for CLI_FOLLOW_UP_PROMPT.md Fix 1: `apply --batch` data loss
on a failed/rolled-back batch when `-o` is the same path as `-g`.

`run_batch`'s except-block used to write the error report via `_write_output`
using `params.output_path` — if the caller passed the same path for `-g` and
`-o` (a legitimate in-place-update pattern), the failing run overwrote the
source graph file with the error report, destroying it. The fix always routes
the error report to stdout and leaves `output_path` untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml

from ig_agents.cli import cmd_apply
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import save_graph


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
    role: str | None = None,
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


class TestFailedBatchDoesNotOverwriteSourceGraph:
    def test_same_path_for_g_and_o_left_untouched_on_failure(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        original_content = graph_path.read_text(encoding="utf-8")

        batch_path = tmp_path / "batch.yaml"
        batch_path.write_text(yaml.dump({
            "operations": [
                {"op": "node.set", "uid": "DOES_NOT_EXIST", "intent": "x"},
            ],
        }))

        with pytest.raises(SystemExit):
            cmd_apply(_apply_args(graph_path, batch_path, graph_path))

        assert graph_path.read_text(encoding="utf-8") == original_content, (
            "failed batch must not overwrite the source graph file"
        )

    def test_distinct_output_path_also_left_untouched_on_failure(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "updated.json"

        batch_path = tmp_path / "batch.yaml"
        batch_path.write_text(yaml.dump({
            "operations": [
                {"op": "node.set", "uid": "DOES_NOT_EXIST", "intent": "x"},
            ],
        }))

        with pytest.raises(SystemExit):
            cmd_apply(_apply_args(graph_path, batch_path, out_path))

        assert not out_path.exists(), (
            "failed batch must not write anything to the output path"
        )
