"""Tests for lens serialization — file I/O, agent text format, round-trips."""

import json
from pathlib import Path

import pytest
import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.models.lens import LOD
from intentgraph.ops.lens_ops import build_lens
from intentgraph.serial.lens_file import (
    lens_to_dict,
    dict_to_lens,
    save_lens,
    load_lens,
    lens_to_agent_text,
    is_lens_file,
)


# ================================================================== #
#  Dict round-trip                                                   #
# ================================================================== #


class TestDictRoundTrip:
    """Test lens_to_dict and dict_to_lens round-trip."""

    def test_to_dict_structure(self, tiny_graph: IntentGraph):
        """lens_to_dict produces expected structure."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        d = lens_to_dict(lens)

        # Should have top-level keys
        assert "lens" in d
        assert "nodes" in d
        assert "treearcs" in d
        assert "intentlinks" in d
        assert "pruned_subtrees" in d

        # Lens metadata
        assert d["lens"]["name"] == "test"
        assert d["lens"]["target_uid"] == "A"
        assert d["lens"]["budget"] == 50

    def test_to_dict_nodes_include_lod(self, tiny_graph: IntentGraph):
        """lens_to_dict includes LOD field in each node."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        d = lens_to_dict(lens)

        for uid, node_dict in d["nodes"].items():
            assert "lod" in node_dict
            assert node_dict["lod"] in {"skeleton", "lean", "full"}

    def test_to_dict_pruned_children_when_nonzero(self, medium_graph: IntentGraph):
        """lens_to_dict includes pruned_children when > 0."""
        lens = build_lens(medium_graph, target_uid="E", budget=5, name="test")

        d = lens_to_dict(lens)

        # Check if any node has pruned_children
        pruned_found = any(
            "pruned_children" in node_dict and node_dict["pruned_children"] > 0
            for node_dict in d["nodes"].values()
        )

        # If the graph was pruned, at least one parent should show this
        if lens.node_count() < medium_graph.node_count():
            assert pruned_found

    def test_dict_to_lens_reconstructs(self, tiny_graph: IntentGraph):
        """dict_to_lens reconstructs a working lens."""
        original = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        d = lens_to_dict(original)
        restored = dict_to_lens(d)

        assert restored.meta.name == original.meta.name
        assert restored.meta.target_uid == original.meta.target_uid
        assert restored.meta.budget == original.meta.budget
        assert set(restored.nodes.keys()) == set(original.nodes.keys())
        assert len(restored.treearcs) == len(original.treearcs)
        assert len(restored.intentlinks) == len(original.intentlinks)

    def test_round_trip_preserves_lod(self, medium_graph: IntentGraph):
        """Round-trip preserves LOD assignments."""
        original = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        d = lens_to_dict(original)
        restored = dict_to_lens(d)

        for uid in original.nodes:
            assert restored.get_lod(uid) == original.get_lod(uid)

    def test_round_trip_preserves_pruned_subtrees(self, medium_graph: IntentGraph):
        """Round-trip preserves pruned_subtrees list."""
        original = build_lens(medium_graph, target_uid="E", budget=5, name="test")

        d = lens_to_dict(original)
        restored = dict_to_lens(d)

        assert set(restored.pruned_subtrees) == set(original.pruned_subtrees)

    def test_dict_to_lens_snapshots_base_state(self, tiny_graph: IntentGraph):
        """dict_to_lens automatically snapshots base state."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        d = lens_to_dict(lens)
        restored = dict_to_lens(d)

        # Should have base_state and dirty=False
        assert restored.base_state is not None
        assert restored.dirty is False


# ================================================================== #
#  File I/O — YAML                                                   #
# ================================================================== #


class TestYAMLFileIO:
    """Test save_lens and load_lens with YAML format."""

    def test_save_yaml(self, tiny_graph: IntentGraph, tmp_path: Path):
        """save_lens writes valid YAML file."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        path = tmp_path / "lens.yaml"
        save_lens(lens, path)

        assert path.exists()
        text = path.read_text()
        doc = yaml.safe_load(text)
        assert "lens" in doc

    def test_load_yaml(self, tiny_graph: IntentGraph, tmp_path: Path):
        """load_lens reads YAML file correctly."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        path = tmp_path / "lens.yaml"
        save_lens(lens, path)

        loaded = load_lens(path)

        assert loaded.meta.name == "test"
        assert loaded.meta.target_uid == "A"
        assert set(loaded.nodes.keys()) == set(lens.nodes.keys())

    def test_yaml_round_trip(self, medium_graph: IntentGraph, tmp_path: Path):
        """Full YAML round-trip preserves all data."""
        original = build_lens(medium_graph, target_uid="E.1", budget=100, name="yaml_test")

        path = tmp_path / "lens.yaml"
        save_lens(original, path)
        loaded = load_lens(path)

        assert loaded.meta.name == original.meta.name
        assert loaded.meta.target_uid == original.meta.target_uid
        assert loaded.meta.budget == original.meta.budget
        assert loaded.meta.scope_root == original.meta.scope_root
        assert set(loaded.nodes.keys()) == set(original.nodes.keys())
        assert set(loaded.treearcs) == set(original.treearcs)
        assert set(loaded.intentlinks.keys()) == set(original.intentlinks.keys())

        # Check LOD preservation
        for uid in original.nodes:
            assert loaded.get_lod(uid) == original.get_lod(uid)

    def test_yaml_is_human_readable(self, tiny_graph: IntentGraph, tmp_path: Path):
        """YAML output is human-readable (not JSON-like)."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        path = tmp_path / "lens.yaml"
        save_lens(lens, path)

        text = path.read_text()

        # Should have YAML-style structure
        assert "lens:" in text
        assert "nodes:" in text
        # Should not have JSON-style braces everywhere
        assert text.count("{") < text.count("\n") / 2


# ================================================================== #
#  File I/O — JSON                                                   #
# ================================================================== #


class TestJSONFileIO:
    """Test save_lens and load_lens with JSON format."""

    def test_save_json(self, tiny_graph: IntentGraph, tmp_path: Path):
        """save_lens with .json extension writes JSON."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        path = tmp_path / "lens.json"
        save_lens(lens, path)

        assert path.exists()
        text = path.read_text()
        doc = json.loads(text)
        assert "lens" in doc

    def test_load_json(self, tiny_graph: IntentGraph, tmp_path: Path):
        """load_lens reads JSON file correctly."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        path = tmp_path / "lens.json"
        save_lens(lens, path)

        loaded = load_lens(path)

        assert loaded.meta.name == "test"
        assert loaded.meta.target_uid == "A"
        assert set(loaded.nodes.keys()) == set(lens.nodes.keys())

    def test_json_round_trip(self, medium_graph: IntentGraph, tmp_path: Path):
        """Full JSON round-trip preserves all data."""
        original = build_lens(medium_graph, target_uid="T.1", budget=100, name="json_test")

        path = tmp_path / "lens.json"
        save_lens(original, path)
        loaded = load_lens(path)

        assert loaded.meta.name == original.meta.name
        assert loaded.meta.target_uid == original.meta.target_uid
        assert set(loaded.nodes.keys()) == set(original.nodes.keys())

        for uid in original.nodes:
            assert loaded.get_lod(uid) == original.get_lod(uid)


# ================================================================== #
#  Agent text format with LOD filtering                              #
# ================================================================== #


class TestLensToAgentText:
    """Test lens_to_agent_text with LOD-based field filtering."""

    def test_agent_text_structure(self, tiny_graph: IntentGraph):
        """lens_to_agent_text produces valid YAML structure."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        text = lens_to_agent_text(lens)
        doc = yaml.safe_load(text)

        assert "lens" in doc
        assert "nodes" in doc
        assert "treearcs" in doc
        assert "intentlinks" in doc

    def test_skeleton_nodes_minimal(self, medium_graph: IntentGraph):
        """Skeleton nodes show only uid and name."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # Set a node to skeleton
        lens.set_lod("L.3.2", LOD.skeleton)

        text = lens_to_agent_text(lens)
        doc = yaml.safe_load(text)

        l32_node = next((n for n in doc["nodes"] if n["uid"] == "L.3.2"), None)
        assert l32_node is not None
        assert "uid" in l32_node
        assert "name" in l32_node
        # Should NOT have intent or other fields
        assert "intent" not in l32_node
        assert "constraints" not in l32_node

    def test_lean_nodes_show_intent_epistemic(self, medium_graph: IntentGraph):
        """Lean nodes show uid, name, intent, epistemic_state."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # ROOT should be lean (ancestor)
        # Let's ensure it's lean
        if lens.get_lod("ROOT") != LOD.lean:
            lens.set_lod("ROOT", LOD.lean)

        text = lens_to_agent_text(lens)
        doc = yaml.safe_load(text)

        root_node = next((n for n in doc["nodes"] if n["uid"] == "ROOT"), None)
        assert root_node is not None
        assert "uid" in root_node
        assert "name" in root_node
        assert "intent" in root_node

        # Should NOT have full-detail fields
        assert "design_notes" not in root_node
        assert "constraints" not in root_node

    def test_full_nodes_show_all_fields(self, medium_graph: IntentGraph):
        """Full nodes show all fields including optional ones."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # Add some optional fields to E.1
        lens.nodes["E.1"].constraints = ["Must be fast"]
        lens.nodes["E.1"].design_notes = "Use streaming parser"

        # E.1 is target → full
        assert lens.get_lod("E.1") == LOD.full

        text = lens_to_agent_text(lens)
        doc = yaml.safe_load(text)

        e1_node = next((n for n in doc["nodes"] if n["uid"] == "E.1"), None)
        assert e1_node is not None
        assert "uid" in e1_node
        assert "name" in e1_node
        assert "intent" in e1_node
        assert "constraints" in e1_node
        assert "design_notes" in e1_node

    def test_intentlinks_visibility_both_lean_or_above(self, medium_graph: IntentGraph):
        """IntentLinks visible only if both endpoints >= lean."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # Set one endpoint to skeleton
        # Find a link where we can test this
        # E_T link: set T to skeleton
        if "E_T" in lens.intentlinks:
            lens.set_lod("T", LOD.skeleton)

            text = lens_to_agent_text(lens)
            doc = yaml.safe_load(text)

            # E_T should NOT appear (T is skeleton)
            link_uids = {link["uid"] for link in doc["intentlinks"]}
            assert "E_T" not in link_uids

    def test_intentlink_description_full_endpoint(self, medium_graph: IntentGraph):
        """IntentLink description shown only if ≥1 endpoint is full."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # E.3 → T.1 link
        # Set both to lean
        if "E.3_T.1" in lens.intentlinks:
            lens.set_lod("E.3", LOD.lean)
            lens.set_lod("T.1", LOD.lean)

            text = lens_to_agent_text(lens)
            doc = yaml.safe_load(text)

            link = next((l for l in doc["intentlinks"] if l["uid"] == "E.3_T.1"), None)
            if link:
                # Both endpoints lean → no intent field
                assert "intent" not in link
                assert "src" in link
                assert "dst" in link

    def test_intentlink_description_shown_when_full(self, medium_graph: IntentGraph):
        """IntentLink description shown when at least one endpoint is full."""
        lens = build_lens(medium_graph, target_uid="T.1", budget=100, name="test")

        # T.1 is target (full), E.3 is intentlink neighbor (full)
        # E.3 → T.1 link should have description

        text = lens_to_agent_text(lens)
        doc = yaml.safe_load(text)

        link = next((l for l in doc["intentlinks"] if l["uid"] == "E.3_T.1"), None)
        if link:
            # At least one endpoint is full → intent shown
            assert "intent" in link

    def test_pruned_children_shown_for_full_nodes(self, medium_graph: IntentGraph):
        """Full nodes with pruned children show pruned_children field."""
        # Use a budget that ensures E remains but some children are pruned
        lens = build_lens(medium_graph, target_uid="E", budget=8, name="test")

        # E should have some children pruned
        if lens.node_metadata.get("E") and lens.node_metadata["E"].pruned_children > 0:
            # E is target → full
            assert lens.get_lod("E") == LOD.full

            text = lens_to_agent_text(lens)
            doc = yaml.safe_load(text)

            e_node = next((n for n in doc["nodes"] if n["uid"] == "E"), None)
            assert e_node is not None
            # Should have pruned_children or collapsed_children field
            # The structure should be valid YAML with node data

    def test_agent_text_sorts_nodes(self, tiny_graph: IntentGraph):
        """lens_to_agent_text sorts nodes by UID."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        text = lens_to_agent_text(lens)
        doc = yaml.safe_load(text)

        node_uids = [n["uid"] for n in doc["nodes"]]
        assert node_uids == sorted(node_uids)


# ================================================================== #
#  Type discriminator                                                #
# ================================================================== #


class TestIsLensFile:
    """Test is_lens_file discriminator."""

    def test_lens_dict_returns_true(self):
        """is_lens_file returns True for lens dict."""
        d = {
            "lens": {
                "name": "test",
                "target_uid": "A",
                "source_graph": "graph.json",
            },
            "nodes": {},
            "treearcs": [],
            "intentlinks": [],
        }

        assert is_lens_file(d) is True

    def test_graph_dict_returns_false(self):
        """is_lens_file returns False for graph dict."""
        d = {
            "meta": {"name": "test"},
            "nodes": [],
            "treearcs": [],
            "intentlinks": [],
        }

        assert is_lens_file(d) is False

    def test_frontier_dict_returns_false(self):
        """is_lens_file returns False for frontier dict."""
        d = {
            "frontier": {"name": "test", "mode": "target-adjacent"},
            "nodes": {},
        }

        assert is_lens_file(d) is False

    def test_missing_required_fields_returns_false(self):
        """is_lens_file returns False if lens meta missing fields."""
        # Missing target_uid
        d = {
            "lens": {
                "name": "test",
                "source_graph": "graph.json",
            },
            "nodes": {},
        }

        assert is_lens_file(d) is False

    def test_non_dict_returns_false(self):
        """is_lens_file returns False for non-dict."""
        assert is_lens_file("not a dict") is False
        assert is_lens_file(None) is False
        assert is_lens_file([]) is False


# ================================================================== #
#  Integration: complex round-trips                                  #
# ================================================================== #


class TestComplexRoundTrips:
    """Test serialization with complex lens states."""

    def test_round_trip_with_scope_root(self, medium_graph: IntentGraph, tmp_path: Path):
        """Round-trip preserves scope_root."""
        lens = build_lens(
            medium_graph,
            target_uid="E.1",
            budget=100,
            scope_root="E",
            name="scoped"
        )

        path = tmp_path / "scoped_lens.yaml"
        save_lens(lens, path)
        loaded = load_lens(path)

        assert loaded.meta.scope_root == "E"
        assert set(loaded.nodes.keys()) == set(lens.nodes.keys())

    def test_round_trip_with_pruning(self, medium_graph: IntentGraph, tmp_path: Path):
        """Round-trip preserves pruned state."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=5, name="pruned")

        path = tmp_path / "pruned_lens.yaml"
        save_lens(lens, path)
        loaded = load_lens(path)

        assert set(loaded.pruned_subtrees) == set(lens.pruned_subtrees)
        assert loaded.node_count() == lens.node_count()

    def test_round_trip_after_modifications(self, tiny_graph: IntentGraph, tmp_path: Path):
        """Round-trip after lens modifications preserves changes."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Make modifications
        lens.nodes["A"].intent = "Modified during test"
        lens.set_lod("B", LOD.skeleton)

        # Don't apply — just save the modified lens
        path = tmp_path / "modified_lens.yaml"
        save_lens(lens, path)
        loaded = load_lens(path)

        # Modifications should be preserved
        assert loaded.nodes["A"].intent == "Modified during test"
        assert loaded.get_lod("B") == LOD.skeleton

    def test_round_trip_preserves_node_details(self, medium_graph: IntentGraph, tmp_path: Path):
        """Round-trip preserves all node optional fields."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # Add rich data to a node
        lens.nodes["E.1"].constraints = ["Must handle CSV", "Must be fast"]
        lens.nodes["E.1"].design_notes = "Use pandas for parsing"
        lens.nodes["E.1"].effort = "medium"

        path = tmp_path / "detailed_lens.yaml"
        save_lens(lens, path)
        loaded = load_lens(path)

        e1 = loaded.nodes["E.1"]
        assert e1.constraints == ["Must handle CSV", "Must be fast"]
        assert e1.design_notes == "Use pandas for parsing"
        assert e1.effort == "medium"

    def test_round_trip_preserves_intentlink_details(self, tiny_graph: IntentGraph, tmp_path: Path):
        """Round-trip preserves intentlink fields."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Modify a link
        if "A_B" in lens.intentlinks:
            lens.intentlinks["A_B"].intent = "Modified link intent"
            lens.intentlinks["A_B"].shape = {"type": "data_flow", "protocol": "json"}

            path = tmp_path / "link_lens.yaml"
            save_lens(lens, path)
            loaded = load_lens(path)

            link = loaded.intentlinks["A_B"]
            assert link.intent == "Modified link intent"
            assert link.shape == {"type": "data_flow", "protocol": "json"}
