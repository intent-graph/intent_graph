"""Tests for Lens model — data structures, metadata, and basic operations."""

import pytest

from intentgraph.models.lens import Lens, LensMeta, LensNode, LOD
from intentgraph.models.node import IntentNode
from intentgraph.models.link import IntentLink


# ================================================================== #
#  LOD enum tests                                                    #
# ================================================================== #


class TestLODEnum:
    """Test LOD comparison operators and ordering."""

    def test_lod_values(self):
        """LOD has exactly three values in order."""
        assert LOD.skeleton.value == "skeleton"
        assert LOD.lean.value == "lean"
        assert LOD.full.value == "full"

    def test_lod_less_than(self):
        """skeleton < lean < full."""
        assert LOD.skeleton < LOD.lean
        assert LOD.lean < LOD.full
        assert LOD.skeleton < LOD.full
        assert not (LOD.full < LOD.lean)
        assert not (LOD.skeleton < LOD.skeleton)

    def test_lod_less_than_or_equal(self):
        """<= includes equality."""
        assert LOD.skeleton <= LOD.lean
        assert LOD.skeleton <= LOD.skeleton
        assert LOD.full <= LOD.full

    def test_lod_greater_than(self):
        """full > lean > skeleton."""
        assert LOD.full > LOD.lean
        assert LOD.lean > LOD.skeleton
        assert LOD.full > LOD.skeleton
        assert not (LOD.skeleton > LOD.lean)

    def test_lod_greater_than_or_equal(self):
        """>= includes equality."""
        assert LOD.full >= LOD.lean
        assert LOD.full >= LOD.full
        assert LOD.skeleton >= LOD.skeleton


# ================================================================== #
#  LensNode tests                                                    #
# ================================================================== #


class TestLensNode:
    """Test LensNode creation and metadata."""

    def test_minimal_construction(self):
        """LensNode requires only uid and lod."""
        ln = LensNode(uid="A", lod=LOD.full)
        assert ln.uid == "A"
        assert ln.lod == LOD.full
        assert ln.pruned_children == 0

    def test_with_pruned_children(self):
        """LensNode can track pruned children count."""
        ln = LensNode(uid="A", lod=LOD.lean, pruned_children=3)
        assert ln.pruned_children == 3

    def test_model_dump(self):
        """LensNode serializes correctly."""
        ln = LensNode(uid="A", lod=LOD.skeleton, pruned_children=2)
        d = ln.model_dump()
        assert d["uid"] == "A"
        assert d["lod"] == "skeleton"
        assert d["pruned_children"] == 2

    def test_roundtrip(self):
        """LensNode round-trips through dict."""
        ln = LensNode(uid="B", lod=LOD.lean, pruned_children=5)
        d = ln.model_dump()
        restored = LensNode.model_validate(d)
        assert restored == ln


# ================================================================== #
#  LensMeta tests                                                    #
# ================================================================== #


class TestLensMeta:
    """Test LensMeta validation and fields."""

    def test_required_fields(self):
        """LensMeta requires name, target_uid, source_graph."""
        meta = LensMeta(
            name="test",
            target_uid="A",
            source_graph="graph.json"
        )
        assert meta.name == "test"
        assert meta.target_uid == "A"
        assert meta.source_graph == "graph.json"
        assert meta.budget == 30  # default
        assert meta.scope_root is None

    def test_full_fields(self):
        """LensMeta supports all optional fields."""
        meta = LensMeta(
            name="work",
            target_uid="E.1",
            source_graph="etl_graph.yaml",
            budget=50,
            scope_root="E",
        )
        assert meta.budget == 50
        assert meta.scope_root == "E"

    def test_roundtrip_dict(self):
        """LensMeta round-trips through dict."""
        meta = LensMeta(
            name="test",
            target_uid="X",
            source_graph="graph.json",
            budget=20,
        )
        d = meta.model_dump()
        restored = LensMeta.model_validate(d)
        assert restored == meta


# ================================================================== #
#  Lens model tests                                                  #
# ================================================================== #


class TestLensModel:
    """Test Lens data model and basic accessors."""

    def test_empty_construction(self):
        """Lens can be constructed with minimal fields."""
        meta = LensMeta(name="empty", target_uid="A", source_graph="g.json")
        lens = Lens(meta=meta)
        assert lens.meta.name == "empty"
        assert lens.meta.target_uid == "A"
        assert len(lens.nodes) == 0
        assert len(lens.node_metadata) == 0
        assert len(lens.treearcs) == 0
        assert len(lens.intentlinks) == 0
        assert lens.pruned_subtrees == []

    def test_with_nodes(self):
        """Lens can contain nodes and metadata."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        node_a = IntentNode(uid="A", name="Module A", intent="Does A")
        node_b = IntentNode(uid="B", name="Module B", intent="Does B")

        lens = Lens(
            meta=meta,
            nodes={"A": node_a, "B": node_b},
            node_metadata={
                "A": LensNode(uid="A", lod=LOD.full),
                "B": LensNode(uid="B", lod=LOD.lean),
            },
            treearcs=[("ROOT", "A"), ("ROOT", "B")],
        )

        assert len(lens.nodes) == 2
        assert "A" in lens.nodes
        assert lens.node_metadata["A"].lod == LOD.full
        assert lens.node_metadata["B"].lod == LOD.lean

    def test_get_lod(self):
        """get_lod retrieves node's LOD."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        node_a = IntentNode(uid="A", name="A", intent="Intent A")
        lens = Lens(
            meta=meta,
            nodes={"A": node_a},
            node_metadata={"A": LensNode(uid="A", lod=LOD.skeleton)},
        )

        assert lens.get_lod("A") == LOD.skeleton

    def test_get_lod_missing_raises(self):
        """get_lod raises KeyError for missing node."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        lens = Lens(meta=meta)

        with pytest.raises(KeyError):
            lens.get_lod("nonexistent")

    def test_set_lod(self):
        """set_lod changes node's LOD."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        node_a = IntentNode(uid="A", name="A", intent="Intent A")
        lens = Lens(
            meta=meta,
            nodes={"A": node_a},
            node_metadata={"A": LensNode(uid="A", lod=LOD.skeleton)},
        )

        lens.set_lod("A", LOD.full)
        assert lens.get_lod("A") == LOD.full

    def test_set_lod_missing_raises(self):
        """set_lod raises KeyError for missing node."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        lens = Lens(meta=meta)

        with pytest.raises(KeyError, match="not in lens"):
            lens.set_lod("nonexistent", LOD.full)

    def test_is_pruned(self):
        """is_pruned checks pruned_subtrees list."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        lens = Lens(meta=meta, pruned_subtrees=["E.1", "T.3"])

        assert lens.is_pruned("E.1")
        assert lens.is_pruned("T.3")
        assert not lens.is_pruned("A")


# ================================================================== #
#  Lens state management                                             #
# ================================================================== #


class TestLensStateManagement:
    """Test snapshot_base_state and dirty tracking."""

    def test_snapshot_base_state_captures_current(self):
        """snapshot_base_state copies current working state."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        node_a = IntentNode(uid="A", name="A", intent="Intent A")
        lens = Lens(
            meta=meta,
            nodes={"A": node_a},
            node_metadata={"A": LensNode(uid="A", lod=LOD.full)},
            treearcs=[("ROOT", "A")],
            intentlinks={},
        )

        lens.snapshot_base_state()

        assert lens.base_state is not None
        assert "nodes" in lens.base_state
        assert "A" in lens.base_state["nodes"]
        assert lens.base_state["treearcs"] == [("ROOT", "A")]
        assert lens.dirty is False

    def test_snapshot_clears_dirty_flag(self):
        """snapshot_base_state sets dirty to False."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        lens = Lens(meta=meta)

        lens.dirty = True
        lens.snapshot_base_state()

        assert lens.dirty is False

    def test_mark_dirty(self):
        """mark_dirty sets dirty flag."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        lens = Lens(meta=meta)

        lens.dirty = False
        lens.mark_dirty()

        assert lens.dirty is True


# ================================================================== #
#  Lens statistics                                                   #
# ================================================================== #


class TestLensStatistics:
    """Test lod_stats, node_count, visible_link_count."""

    def test_node_count(self):
        """node_count returns number of nodes."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        node_a = IntentNode(uid="A", name="A", intent="A")
        node_b = IntentNode(uid="B", name="B", intent="B")
        lens = Lens(
            meta=meta,
            nodes={"A": node_a, "B": node_b},
            node_metadata={
                "A": LensNode(uid="A", lod=LOD.full),
                "B": LensNode(uid="B", lod=LOD.lean),
            },
        )

        assert lens.node_count() == 2

    def test_lod_stats(self):
        """lod_stats counts nodes at each LOD level."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        nodes = {
            "A": IntentNode(uid="A", name="A", intent="A"),
            "B": IntentNode(uid="B", name="B", intent="B"),
            "C": IntentNode(uid="C", name="C", intent="C"),
            "D": IntentNode(uid="D", name="D", intent="D"),
        }
        metadata = {
            "A": LensNode(uid="A", lod=LOD.full),
            "B": LensNode(uid="B", lod=LOD.full),
            "C": LensNode(uid="C", lod=LOD.lean),
            "D": LensNode(uid="D", lod=LOD.skeleton),
        }
        lens = Lens(meta=meta, nodes=nodes, node_metadata=metadata)

        stats = lens.lod_stats()

        assert stats["full"] == 2
        assert stats["lean"] == 1
        assert stats["skeleton"] == 1

    def test_visible_link_count(self):
        """visible_link_count returns number of visible intentlinks."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        link1 = IntentLink(uid="A_B", src="A", dst="B", intent="A to B")
        link2 = IntentLink(uid="B_C", src="B", dst="C", intent="B to C")
        lens = Lens(
            meta=meta,
            intentlinks={"A_B": link1, "B_C": link2},
        )

        assert lens.visible_link_count() == 2


# ================================================================== #
#  Lens serialization round-trip                                     #
# ================================================================== #


class TestLensSerialization:
    """Test to_serial_dict and from_serial_dict round-trip."""

    def test_to_serial_dict_structure(self):
        """to_serial_dict produces expected structure."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json", budget=25)
        node_a = IntentNode(uid="A", name="Module A", intent="Does A")
        lens = Lens(
            meta=meta,
            nodes={"A": node_a},
            node_metadata={"A": LensNode(uid="A", lod=LOD.full, pruned_children=2)},
            treearcs=[("ROOT", "A")],
            intentlinks={},
            pruned_subtrees=["B"],
        )

        d = lens.to_serial_dict()

        assert "lens" in d
        assert d["lens"]["name"] == "test"
        assert d["lens"]["target_uid"] == "A"
        assert d["lens"]["budget"] == 25
        assert "nodes" in d
        assert "A" in d["nodes"]
        assert d["nodes"]["A"]["lod"] == "full"
        assert d["nodes"]["A"]["pruned_children"] == 2
        assert "treearcs" in d
        assert len(d["treearcs"]) == 1
        assert d["pruned_subtrees"] == ["B"]

    def test_to_serial_dict_omits_zero_pruned_children(self):
        """to_serial_dict omits pruned_children when 0."""
        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        node_a = IntentNode(uid="A", name="A", intent="A")
        lens = Lens(
            meta=meta,
            nodes={"A": node_a},
            node_metadata={"A": LensNode(uid="A", lod=LOD.skeleton, pruned_children=0)},
        )

        d = lens.to_serial_dict()

        assert "pruned_children" not in d["nodes"]["A"]

    def test_from_serial_dict(self):
        """from_serial_dict reconstructs Lens."""
        d = {
            "lens": {
                "name": "test",
                "target_uid": "A",
                "budget": 20,
                "source_graph": "graph.json",
                "scope_root": None,
            },
            "nodes": {
                "A": {
                    "uid": "A",
                    "name": "Module A",
                    "intent": "Does A",
                    "epistemic_state": "known",
                    "lod": "full",
                    "pruned_children": 1,
                },
            },
            "treearcs": [{"parent": "ROOT", "child": "A"}],
            "intentlinks": [],
            "pruned_subtrees": [],
        }

        lens = Lens.from_serial_dict(d)

        assert lens.meta.name == "test"
        assert lens.meta.target_uid == "A"
        assert lens.meta.budget == 20
        assert "A" in lens.nodes
        assert lens.nodes["A"].name == "Module A"
        assert lens.get_lod("A") == LOD.full
        assert lens.node_metadata["A"].pruned_children == 1
        assert len(lens.treearcs) == 1

    def test_round_trip(self):
        """to_serial_dict → from_serial_dict preserves state."""
        meta = LensMeta(name="rt", target_uid="E.1", source_graph="etl.json", budget=40)
        node_e = IntentNode(uid="E", name="Extract", intent="Extraction phase")
        node_e1 = IntentNode(uid="E.1", name="Parse CSV", intent="Parse CSV files")
        link = IntentLink(uid="E_E1", src="E", dst="E.1", intent="Parent to child")

        lens = Lens(
            meta=meta,
            nodes={"E": node_e, "E.1": node_e1},
            node_metadata={
                "E": LensNode(uid="E", lod=LOD.lean),
                "E.1": LensNode(uid="E.1", lod=LOD.full, pruned_children=0),
            },
            treearcs=[("ROOT", "E"), ("E", "E.1")],
            intentlinks={"E_E1": link},
            pruned_subtrees=["T"],
        )

        # Snapshot base state (from_serial_dict does this automatically)
        lens.snapshot_base_state()

        d = lens.to_serial_dict()
        restored = Lens.from_serial_dict(d)

        assert restored.meta.name == lens.meta.name
        assert restored.meta.target_uid == lens.meta.target_uid
        assert restored.meta.budget == lens.meta.budget
        assert set(restored.nodes.keys()) == set(lens.nodes.keys())
        assert restored.get_lod("E") == LOD.lean
        assert restored.get_lod("E.1") == LOD.full
        assert set(restored.treearcs) == set(lens.treearcs)
        assert set(restored.intentlinks.keys()) == set(lens.intentlinks.keys())
        assert restored.pruned_subtrees == lens.pruned_subtrees
        # from_serial_dict automatically snapshots
        assert restored.base_state is not None
        assert restored.dirty is False

    def test_from_serial_dict_rebuilds_parent_pointers(self):
        """from_serial_dict rebuilds parent_uid and children_uids."""
        d = {
            "lens": {
                "name": "test",
                "target_uid": "A",
                "budget": 30,
                "source_graph": "g.json",
            },
            "nodes": {
                "ROOT": {"uid": "ROOT", "name": "Root", "intent": "Root", "lod": "skeleton"},
                "A": {"uid": "A", "name": "A", "intent": "A", "lod": "full"},
            },
            "treearcs": [{"parent": "ROOT", "child": "A"}],
            "intentlinks": [],
            "pruned_subtrees": [],
        }

        lens = Lens.from_serial_dict(d)

        assert lens.nodes["A"].parent_uid == "ROOT"
        assert "A" in lens.nodes["ROOT"].children_uids
