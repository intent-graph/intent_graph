"""Tests for JSON/YAML round-trip serialization."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.models.node import HistoryEntry
from intentgraph.serial.json_yaml import (
    dict_to_graph,
    graph_to_dict,
    graph_to_json,
    graph_to_yaml,
    json_to_graph,
    load_graph,
    load_json,
    load_yaml,
    save_graph,
    save_json,
    save_yaml,
    yaml_to_graph,
)


class TestGraphToDict:

    def test_empty_graph(self, empty_graph: IntentGraph):
        d = graph_to_dict(empty_graph)
        assert d["nodes"] == []
        assert d["treearcs"] == []
        assert d["intentlinks"] == []

    def test_treearcs_explicit(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        tarcs = d["treearcs"]
        assert len(tarcs) == 2
        assert {"parent": "ROOT", "child": "A"} in tarcs
        assert {"parent": "ROOT", "child": "B"} in tarcs

    def test_nodes_and_treearcs_breadth_first(self, tiny_graph: IntentGraph, medium_graph: IntentGraph):
        """Serialized nodes and treearcs are in breadth-first order."""
        # tiny: ROOT, A, B
        d = graph_to_dict(tiny_graph)
        uids = [n["uid"] for n in d["nodes"]]
        assert uids == ["ROOT", "A", "B"]
        assert d["treearcs"] == [{"parent": "ROOT", "child": "A"}, {"parent": "ROOT", "child": "B"}]

        # medium: ROOT, E,T,L, then E.1..E.3, T.1..T.3, L.1..L.3, then L.3.1, L.3.2
        d = graph_to_dict(medium_graph)
        uids = [n["uid"] for n in d["nodes"]]
        assert uids[0] == "ROOT"
        assert set(uids[1:4]) == {"E", "T", "L"}
        assert uids[4:7] == ["E.1", "E.2", "E.3"]
        assert uids[7:10] == ["T.1", "T.2", "T.3"]
        assert uids[10:13] == ["L.1", "L.2", "L.3"]
        assert uids[13:15] == ["L.3.1", "L.3.2"]

    def test_nodes_exclude_structural_fields(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        for node_dict in d["nodes"]:
            assert "parent_uid" not in node_dict
            assert "children_uids" not in node_dict

    def test_links_serialized(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        assert len(d["intentlinks"]) == 1
        assert d["intentlinks"][0]["src"] == "A"
        assert d["intentlinks"][0]["dst"] == "B"


class TestDictRoundTrip:

    def test_tiny_round_trip(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        g2 = dict_to_graph(d)

        assert g2.node_count() == tiny_graph.node_count()
        assert g2.link_count() == tiny_graph.link_count()
        assert g2.parent("A").uid == "ROOT"
        assert g2.parent("B").uid == "ROOT"
        assert [c.uid for c in g2.children("ROOT")] == ["A", "B"]

    def test_medium_round_trip(self, medium_graph: IntentGraph):
        d = graph_to_dict(medium_graph)
        g2 = dict_to_graph(d)

        assert g2.node_count() == medium_graph.node_count()
        assert g2.link_count() == medium_graph.link_count()
        # Check deep structure
        assert g2.parent("L.3.1").uid == "L.3"
        assert set(c.uid for c in g2.children("L.3")) == {"L.3.1", "L.3.2"}

    def test_preserves_node_fields(self):
        g = IntentGraph()
        g.add_node(
            "ROOT", "Root", "Top level",
            epistemic_state="known",
            constraints=["Must be stable"],
            examples=["Example 1"],
            design_notes="Chose this because...",
            effort="high",
            history=[{"who": "remi", "date": "2026-02", "note": "Created"}],
        )

        d = graph_to_dict(g)
        g2 = dict_to_graph(d)
        node = g2.get_node("ROOT")
        assert node.epistemic_state == "known"
        assert node.constraints == ["Must be stable"]
        assert node.examples == ["Example 1"]
        assert node.design_notes == "Chose this because..."
        assert node.effort == "high"
        assert len(node.history) == 1
        assert node.history[0].who == "remi"

    def test_inter_intentlinks_round_trip(self):
        """Inter intentlinks serialize and deserialize; backward compat when key absent."""
        g = IntentGraph(meta={"name": "test"})
        g.add_node("ROOT", "Root", "Top")
        g.add_inter_link(
            "pig-py:PIG-PY-TYPES.1",
            "product:DISCOVER.1",
            "Renders product node DISCOVER.1",
            shape={"type": "renders"},
        )
        d = graph_to_dict(g)
        assert "inter_intentlinks" in d
        assert len(d["inter_intentlinks"]) == 1
        assert d["inter_intentlinks"][0]["src"] == "pig-py:PIG-PY-TYPES.1"
        assert d["inter_intentlinks"][0]["dst"] == "product:DISCOVER.1"
        g2 = dict_to_graph(d)
        assert g2.inter_link_count() == 1
        link = g2.get_inter_link("pig-py:PIG-PY-TYPES.1_product:DISCOVER.1")
        assert link.intent == "Renders product node DISCOVER.1"
        assert link.shape == {"type": "renders"}

    def test_dict_without_inter_intentlinks_loads(self):
        """Backward compat: dict without inter_intentlinks key yields empty inter_links."""
        g = IntentGraph(meta={})
        g.add_node("ROOT", "R", "Intent")
        d = graph_to_dict(g)
        d.pop("inter_intentlinks", None)
        g2 = dict_to_graph(d)
        assert g2.inter_link_count() == 0


class TestJsonRoundTrip:

    def test_json_string_round_trip(self, medium_graph: IntentGraph):
        text = graph_to_json(medium_graph)
        g2 = json_to_graph(text)
        assert g2.node_count() == medium_graph.node_count()
        assert g2.link_count() == medium_graph.link_count()

    def test_json_is_valid_json(self, tiny_graph: IntentGraph):
        text = graph_to_json(tiny_graph)
        parsed = json.loads(text)
        assert "nodes" in parsed
        assert "treearcs" in parsed

    def test_json_file_round_trip(self, medium_graph: IntentGraph):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_json(medium_graph, path)
            g2 = load_json(path)
            assert g2.node_count() == medium_graph.node_count()
        finally:
            Path(path).unlink(missing_ok=True)


class TestYamlRoundTrip:

    def test_yaml_string_round_trip(self, medium_graph: IntentGraph):
        text = graph_to_yaml(medium_graph)
        g2 = yaml_to_graph(text)
        assert g2.node_count() == medium_graph.node_count()
        assert g2.link_count() == medium_graph.link_count()

    def test_yaml_is_valid_yaml(self, tiny_graph: IntentGraph):
        text = graph_to_yaml(tiny_graph)
        parsed = yaml.safe_load(text)
        assert "nodes" in parsed
        assert "treearcs" in parsed

    def test_yaml_file_round_trip(self, medium_graph: IntentGraph):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            save_yaml(medium_graph, path)
            g2 = load_yaml(path)
            assert g2.node_count() == medium_graph.node_count()
        finally:
            Path(path).unlink(missing_ok=True)


class TestLoadSaveGraph:

    """Format-agnostic load_graph/save_graph dispatch by extension."""

    def test_load_save_graph_json_round_trip(self, medium_graph: IntentGraph, tmp_path: Path):
        path = tmp_path / "graph.json"
        save_graph(medium_graph, path)
        g2 = load_graph(path)
        assert g2.node_count() == medium_graph.node_count()
        assert g2.link_count() == medium_graph.link_count()

    def test_load_save_graph_yaml_round_trip(self, medium_graph: IntentGraph, tmp_path: Path):
        path = tmp_path / "graph.yaml"
        save_graph(medium_graph, path)
        g2 = load_graph(path)
        assert g2.node_count() == medium_graph.node_count()
        assert g2.link_count() == medium_graph.link_count()

    def test_load_save_graph_yml_round_trip(self, medium_graph: IntentGraph, tmp_path: Path):
        path = tmp_path / "graph.yml"
        save_graph(medium_graph, path)
        g2 = load_graph(path)
        assert g2.node_count() == medium_graph.node_count()
        assert g2.link_count() == medium_graph.link_count()

    def test_load_graph_invalid_extension_raises(self, medium_graph: IntentGraph, tmp_path: Path):
        path = tmp_path / "graph.txt"
        path.write_text("nodes: []\ntreearcs: []\nintentlinks: []")
        with pytest.raises(ValueError, match="extension .json, .yaml, or .yml"):
            load_graph(path)

    def test_save_graph_invalid_extension_raises(self, medium_graph: IntentGraph, tmp_path: Path):
        path = tmp_path / "graph.txt"
        with pytest.raises(ValueError, match="extension .json, .yaml, or .yml"):
            save_graph(medium_graph, path)
