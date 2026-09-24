"""Tests for LensConfig model, IntentGraph.lenses integration,
closure invariants, validation rules, and serialization round-trip.

Spec: foundation_and_formalism/LENS_REDESIGN_SPEC.md
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest
import yaml

from intentgraph.errors import ClosureViolation
from intentgraph.models.graph import IntentGraph
from intentgraph.models.lens_config import LensConfig, LensNodeEntry, Position
from intentgraph.serial.json_yaml import (
    dict_to_graph,
    graph_to_dict,
    graph_to_json,
    graph_to_yaml,
    load_graph,
    save_graph,
    yaml_to_graph,
)
from intentgraph.validation import validate_lenses


# ================================================================== #
#  Helpers                                                            #
# ================================================================== #


def _e(lod: str, *, x: float | None = None, y: float | None = None) -> LensNodeEntry:
    """Shorthand: build a LensNodeEntry, optionally with position."""
    pos = Position(x=x, y=y) if x is not None and y is not None else None
    return LensNodeEntry(lod=lod, position=pos)  # type: ignore[arg-type]


# ================================================================== #
#  Fixtures                                                           #
# ================================================================== #


@pytest.fixture
def simple_graph() -> IntentGraph:
    """AUTH → AUTH.1 → AUTH.1.1, one intentlink AUTH.1 → AUTH.1.1."""
    g = IntentGraph(meta={"name": "auth"})
    g.add_node("ROOT", "Root", "System root")
    g.add_node_under("AUTH", "Authentication", "Handles auth", parent_uid="ROOT")
    g.add_node_under("AUTH.1", "Credential Validation", "Validates creds", parent_uid="AUTH")
    g.add_node_under(
        "AUTH.1.1", "Token Issuance", "Issues tokens after validation", parent_uid="AUTH.1"
    )
    g.add_link("AUTH.1", "AUTH.1.1", "Validated creds trigger token issuance")
    return g


@pytest.fixture
def empty_lens() -> LensConfig:
    return LensConfig(name="empty-lens")


# ================================================================== #
#  AC1 + AC2 — LensConfig model basics                               #
# ================================================================== #


class TestLensConfigModel:
    def test_ac1_defaults(self):
        """AC1: LensConfig instantiates with name, nodes, intentlinks only."""
        lc = LensConfig(name="my-lens")
        assert lc.name == "my-lens"
        assert lc.description is None
        assert lc.target_uids == []
        assert lc.nodes == {}
        assert lc.intentlinks == []

    def test_ac2_empty_name_raises(self):
        """AC2: empty/whitespace name raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensConfig(name="")

        with pytest.raises(ValidationError):
            LensConfig(name="   ")

    def test_full_construction(self):
        lc = LensConfig(
            name="auth-flow",
            description="Auth data path",
            target_uids=["AUTH.1"],
            nodes={
                "ROOT": _e("skeleton"),
                "AUTH": _e("lean"),
                "AUTH.1": _e("full"),
            },
            intentlinks=["AUTH.1_AUTH.1.1"],
        )
        assert lc.description == "Auth data path"
        assert "AUTH" in lc.nodes
        assert lc.nodes["AUTH"].lod == "lean"
        assert "AUTH.1_AUTH.1.1" in lc.intentlinks

    def test_model_validate_from_dict(self):
        raw = {
            "name": "test",
            "nodes": {"ROOT": {"lod": "skeleton"}},
            "intentlinks": [],
        }
        lc = LensConfig.model_validate(raw)
        assert lc.name == "test"
        assert lc.nodes["ROOT"].lod == "skeleton"

    def test_reject_old_scalar_shape(self):
        """Old dict[uid, lod_str] shape raises ValidationError (no backward compat).

        PIG: LENSSCHEMA.NODESHAPE — 'Old shape: ... -- scalar lod string.'
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensConfig.model_validate({
                "name": "test",
                "nodes": {"ROOT": "skeleton"},
            })


# ================================================================== #
#  Position and LensNodeEntry model                                   #
# ================================================================== #


class TestPositionModel:
    def test_position_construction(self):
        """Position(x, y) constructs correctly."""
        p = Position(x=100.0, y=200.0)
        assert p.x == 100.0
        assert p.y == 200.0

    def test_position_rejects_extra_keys(self):
        """Position extra='forbid' rejects extra keys.

        PIG: LENSSCHEMA.VALIDATION — V-POS2
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": 0.0, "y": 0.0, "z": 5.0})

    def test_lens_node_entry_without_position(self):
        """LensNodeEntry with no position has position=None."""
        e = LensNodeEntry(lod="lean")
        assert e.lod == "lean"
        assert e.position is None

    def test_lens_node_entry_with_position(self):
        """LensNodeEntry with position stores it correctly."""
        e = LensNodeEntry(lod="full", position=Position(x=10.0, y=20.0))
        assert e.lod == "full"
        assert e.position is not None
        assert e.position.x == 10.0
        assert e.position.y == 20.0

    def test_lens_node_entry_from_dict_with_position(self):
        """LensNodeEntry deserializes from dict with nested position dict."""
        e = LensNodeEntry.model_validate({"lod": "full", "position": {"x": 5.0, "y": 7.0}})
        assert e.position is not None
        assert e.position.x == 5.0

    def test_lens_node_entry_from_dict_without_position(self):
        """LensNodeEntry deserializes from dict without position key."""
        e = LensNodeEntry.model_validate({"lod": "lean"})
        assert e.position is None


# ================================================================== #
#  Closure invariants (Spec §6)                                       #
# ================================================================== #


class TestClosureInvariants:
    def test_ac5_add_node_ancestor_fill(self, simple_graph: IntentGraph):
        """AC5: add_node auto-inserts all ancestors at skeleton."""
        lc = LensConfig(name="test")
        lc.add_node("AUTH.1.1", "full", simple_graph)

        # Target node is at 'full'
        assert lc.nodes["AUTH.1.1"].lod == "full"
        # Every ancestor must be present
        assert "AUTH.1" in lc.nodes
        assert "AUTH" in lc.nodes
        assert "ROOT" in lc.nodes
        # Ancestors default to skeleton
        assert lc.nodes["AUTH.1"].lod == "skeleton"
        assert lc.nodes["AUTH"].lod == "skeleton"
        assert lc.nodes["ROOT"].lod == "skeleton"

    def test_add_node_no_duplicate_ancestor_downgrade(self, simple_graph: IntentGraph):
        """Adding a node should not downgrade an ancestor already at lean/full."""
        lc = LensConfig(name="test")
        lc.nodes["ROOT"] = _e("lean")
        lc.nodes["AUTH"] = _e("full")
        lc.add_node("AUTH.1", "full", simple_graph)

        # Existing LODs are not downgraded
        assert lc.nodes["ROOT"].lod == "lean"
        assert lc.nodes["AUTH"].lod == "full"
        assert lc.nodes["AUTH.1"].lod == "full"

    def test_ac6_remove_node_descendant_purge(self, simple_graph: IntentGraph):
        """AC6: remove_node removes uid, all descendants, and touching links."""
        lc = LensConfig(name="test")
        # Populate manually (bypassing closure for setup)
        lc.nodes = {
            "ROOT": _e("skeleton"),
            "AUTH": _e("lean"),
            "AUTH.1": _e("full"),
            "AUTH.1.1": _e("full"),
        }
        lc.intentlinks = ["AUTH.1_AUTH.1.1"]

        lc.remove_node("AUTH", simple_graph)

        assert "AUTH" not in lc.nodes
        assert "AUTH.1" not in lc.nodes
        assert "AUTH.1.1" not in lc.nodes
        # Link whose endpoints are in the removed set must also be removed
        assert "AUTH.1_AUTH.1.1" not in lc.intentlinks
        # ROOT survives
        assert "ROOT" in lc.nodes

    def test_remove_node_leaf(self, simple_graph: IntentGraph):
        """Removing a leaf removes only that node and its touching links."""
        lc = LensConfig(name="test")
        lc.nodes = {
            "ROOT": _e("skeleton"),
            "AUTH": _e("lean"),
            "AUTH.1": _e("full"),
            "AUTH.1.1": _e("full"),
        }
        lc.intentlinks = ["AUTH.1_AUTH.1.1"]

        lc.remove_node("AUTH.1.1", simple_graph)

        assert "AUTH.1.1" not in lc.nodes
        assert "AUTH.1_AUTH.1.1" not in lc.intentlinks
        assert "AUTH.1" in lc.nodes  # parent survives

    def test_ac7_add_link_closure_violation(self, simple_graph: IntentGraph):
        """AC7: add_link raises ClosureViolation when endpoint not in lens."""
        lc = LensConfig(name="test")
        lc.nodes = {
            "ROOT": _e("skeleton"),
            "AUTH": _e("lean"),
            "AUTH.1": _e("full"),
        }
        # AUTH.1.1 is NOT in the lens

        with pytest.raises(ClosureViolation, match="endpoint"):
            lc.add_link("AUTH.1_AUTH.1.1", simple_graph)

    def test_add_link_success(self, simple_graph: IntentGraph):
        """add_link succeeds when both endpoints are in the lens."""
        lc = LensConfig(name="test")
        lc.nodes = {
            "ROOT": _e("skeleton"),
            "AUTH": _e("lean"),
            "AUTH.1": _e("full"),
            "AUTH.1.1": _e("full"),
        }
        lc.add_link("AUTH.1_AUTH.1.1", simple_graph)
        assert "AUTH.1_AUTH.1.1" in lc.intentlinks

    def test_add_link_nonexistent_link_raises(self, simple_graph: IntentGraph):
        """add_link raises when link does not exist in graph."""
        lc = LensConfig(name="test")
        lc.nodes = {"ROOT": _e("skeleton")}
        with pytest.raises(ValueError, match="does not exist"):
            lc.add_link("NONEXISTENT_LINK", simple_graph)

    def test_ac8_set_lod_does_not_change_keyset(self, simple_graph: IntentGraph):
        """AC8: set_lod does not change lens.nodes keyset."""
        lc = LensConfig(name="test")
        lc.nodes = {"ROOT": _e("skeleton"), "AUTH": _e("lean")}
        original_keys = set(lc.nodes.keys())

        lc.set_lod("AUTH", "full")

        assert lc.nodes["AUTH"].lod == "full"
        assert set(lc.nodes.keys()) == original_keys  # no new keys, none removed

    def test_set_lod_preserves_position(self, simple_graph: IntentGraph):
        """set_lod must not alter an existing position.

        PIG: LENSSCHEMA.NODESHAPE — position persists across LOD changes.
        """
        lc = LensConfig(name="test")
        lc.nodes = {"ROOT": _e("skeleton"), "AUTH": _e("lean", x=10.0, y=20.0)}
        lc.set_lod("AUTH", "full")
        assert lc.nodes["AUTH"].lod == "full"
        assert lc.nodes["AUTH"].position is not None
        assert lc.nodes["AUTH"].position.x == 10.0
        assert lc.nodes["AUTH"].position.y == 20.0

    def test_set_lod_node_not_in_lens_raises(self):
        lc = LensConfig(name="test")
        lc.nodes = {"ROOT": _e("skeleton")}
        with pytest.raises(ValueError, match="not in the lens"):
            lc.set_lod("AUTH", "full")

    def test_remove_link_unconstrained(self):
        """remove_link removes a link with no side effects."""
        lc = LensConfig(
            name="test",
            nodes={"ROOT": _e("skeleton"), "AUTH": _e("lean")},
            intentlinks=["link1", "link2"],
        )
        lc.remove_link("link1")
        assert "link1" not in lc.intentlinks
        assert "link2" in lc.intentlinks

    def test_remove_node_not_in_lens_raises(self, simple_graph: IntentGraph):
        """remove_node raises when uid not in lens."""
        lc = LensConfig(name="test")
        lc.nodes = {}
        with pytest.raises(ValueError, match="not in the lens"):
            lc.remove_node("AUTH", simple_graph)

    def test_add_node_nonexistent_uid_raises(self, simple_graph: IntentGraph):
        """add_node raises when uid does not exist in graph."""
        lc = LensConfig(name="test")
        with pytest.raises(ValueError, match="does not exist"):
            lc.add_node("NONEXISTENT", "full", simple_graph)

    def test_add_node_preserves_existing_position(self, simple_graph: IntentGraph):
        """add_node on an already-present uid preserves its position.

        PIG: LENSSCHEMA.NODESHAPE — position field is user-decidable visual state.
        """
        lc = LensConfig(name="test")
        lc.nodes["ROOT"] = _e("skeleton")
        lc.nodes["AUTH"] = _e("lean")
        lc.nodes["AUTH.1"] = _e("skeleton", x=50.0, y=75.0)
        lc.add_node("AUTH.1", "full", simple_graph)
        assert lc.nodes["AUTH.1"].lod == "full"
        assert lc.nodes["AUTH.1"].position is not None
        assert lc.nodes["AUTH.1"].position.x == 50.0


# ================================================================== #
#  IntentGraph.lenses convenience methods                             #
# ================================================================== #


class TestIntentGraphLensMethods:
    def test_add_and_get_lens(self, simple_graph: IntentGraph):
        lc = LensConfig(name="my-lens", nodes={"ROOT": _e("skeleton")})
        simple_graph.add_lens(lc)
        retrieved = simple_graph.get_lens("my-lens")
        assert retrieved is lc

    def test_get_lens_missing_raises(self, simple_graph: IntentGraph):
        with pytest.raises(KeyError):
            simple_graph.get_lens("nonexistent")

    def test_remove_lens(self, simple_graph: IntentGraph):
        lc = LensConfig(name="to-remove")
        simple_graph.add_lens(lc)
        simple_graph.remove_lens("to-remove")
        assert "to-remove" not in simple_graph.lenses

    def test_remove_lens_clears_default_lens(self, simple_graph: IntentGraph):
        lc = LensConfig(name="default")
        simple_graph.add_lens(lc)
        simple_graph.meta["default_lens"] = "default"
        simple_graph.remove_lens("default")
        assert "default_lens" not in simple_graph.meta

    def test_remove_lens_missing_raises(self, simple_graph: IntentGraph):
        with pytest.raises(KeyError):
            simple_graph.remove_lens("nonexistent")

    def test_lenses_default_empty(self, simple_graph: IntentGraph):
        assert simple_graph.lenses == {}


# ================================================================== #
#  Serialization round-trip (AC3, AC4, AC19)                         #
# ================================================================== #


class TestLensConfigSerialization:
    def test_ac3_lenses_omitted_when_empty(self, simple_graph: IntentGraph):
        """AC3: graph_to_dict omits lenses key when graph.lenses is empty."""
        d = graph_to_dict(simple_graph)
        assert "lenses" not in d

    def test_ac4_round_trip_yaml(self, simple_graph: IntentGraph):
        """AC4: round-trip through YAML preserves lenses."""
        lc = LensConfig(
            name="auth-flow",
            description="Auth path",
            target_uids=["AUTH.1"],
            nodes={
                "ROOT": _e("skeleton"),
                "AUTH": _e("lean"),
                "AUTH.1": _e("full"),
            },
            intentlinks=["AUTH.1_AUTH.1.1"],
        )
        simple_graph.add_lens(lc)

        yaml_str = graph_to_yaml(simple_graph)
        restored = yaml_to_graph(yaml_str)

        assert "auth-flow" in restored.lenses
        restored_lc = restored.lenses["auth-flow"]
        assert restored_lc.name == "auth-flow"
        assert restored_lc.description == "Auth path"
        assert restored_lc.target_uids == ["AUTH.1"]
        assert restored_lc.nodes["ROOT"].lod == "skeleton"
        assert restored_lc.nodes["AUTH"].lod == "lean"
        assert restored_lc.nodes["AUTH.1"].lod == "full"
        assert "AUTH.1_AUTH.1.1" in restored_lc.intentlinks

    def test_round_trip_json(self, simple_graph: IntentGraph):
        """Round-trip through JSON preserves lenses."""
        lc = LensConfig(
            name="compact",
            nodes={"ROOT": _e("skeleton"), "AUTH": _e("lean")},
        )
        simple_graph.add_lens(lc)

        json_str = graph_to_json(simple_graph)
        d = json.loads(json_str)
        restored = dict_to_graph(d)

        assert "compact" in restored.lenses
        assert restored.lenses["compact"].nodes["AUTH"].lod == "lean"

    def test_round_trip_without_position(self, simple_graph: IntentGraph):
        """Round-trip: lens without positions; position key absent in serialized output.

        PIG: LENSSCHEMA.NODESHAPE — 'position is optional; absent means unpinned.'
        """
        lc = LensConfig(name="no-pos", nodes={"ROOT": _e("lean")})
        simple_graph.add_lens(lc)

        d = graph_to_dict(simple_graph)
        node_entry = d["lenses"]["no-pos"]["nodes"]["ROOT"]
        assert "position" not in node_entry, "position key must be absent when None"
        assert node_entry == {"lod": "lean"}

        restored = dict_to_graph(d)
        assert restored.lenses["no-pos"].nodes["ROOT"].position is None

    def test_round_trip_with_position(self, simple_graph: IntentGraph):
        """Round-trip: lens with positions survives serialization intact.

        PIG: LENSSCHEMA.NODESHAPE, PERSISTENCE.POSITIONS
        """
        lc = LensConfig(
            name="pinned",
            nodes={
                "ROOT": _e("skeleton"),
                "AUTH": _e("full", x=100.0, y=200.0),
            },
        )
        simple_graph.add_lens(lc)

        yaml_str = graph_to_yaml(simple_graph)
        restored = yaml_to_graph(yaml_str)

        entry = restored.lenses["pinned"].nodes["AUTH"]
        assert entry.lod == "full"
        assert entry.position is not None
        assert entry.position.x == 100.0
        assert entry.position.y == 200.0

    def test_position_absent_in_yaml_output_when_none(self, simple_graph: IntentGraph):
        """position key is not emitted in YAML when position=None (omission rule).

        PIG: LENSSCHEMA.NODESHAPE design_notes — 'position is omitted when None.'
        """
        lc = LensConfig(name="clean", nodes={"ROOT": _e("lean")})
        simple_graph.add_lens(lc)
        yaml_str = graph_to_yaml(simple_graph)
        parsed = yaml.safe_load(yaml_str)
        node_raw = parsed["lenses"]["clean"]["nodes"]["ROOT"]
        assert "position" not in node_raw

    def test_ac19_hand_authored_yaml_roundtrip(self, tmp_path: Path):
        """AC19: hand-authored YAML with lenses block round-trips correctly."""
        yaml_content = """\
meta:
  name: "Hand-authored IG"
  default_lens: main-view
nodes:
  - uid: ROOT
    name: Root
    intent: System root
  - uid: AUTH
    name: Auth
    intent: Authentication
treearcs:
  - {parent: ROOT, child: AUTH}
intentlinks: []
frontiers: []
lenses:
  main-view:
    name: main-view
    description: "Primary view"
    nodes:
      ROOT:
        lod: skeleton
      AUTH:
        lod: lean
    intentlinks: []
"""
        fp = tmp_path / "test.ig.yaml"
        fp.write_text(yaml_content, encoding="utf-8")

        g = load_graph(fp)

        assert "main-view" in g.lenses
        lc = g.lenses["main-view"]
        assert lc.description == "Primary view"
        assert lc.nodes["ROOT"].lod == "skeleton"
        assert lc.nodes["AUTH"].lod == "lean"

        # Save and reload
        out_path = tmp_path / "out.ig.yaml"
        save_graph(g, out_path)
        g2 = load_graph(out_path)
        assert "main-view" in g2.lenses
        assert g2.lenses["main-view"].nodes["AUTH"].lod == "lean"

    def test_hand_authored_yaml_with_position(self, tmp_path: Path):
        """Hand-authored YAML with position field deserializes correctly.

        PIG: LENSSCHEMA.NODESHAPE
        """
        yaml_content = """\
meta:
  name: "IG with positions"
nodes:
  - uid: ROOT
    name: Root
    intent: Root node
  - uid: AUTH
    name: Auth
    intent: Auth node
treearcs:
  - {parent: ROOT, child: AUTH}
intentlinks: []
frontiers: []
lenses:
  pinned:
    name: pinned
    nodes:
      ROOT:
        lod: skeleton
      AUTH:
        lod: full
        position:
          x: 150.0
          y: 75.0
"""
        fp = tmp_path / "with_pos.ig.yaml"
        fp.write_text(yaml_content, encoding="utf-8")
        g = load_graph(fp)
        entry = g.lenses["pinned"].nodes["AUTH"]
        assert entry.lod == "full"
        assert entry.position is not None
        assert entry.position.x == 150.0
        assert entry.position.y == 75.0

    def test_empty_intentlinks_omitted_from_serial(self, simple_graph: IntentGraph):
        """Empty intentlinks list is omitted in serialized dict (compact form)."""
        lc = LensConfig(name="compact", nodes={"ROOT": _e("skeleton")})
        simple_graph.add_lens(lc)
        d = graph_to_dict(simple_graph)
        assert "intentlinks" not in d["lenses"]["compact"]

    def test_empty_target_uids_omitted_from_serial(self, simple_graph: IntentGraph):
        """Empty target_uids list is omitted in serialized dict (compact form)."""
        lc = LensConfig(name="compact", nodes={"ROOT": _e("skeleton")})
        simple_graph.add_lens(lc)
        d = graph_to_dict(simple_graph)
        assert "target_uids" not in d["lenses"]["compact"]

    def test_multiple_lenses_round_trip(self, simple_graph: IntentGraph):
        """Multiple lenses all survive serialization round-trip."""
        simple_graph.add_lens(LensConfig(name="lens-a", nodes={"ROOT": _e("lean")}))
        simple_graph.add_lens(
            LensConfig(name="lens-b", nodes={"ROOT": _e("full"), "AUTH": _e("lean")})
        )

        restored = yaml_to_graph(graph_to_yaml(simple_graph))
        assert "lens-a" in restored.lenses
        assert "lens-b" in restored.lenses
        assert restored.lenses["lens-b"].nodes["AUTH"].lod == "lean"


# ================================================================== #
#  Validation rules (Spec §7)                                         #
# ================================================================== #


class TestValidateLenses:
    def test_no_lenses_no_issues(self, simple_graph: IntentGraph):
        """Empty lenses dict produces zero issues."""
        issues = validate_lenses(simple_graph)
        assert issues == []

    def test_ac9_v_l1_unknown_node_uid(self, simple_graph: IntentGraph):
        """AC9: V-L1 — lens references a non-existent node UID."""
        lc = LensConfig(
            name="bad",
            nodes={"ROOT": _e("skeleton"), "NONEXISTENT": _e("full")},
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("NONEXISTENT" in i["issue"] for i in errors)

    def test_v_l2_unknown_link_uid(self, simple_graph: IntentGraph):
        """V-L2: lens references a non-existent intentlink UID."""
        lc = LensConfig(
            name="bad",
            nodes={
                "ROOT": _e("skeleton"),
                "AUTH": _e("lean"),
                "AUTH.1": _e("full"),
            },
            intentlinks=["NO_SUCH_LINK"],
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("NO_SUCH_LINK" in i["issue"] for i in errors)

    def test_ac10_v_l3_ancestor_closure_violation(self, simple_graph: IntentGraph):
        """AC10: V-L3 — ancestor missing from lens."""
        # AUTH.1 is displayed but AUTH (its parent) is not
        lc = LensConfig(
            name="bad-closure",
            nodes={"ROOT": _e("skeleton"), "AUTH.1": _e("full")},  # AUTH missing
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("ancestor" in i["issue"] and "AUTH" in i["issue"] for i in errors)

    def test_v_l4_link_endpoint_not_in_lens(self, simple_graph: IntentGraph):
        """V-L4: link is displayed but one endpoint is not in nodes."""
        # Include the link but exclude AUTH.1.1 from nodes
        lc = LensConfig(
            name="bad-link",
            nodes={
                "ROOT": _e("skeleton"),
                "AUTH": _e("lean"),
                "AUTH.1": _e("full"),
            },
            intentlinks=["AUTH.1_AUTH.1.1"],
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any(
            "AUTH.1_AUTH.1.1" in i["issue"] and "endpoint" in i["issue"]
            for i in errors
        )

    def test_ac11_v_l5_default_lens_not_found(self, simple_graph: IntentGraph):
        """AC11: V-L5 warning when meta.default_lens is missing from lenses."""
        simple_graph.meta["default_lens"] = "nonexistent-lens"
        issues = validate_lenses(simple_graph)
        warnings = [i for i in issues if i["severity"] == "warning"]
        assert any(
            "default_lens" in i["issue"] and "nonexistent-lens" in i["issue"]
            for i in warnings
        )

    def test_v_l5_default_lens_valid_no_warning(self, simple_graph: IntentGraph):
        """V-L5: no warning when default_lens points to an existing lens."""
        simple_graph.add_lens(LensConfig(name="ok-lens"))
        simple_graph.meta["default_lens"] = "ok-lens"
        issues = validate_lenses(simple_graph)
        warnings = [i for i in issues if i["severity"] == "warning"]
        assert not any("default_lens" in i.get("issue", "") for i in warnings)

    def test_ac12_derived_ig_valid(self, tmp_path: Path):
        """AC12: derived IG with correct meta.derived_from + V-L7 coverage passes."""
        g = IntentGraph(meta={
            "name": "Reduced",
            "derived_from": {"of": "parent.ig.yaml", "via_lens": "auth-flow"},
        })
        g.add_node("ROOT", "Root", "Root")
        g.add_node("AUTH", "Auth", "Auth")
        lc = LensConfig(
            name="auth-flow",
            nodes={"ROOT": _e("skeleton"), "AUTH": _e("lean")},
        )
        g.add_lens(lc)
        issues = validate_lenses(g)
        errors = [i for i in issues if i["severity"] == "error"]
        assert errors == []

    def test_ac13_v_l7_node_not_covered(self, tmp_path: Path):
        """AC13: V-L7 fails when a node in derived IG is not in via_lens.nodes."""
        g = IntentGraph(meta={
            "name": "Reduced",
            "derived_from": {"of": "parent.ig.yaml", "via_lens": "partial-lens"},
        })
        g.add_node("ROOT", "Root", "Root")
        g.add_node("AUTH", "Auth", "Auth")
        g.add_node("EXTRA", "Extra", "Extra node not in lens")

        lc = LensConfig(
            name="partial-lens",
            nodes={"ROOT": _e("skeleton"), "AUTH": _e("lean")},  # EXTRA missing
        )
        g.add_lens(lc)
        issues = validate_lenses(g)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("EXTRA" in i.get("uid", "") or "EXTRA" in i["issue"] for i in errors)

    def test_v_l6_via_lens_not_in_lenses(self):
        """V-L6: error when via_lens in meta.derived_from is not in lenses."""
        g = IntentGraph(meta={
            "name": "Reduced",
            "derived_from": {"of": "parent.ig.yaml", "via_lens": "missing-lens"},
        })
        g.add_node("ROOT", "Root", "Root")
        # No lenses at all
        issues = validate_lenses(g)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any(
            "via_lens" in i["issue"] and "missing-lens" in i["issue"]
            for i in errors
        )

    def test_valid_lens_no_issues(self, simple_graph: IntentGraph):
        """A fully correct lens (all closure invariants satisfied) produces no errors."""
        lc = LensConfig(
            name="good-lens",
            nodes={
                "ROOT": _e("skeleton"),
                "AUTH": _e("lean"),
                "AUTH.1": _e("full"),
                "AUTH.1.1": _e("full"),
            },
            intentlinks=["AUTH.1_AUTH.1.1"],
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert errors == []

    def test_valid_lens_with_positions_no_issues(self, simple_graph: IntentGraph):
        """A lens with valid positions produces no errors.

        PIG: LENSSCHEMA.VALIDATION
        """
        lc = LensConfig(
            name="pinned",
            nodes={
                "ROOT": _e("skeleton"),
                "AUTH": _e("lean", x=0.0, y=0.0),
                "AUTH.1": _e("full", x=100.0, y=200.0),
                "AUTH.1.1": _e("full"),
            },
            intentlinks=["AUTH.1_AUTH.1.1"],
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert errors == []


# ================================================================== #
#  V-POS1 / V-POS2 validation rules                                  #
# ================================================================== #


class TestPositionValidation:
    """Tests for V-POS1 and V-POS2 position validation rules.

    PIG: LENSSCHEMA.VALIDATION
    """

    def _graph_with_pinned_entry(
        self, lod: str, pos: Position | None
    ) -> tuple[IntentGraph, LensConfig]:
        g = IntentGraph(meta={"name": "test"})
        g.add_node("ROOT", "Root", "Root")
        lc = LensConfig(
            name="lens",
            nodes={"ROOT": LensNodeEntry(lod=lod, position=pos)},
        )
        g.add_lens(lc)
        return g, lc

    def test_v_pos1_nan_x_fails(self, simple_graph: IntentGraph):
        """V-POS1: NaN in position.x is rejected.

        PIG: LENSSCHEMA.VALIDATION — 'NaN and Infinity are rejected.'
        """
        lc = LensConfig(
            name="bad",
            nodes={
                "ROOT": LensNodeEntry(lod="lean", position=Position(x=float("nan"), y=0.0))
            },
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("V-POS1" in i["issue"] for i in errors)

    def test_v_pos1_inf_x_fails(self, simple_graph: IntentGraph):
        """V-POS1: +Inf in position.x is rejected.

        PIG: LENSSCHEMA.VALIDATION
        """
        lc = LensConfig(
            name="bad",
            nodes={
                "ROOT": LensNodeEntry(
                    lod="lean", position=Position(x=math.inf, y=0.0)
                )
            },
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("V-POS1" in i["issue"] for i in errors)

    def test_v_pos1_neg_inf_y_fails(self, simple_graph: IntentGraph):
        """V-POS1: -Inf in position.y is rejected.

        PIG: LENSSCHEMA.VALIDATION
        """
        lc = LensConfig(
            name="bad",
            nodes={
                "ROOT": LensNodeEntry(
                    lod="lean", position=Position(x=0.0, y=-math.inf)
                )
            },
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("V-POS1" in i["issue"] for i in errors)

    def test_v_pos1_finite_values_pass(self, simple_graph: IntentGraph):
        """V-POS1: finite x and y produce no V-POS1 error.

        PIG: LENSSCHEMA.VALIDATION
        """
        lc = LensConfig(
            name="ok",
            nodes={
                "ROOT": _e("lean"),
                "AUTH": _e("full", x=10.5, y=-30.0),
            },
        )
        simple_graph.add_lens(lc)
        issues = validate_lenses(simple_graph)
        pos1_errors = [
            i for i in issues if i["severity"] == "error" and "V-POS1" in i["issue"]
        ]
        assert pos1_errors == []

    def test_v_pos2_extra_key_rejected_at_construction(self):
        """V-POS2: position dict with extra key is rejected by Position(extra='forbid').

        PIG: LENSSCHEMA.VALIDATION — 'must have exactly keys x and y'
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": 0.0, "y": 0.0, "z": 5.0})

    def test_v_pos2_missing_key_rejected_at_construction(self):
        """V-POS2: position dict missing y is rejected at model construction.

        PIG: LENSSCHEMA.VALIDATION
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": 0.0})

    def test_v_pos2_missing_key_rejected_via_lens_node_entry(self):
        """V-POS2: LensNodeEntry deserialization with {x: 0} raises ValidationError.

        PIG: LENSSCHEMA.VALIDATION
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensNodeEntry.model_validate({"lod": "lean", "position": {"x": 0.0}})

    def test_v_pos2_extra_key_rejected_via_lens_node_entry(self):
        """V-POS2: LensNodeEntry deserialization with {x,y,z} raises ValidationError.

        PIG: LENSSCHEMA.VALIDATION
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensNodeEntry.model_validate(
                {"lod": "lean", "position": {"x": 0.0, "y": 0.0, "z": 1.0}}
            )

    def test_v_pos_string_coordinate_rejected(self):
        """position.x='foo' raises ValidationError (type error).

        PIG: LENSSCHEMA.VALIDATION — 'must be numeric (float or int)'
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensNodeEntry.model_validate(
                {"lod": "lean", "position": {"x": "foo", "y": 0.0}}
            )

    def test_reject_old_string_node_shape(self):
        """Old shape 'nodes: {UID: lod_str}' raises a clear deserialization error.

        PIG: LENSSCHEMA.NODESHAPE — 'Old shape ... no backward-compatible extension path'
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensConfig.model_validate({
                "name": "old",
                "nodes": {"ROOT": "lean"},
            })


# ================================================================== #
#  V-CG cross-IG lens validation (Spec §10)                          #
# ================================================================== #


class TestCrossIGValidation:
    """Tests for V-CG1–V-CG4 cross-IG lens reference validation (Spec §10).

    Each rule has a failing test (violation → specific error/warning) and a
    passing test (valid case → no issue of that kind).
    """

    def _make_local_graph(self) -> IntentGraph:
        """A small graph to serve as the 'home' IG in cross-IG tests."""
        g = IntentGraph(meta={"name": "home-graph"})
        g.add_node("ROOT", "Root", "Root node")
        g.add_node_under("AUTH", "Auth", "Auth node", parent_uid="ROOT")
        return g

    def _make_foreign_graph(self, tmp_path: Path) -> Path:
        """Write a small foreign IG to a temp file; return its path."""
        fg = IntentGraph(meta={"name": "foreign-graph"})
        fg.add_node("F_ROOT", "Foreign Root", "Root of foreign graph")
        fp = tmp_path / "foreign.ig.yaml"
        save_graph(fg, fp)
        return fp

    def _write_manifest(
        self, tmp_path: Path, graph_id: str, graph_file: Path
    ) -> Path:
        """Write an intent_resources.yaml manifest; return its path."""
        import yaml as _yaml
        manifest = {
            "product": [
                {"id": graph_id, "name": graph_id, "file": str(graph_file)},
            ]
        }
        mp = tmp_path / "intent_resources.yaml"
        mp.write_text(_yaml.dump(manifest), encoding="utf-8")
        return mp

    # --- V-CG1: manifest declared but missing ---

    def test_vcg1_missing_manifest_warns(self, tmp_path: Path):
        """V-CG1: meta.intent_resources points to a non-existent file → warning."""
        g = self._make_local_graph()
        g.meta["intent_resources"] = "nonexistent_resources.yaml"
        ig_fp = tmp_path / "home.ig.yaml"
        save_graph(g, ig_fp)

        issues = validate_lenses(g, ig_path=ig_fp)
        warnings = [i for i in issues if i["severity"] == "warning"]
        assert any("V-CG1" in i["issue"] or "intent_resources" in i["issue"]
                   for i in warnings), f"Expected V-CG1 warning; got: {issues}"

    def test_vcg1_no_warning_when_manifest_absent(self, tmp_path: Path):
        """V-CG1: no meta.intent_resources set → no V-CG1 warning."""
        g = self._make_local_graph()
        g.add_lens(LensConfig(
            name="local-lens",
            nodes={"ROOT": _e("skeleton"), "AUTH": _e("lean")},
        ))
        ig_fp = tmp_path / "home.ig.yaml"
        save_graph(g, ig_fp)

        issues = validate_lenses(g, ig_path=ig_fp)
        vcg1_issues = [
            i for i in issues
            if "V-CG1" in i.get("issue", "") or
               ("intent_resources" in i.get("issue", "") and i["severity"] == "warning")
        ]
        assert vcg1_issues == []

    # --- V-CG2: qualified UID present but no intent_resources ---

    def test_vcg2_qualified_uid_without_resources_errors(self, tmp_path: Path):
        """V-CG2: qualified UID in lens but meta.intent_resources absent → error."""
        g = self._make_local_graph()
        g.add_lens(LensConfig(
            name="cross-lens",
            nodes={"foreign_graph:F_ROOT": _e("full")},
        ))
        ig_fp = tmp_path / "home.ig.yaml"
        save_graph(g, ig_fp)

        issues = validate_lenses(g, ig_path=ig_fp)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("V-CG2" in i["issue"] for i in errors), (
            f"Expected V-CG2 error; got: {errors}"
        )

    def test_vcg2_no_error_when_intent_resources_present(self, tmp_path: Path):
        """V-CG2: qualified UID with meta.intent_resources present → no V-CG2 error."""
        foreign_fp = self._make_foreign_graph(tmp_path)
        manifest_fp = self._write_manifest(tmp_path, "fg", foreign_fp)

        g = self._make_local_graph()
        g.meta["intent_resources"] = manifest_fp.name
        g.add_lens(LensConfig(
            name="cross-lens",
            nodes={"fg:F_ROOT": _e("full")},
        ))
        ig_fp = tmp_path / "home.ig.yaml"
        save_graph(g, ig_fp)

        issues = validate_lenses(g, ig_path=ig_fp)
        errors = [i for i in issues if i["severity"] == "error"]
        vcg2_errors = [e for e in errors if "V-CG2" in e["issue"]]
        assert vcg2_errors == [], f"Unexpected V-CG2 errors: {vcg2_errors}"

    # --- V-CG3: graph_id not in manifest ---

    def test_vcg3_unknown_graph_id_errors(self, tmp_path: Path):
        """V-CG3: qualified UID graph_id not found in manifest → error."""
        foreign_fp = self._make_foreign_graph(tmp_path)
        manifest_fp = self._write_manifest(tmp_path, "fg", foreign_fp)

        g = self._make_local_graph()
        g.meta["intent_resources"] = manifest_fp.name
        g.add_lens(LensConfig(
            name="cross-lens",
            nodes={"unknown_graph:F_ROOT": _e("full")},
        ))
        ig_fp = tmp_path / "home.ig.yaml"
        save_graph(g, ig_fp)

        issues = validate_lenses(g, ig_path=ig_fp)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("V-CG3" in i["issue"] for i in errors), (
            f"Expected V-CG3 error; got: {errors}"
        )

    def test_vcg3_known_graph_id_passes(self, tmp_path: Path):
        """V-CG3: qualified UID with valid graph_id in manifest → no V-CG3 error."""
        foreign_fp = self._make_foreign_graph(tmp_path)
        manifest_fp = self._write_manifest(tmp_path, "fg", foreign_fp)

        g = self._make_local_graph()
        g.meta["intent_resources"] = manifest_fp.name
        g.add_lens(LensConfig(
            name="cross-lens",
            nodes={"fg:F_ROOT": _e("full")},
        ))
        ig_fp = tmp_path / "home.ig.yaml"
        save_graph(g, ig_fp)

        issues = validate_lenses(g, ig_path=ig_fp)
        errors = [i for i in issues if i["severity"] == "error"]
        vcg3_errors = [e for e in errors if "V-CG3" in e["issue"]]
        assert vcg3_errors == [], f"Unexpected V-CG3 errors: {vcg3_errors}"

    # --- V-CG4: node_uid not found in foreign graph ---

    def test_vcg4_missing_foreign_node_errors(self, tmp_path: Path):
        """V-CG4: qualified UID node not found in foreign graph → error."""
        foreign_fp = self._make_foreign_graph(tmp_path)
        manifest_fp = self._write_manifest(tmp_path, "fg", foreign_fp)

        g = self._make_local_graph()
        g.meta["intent_resources"] = manifest_fp.name
        g.add_lens(LensConfig(
            name="cross-lens",
            nodes={"fg:MISSING_NODE": _e("full")},
        ))
        ig_fp = tmp_path / "home.ig.yaml"
        save_graph(g, ig_fp)

        issues = validate_lenses(g, ig_path=ig_fp)
        errors = [i for i in issues if i["severity"] == "error"]
        assert any("V-CG4" in i["issue"] for i in errors), (
            f"Expected V-CG4 error; got: {errors}"
        )

    def test_vcg4_existing_foreign_node_passes(self, tmp_path: Path):
        """V-CG4: qualified UID node exists in foreign graph → no V-CG4 error."""
        foreign_fp = self._make_foreign_graph(tmp_path)
        manifest_fp = self._write_manifest(tmp_path, "fg", foreign_fp)

        g = self._make_local_graph()
        g.meta["intent_resources"] = manifest_fp.name
        g.add_lens(LensConfig(
            name="cross-lens",
            nodes={"fg:F_ROOT": _e("full")},
        ))
        ig_fp = tmp_path / "home.ig.yaml"
        save_graph(g, ig_fp)

        issues = validate_lenses(g, ig_path=ig_fp)
        errors = [i for i in issues if i["severity"] == "error"]
        vcg4_errors = [e for e in errors if "V-CG4" in e["issue"]]
        assert vcg4_errors == [], f"Unexpected V-CG4 errors: {vcg4_errors}"
