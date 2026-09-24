"""Integration tests for `ig-tool convert`.

Legacy-read coverage: a graph file that still contains a top-level
``frontiers:`` key (removed display-frontier concept) must convert cleanly —
the key is ignored on load and never re-emitted, and no Python-tagged YAML
ever leaks into the output.

These tests call ``cmd_convert`` directly with a built ``argparse.Namespace``
to avoid subprocess overhead while still exercising the full CLI dispatch path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from ig_agents.cli import cmd_convert
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import graph_to_dict


def _build_graph_file_with_legacy_frontiers(tmp_path: Path, fmt: str) -> Path:
    """Persist a graph file that carries a legacy top-level `frontiers:` key."""
    g = IntentGraph(meta={"name": "test"})
    g.add_node("ROOT", "Root", "root intent")
    g.add_node_under("A", "A", "A intent", parent_uid="ROOT")
    g.add_node_under("B", "B", "B intent", parent_uid="ROOT")
    g.add_link("A", "B", "A feeds B")

    d = graph_to_dict(g)
    d["frontiers"] = [{"uid": "f1", "name": "test", "node_uids": ["A", "B"]}]

    path = tmp_path / f"graph.{fmt}"
    if fmt == "json":
        path.write_text(json.dumps(d, indent=2), encoding="utf-8")
    else:
        path.write_text(yaml.dump(d, sort_keys=False), encoding="utf-8")
    return path


def _convert(input_path: Path, output_path: Path, fmt: str | None = None) -> None:
    args = argparse.Namespace(
        command="convert",
        input=str(input_path),
        output=str(output_path),
        format=fmt,
    )
    cmd_convert(args)


class TestConvertYamlToJson:

    def test_converts_without_crash(self, tmp_path: Path):
        src = _build_graph_file_with_legacy_frontiers(tmp_path, "yaml")
        dst = tmp_path / "out.json"
        _convert(src, dst)
        assert dst.exists()

    def test_output_loads_as_json_and_drops_frontiers(self, tmp_path: Path):
        src = _build_graph_file_with_legacy_frontiers(tmp_path, "yaml")
        dst = tmp_path / "out.json"
        _convert(src, dst)
        with dst.open() as fh:
            data = json.load(fh)
        assert "frontiers" not in data
        assert "_frontiers" not in data["meta"]
        assert "_raw_frontiers" not in data["meta"]
        assert len(data["nodes"]) == 3


class TestConvertJsonToYaml:

    def test_yaml_safe_load_succeeds(self, tmp_path: Path):
        src = _build_graph_file_with_legacy_frontiers(tmp_path, "json")
        dst = tmp_path / "out.yaml"
        _convert(src, dst)
        text = dst.read_text()
        assert "!!python" not in text, (
            "YAML output contains Python-typed tags (would fail safe_load)"
        )
        data = yaml.safe_load(text)
        assert "frontiers" not in data
        assert "_frontiers" not in data["meta"]
        assert len(data["nodes"]) == 3


class TestRoundTrip:

    def test_yaml_to_json_to_yaml(self, tmp_path: Path):
        src = _build_graph_file_with_legacy_frontiers(tmp_path, "yaml")
        intermediate = tmp_path / "step.json"
        final = tmp_path / "final.yaml"
        _convert(src, intermediate)
        _convert(intermediate, final)
        data = yaml.safe_load(final.read_text())
        assert len(data["nodes"]) == 3
        assert "frontiers" not in data
