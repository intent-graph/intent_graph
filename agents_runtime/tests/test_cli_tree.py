"""Integration tests for `ig-tool tree`.

Regression guard for Bug 3: `tree -o` wrote the output file correctly, then
crashed on a `'words'` KeyError while generating the summary, because `cmd_tree`
hand-built an incomplete `size` dict (`{"lines": ..., "chars": ...}`, no
`"words"` key) instead of reusing `_write_output`'s measuring logic.

These tests call ``cmd_tree`` directly with a built ``argparse.Namespace``
to avoid subprocess overhead while still exercising the full CLI dispatch
path (render -> write -> summary).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ig_agents.cli import cmd_tree
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import save_graph


def _build_graph(tmp_path: Path) -> Path:
    g = IntentGraph(meta={"name": "test"})
    g.add_node("ROOT", "Root", "root intent")
    g.add_node_under("A", "A", "A intent", parent_uid="ROOT")
    g.add_node_under("B", "B", "B intent", parent_uid="ROOT")

    path = tmp_path / "graph.json"
    save_graph(g, path)
    return path


def _tree_args(graph_path: Path, output: str | None) -> argparse.Namespace:
    return argparse.Namespace(
        command="tree",
        graph=str(graph_path),
        output=output,
        root=None,
        show_intent=False,
        style="simple",
        width=None,
        indent=None,
    )


class TestTreeWithOutputPath:

    def test_does_not_crash(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "tree.txt"
        # Historically this wrote the file then raised KeyError('words')
        # while building the summary. Must complete cleanly.
        cmd_tree(_tree_args(graph_path, str(out_path)))

    def test_writes_file(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "tree.txt"
        cmd_tree(_tree_args(graph_path, str(out_path)))
        assert out_path.exists()
        assert "Root" in out_path.read_text()

    def test_summary_contains_words_key(self, tmp_path: Path, capsys):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "tree.txt"
        cmd_tree(_tree_args(graph_path, str(out_path)))
        captured = capsys.readouterr()
        assert "words" in captured.out
        assert "output_size" in captured.out


class TestTreeToStdout:

    def test_does_not_crash_without_output(self, tmp_path: Path, capsys):
        graph_path = _build_graph(tmp_path)
        cmd_tree(_tree_args(graph_path, None))
        captured = capsys.readouterr()
        assert "Root" in captured.out
        # No -o path: summary must not include output/output_size block.
        assert "output_size" not in captured.out
