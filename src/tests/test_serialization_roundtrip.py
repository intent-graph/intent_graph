"""Regression tests for serialization round-trips and legacy `frontiers:` data.

The display-frontier concept is removed. A legacy graph file may still carry
a top-level ``frontiers:`` key: loading must tolerate it (ignore, never
store) and saving must never re-emit it. Private (``_``-prefixed) meta keys
must never leak into serialized output.
"""

from __future__ import annotations

import json

import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import (
    dict_to_graph,
    graph_to_dict,
    graph_to_json,
    graph_to_yaml,
    json_to_graph,
    yaml_to_graph,
)


class TestNoPrivateKeyLeak:

    def test_clean_meta_excludes_underscore_keys(self, medium_graph: IntentGraph):
        medium_graph.meta["_runtime_cache"] = object()
        d = graph_to_dict(medium_graph)
        for key in d["meta"]:
            assert not key.startswith("_"), (
                f"Private meta key '{key}' leaked into serialized form"
            )

    def test_clean_meta_keeps_public_keys(self, medium_graph: IntentGraph):
        medium_graph.meta["public_key"] = "kept"
        medium_graph.meta["_private_key"] = "dropped"
        d = graph_to_dict(medium_graph)
        assert d["meta"]["name"] == "medium_etl"
        assert d["meta"]["public_key"] == "kept"


class TestLegacyFrontiersKey:
    """A legacy `frontiers:` key loads fine, is ignored, and is never re-emitted."""

    def test_load_ignores_legacy_frontiers_key(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        d["frontiers"] = [{"name": "legacy", "nodes": ["A", "B"]}]
        graph = dict_to_graph(d)
        # Graph loads intact; nothing frontier-related is stored anywhere.
        assert len(list(graph.iter_nodes())) == 3
        assert "_frontiers" not in graph.meta
        assert "_raw_frontiers" not in graph.meta

    def test_legacy_frontiers_not_reemitted(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        d["frontiers"] = [{"name": "legacy", "nodes": ["A", "B"]}]
        graph = dict_to_graph(d)
        out = graph_to_dict(graph)
        assert "frontiers" not in out

    def test_serialized_form_has_no_frontiers_key(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        assert "frontiers" not in d

    def test_json_load_with_legacy_frontiers(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        d["frontiers"] = [{"name": "legacy", "nodes": ["A"]}]
        graph = json_to_graph(json.dumps(d))
        assert len(list(graph.iter_nodes())) == 3
        assert "frontiers" not in json.loads(graph_to_json(graph))

    def test_yaml_load_with_legacy_frontiers(self, tiny_graph: IntentGraph):
        d = graph_to_dict(tiny_graph)
        d["frontiers"] = [{"name": "legacy", "nodes": ["A"]}]
        graph = yaml_to_graph(yaml.dump(d))
        assert len(list(graph.iter_nodes())) == 3
        assert "frontiers" not in yaml.safe_load(graph_to_yaml(graph))


class TestYamlSerialization:

    def test_yaml_safe_load_succeeds(self, tiny_graph: IntentGraph):
        """Output must NOT contain `!!python/object/new:...` tags."""
        tiny_graph.meta["_runtime_cache"] = object()
        text = graph_to_yaml(tiny_graph)
        assert "!!python" not in text, (
            "YAML output contains Python-typed tags (unsafe-load only)"
        )
        # safe_load is the real assertion — it would crash on python tags
        d = yaml.safe_load(text)
        assert "_runtime_cache" not in d["meta"]


class TestRoundTrip:

    def test_json_yaml_json_roundtrip(self, medium_graph: IntentGraph):
        as_json = graph_to_json(medium_graph)
        graph2 = json_to_graph(as_json)
        as_yaml = graph_to_yaml(graph2)
        graph3 = yaml_to_graph(as_yaml)
        assert graph3.iter_nodes_bfs().__class__  # graph reloads
        # Node and link counts preserved
        assert len(list(graph3.iter_nodes())) == len(list(medium_graph.iter_nodes()))
        assert len(list(graph3.iter_links())) == len(list(medium_graph.iter_links()))

    def test_yaml_json_yaml_roundtrip(self, medium_graph: IntentGraph):
        as_yaml = graph_to_yaml(medium_graph)
        graph2 = yaml_to_graph(as_yaml)
        as_json = graph_to_json(graph2)
        graph3 = json_to_graph(as_json)
        assert len(list(graph3.iter_nodes())) == len(list(medium_graph.iter_nodes()))
        assert len(list(graph3.iter_links())) == len(list(medium_graph.iter_links()))

    def test_json_yaml_roundtrip_baseline(self, tiny_graph: IntentGraph):
        as_json = graph_to_json(tiny_graph)
        graph2 = json_to_graph(as_json)
        as_yaml = graph_to_yaml(graph2)
        graph3 = yaml_to_graph(as_yaml)
        assert len(list(graph3.iter_nodes())) == 3
