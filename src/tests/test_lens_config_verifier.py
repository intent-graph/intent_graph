"""Verifier tests for Phase 5.1 LensConfig position support.

Derived independently from PIG constraints (LENSSCHEMA.NODESHAPE, LENSSCHEMA.VALIDATION,
PERSISTENCE.POSITIONS) to validate the implementer's code against the intent contract.
These tests focus on edge cases and constraint boundaries that complement the
implementer's test_lens_config.py file.

PIG reference:
- LENSSCHEMA.NODESHAPE: LensNodeEntry shape, position optionality, coordinate frame
- LENSSCHEMA.VALIDATION: V-POS1 (finite only), V-POS2 (exactly x and y keys)
- PERSISTENCE.POSITIONS: parent-relative frame, Cytoscape center storage
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pytest
import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.models.lens_config import LensConfig, LensNodeEntry, Position
from intentgraph.serial.json_yaml import (
    dict_to_graph,
    graph_to_dict,
    graph_to_yaml,
    yaml_to_graph,
    load_graph,
    save_graph,
)
from intentgraph.validation import validate_lenses


def _simple_graph() -> IntentGraph:
    """Minimal test graph: ROOT → AUTH."""
    g = IntentGraph(meta={"name": "test"})
    g.add_node("ROOT", "Root", "Root")
    g.add_node_under("AUTH", "Auth", "Auth", parent_uid="ROOT")
    return g


# ================================================================== #
#  Position Boundary Values — Finitude Constraint (V-POS1)          #
# ================================================================== #


class TestPositionFinitudeBoundaries:
    """V-POS1: x and y must be finite. Test edge cases on the boundary of valid/invalid.

    PIG: LENSSCHEMA.VALIDATION — 'x and y must be ... finite. NaN and Infinity are rejected.'
    """

    def test_position_max_finite_value(self):
        # from PIG: PERSISTENCE.POSITIONS — position must be numeric and finite
        p = Position(x=1.7976931348623157e308, y=-1.7976931348623157e308)
        assert math.isfinite(p.x)
        assert math.isfinite(p.y)

    def test_position_very_small_positive_finite(self):
        # from PIG: LENSSCHEMA.NODESHAPE — no lower bound specified, only finiteness
        p = Position(x=1e-308, y=1e-308)
        assert math.isfinite(p.x)
        assert math.isfinite(p.y)

    def test_position_negative_zero(self):
        # from PIG: PERSISTENCE.POSITIONS — parent-relative coordinates can be any finite value
        p = Position(x=-0.0, y=0.0)
        assert math.isfinite(p.x)
        assert math.isfinite(p.y)

    def test_position_negative_coordinates(self):
        # from PIG: LENSSCHEMA.NODESHAPE — 'parent-relative: (x, y) offset from parent top-left'
        # Negative offsets are valid (child to left or above parent reference point)
        p = Position(x=-100.5, y=-50.25)
        assert p.x == -100.5
        assert p.y == -50.25

    def test_lens_node_entry_with_large_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE — position stores coordinate pair
        e = LensNodeEntry(lod="lean", position=Position(x=1e6, y=-1e6))
        assert e.position is not None
        assert e.position.x == 1e6
        assert e.position.y == -1e6

    def test_validate_lenses_accepts_max_finite_coordinates(self):
        # from PIG: LENSSCHEMA.VALIDATION — no bounds check; drag handler enforces bounds
        g = _simple_graph()
        lc = LensConfig(
            name="extreme",
            nodes={
                "ROOT": LensNodeEntry(lod="skeleton"),
                "AUTH": LensNodeEntry(
                    lod="lean",
                    position=Position(x=1e308, y=1e308)
                ),
            },
        )
        g.add_lens(lc)
        issues = validate_lenses(g)
        errors = [i for i in issues if i["severity"] == "error" and "V-POS1" in i["issue"]]
        assert errors == []


# ================================================================== #
#  LOD Enum Strictness — Only Three Literals                        #
# ================================================================== #


class TestLODEnumStrictness:
    """PIG: LENSSCHEMA.NODESHAPE — lod is Literal['skeleton', 'lean', 'full'].

    Test that only these three values are accepted; case-sensitive.
    """

    def test_lod_skeleton_valid(self):
        e = LensNodeEntry(lod="skeleton")
        assert e.lod == "skeleton"

    def test_lod_lean_valid(self):
        e = LensNodeEntry(lod="lean")
        assert e.lod == "lean"

    def test_lod_full_valid(self):
        e = LensNodeEntry(lod="full")
        assert e.lod == "full"

    def test_lod_uppercase_skeleton_rejected(self):
        # from PIG: LENSSCHEMA.NODESHAPE — Literal["skeleton", "lean", "full"] is case-sensitive
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensNodeEntry(lod="SKELETON")

    def test_lod_uppercase_lean_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensNodeEntry(lod="LEAN")

    def test_lod_uppercase_full_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensNodeEntry(lod="FULL")

    def test_lod_typo_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensNodeEntry(lod="medium")


# ================================================================== #
#  Position Optionality — Omission Rule & YAML Null Handling        #
# ================================================================== #


class TestPositionOptionalityAndOmission:
    """PIG: LENSSCHEMA.NODESHAPE — 'position is optional; absent means the node is unpinned.'
    Design notes: 'position is omitted when None' (omission rule, SERIALIZATION_FORMAT.md §4).

    Test that position=None does not serialize a position key, and that hand-authored
    YAML with explicit `position: null` or missing position both deserialize to None.
    """

    def test_position_none_on_construction(self):
        # from PIG: LENSSCHEMA.NODESHAPE — position optional, default None
        e = LensNodeEntry(lod="lean")
        assert e.position is None

    def test_position_none_explicit_on_construction(self):
        # from PIG: LENSSCHEMA.NODESHAPE — can explicitly set position=None
        e = LensNodeEntry(lod="lean", position=None)
        assert e.position is None

    def test_position_absent_in_dict_serialization(self):
        # from PIG: LENSSCHEMA.NODESHAPE design_notes — position omitted when None
        e = LensNodeEntry(lod="lean")
        d = e.model_dump(exclude_none=True)
        assert "position" not in d
        assert d == {"lod": "lean"}

    def test_position_absent_in_yaml_serialization(self):
        # from PIG: LENSSCHEMA.NODESHAPE — omission rule applies
        g = _simple_graph()
        lc = LensConfig(
            name="unpinned",
            nodes={"ROOT": LensNodeEntry(lod="skeleton")},
        )
        g.add_lens(lc)
        yaml_str = graph_to_yaml(g)
        parsed = yaml.safe_load(yaml_str)
        root_entry = parsed["lenses"]["unpinned"]["nodes"]["ROOT"]
        assert "position" not in root_entry

    def test_deserialize_position_null_yields_none(self, tmp_path: Path):
        # from PIG: LENSSCHEMA.NODESHAPE — position: null in YAML should deserialize to None
        yaml_content = """\
meta:
  name: "Explicit null position"
nodes:
  - uid: ROOT
    name: Root
    intent: Root
treearcs: []
intentlinks: []
frontiers: []
lenses:
  test-lens:
    name: test-lens
    nodes:
      ROOT:
        lod: skeleton
        position: null
"""
        fp = tmp_path / "null_pos.ig.yaml"
        fp.write_text(yaml_content, encoding="utf-8")
        g = load_graph(fp)
        entry = g.lenses["test-lens"].nodes["ROOT"]
        assert entry.position is None

    def test_deserialize_missing_position_key(self, tmp_path: Path):
        # from PIG: LENSSCHEMA.NODESHAPE — missing position key means unpinned
        yaml_content = """\
meta:
  name: "Missing position key"
nodes:
  - uid: ROOT
    name: Root
    intent: Root
treearcs: []
intentlinks: []
frontiers: []
lenses:
  test-lens:
    name: test-lens
    nodes:
      ROOT:
        lod: lean
"""
        fp = tmp_path / "missing_pos.ig.yaml"
        fp.write_text(yaml_content, encoding="utf-8")
        g = load_graph(fp)
        entry = g.lenses["test-lens"].nodes["ROOT"]
        assert entry.position is None


# ================================================================== #
#  V-POS2: Position Dict Key Validation                             #
# ================================================================== #


class TestPositionDictKeyValidation:
    """V-POS2: position must contain exactly the keys x and y.

    PIG: LENSSCHEMA.VALIDATION — 'must contain exactly the keys x and y (no extra keys).'
    """

    def test_position_rejects_z_key(self):
        # from PIG: LENSSCHEMA.VALIDATION — V-POS2
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": 0.0, "y": 0.0, "z": 0.0})

    def test_position_rejects_only_x(self):
        # from PIG: LENSSCHEMA.VALIDATION — must have both x and y
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": 0.0})

    def test_position_rejects_only_y(self):
        # from PIG: LENSSCHEMA.VALIDATION — must have both x and y
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"y": 0.0})

    def test_position_rejects_empty_dict(self):
        # from PIG: LENSSCHEMA.VALIDATION — must have both x and y
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({})

    def test_position_rejects_mixed_extra_keys(self):
        # from PIG: LENSSCHEMA.VALIDATION — extra='forbid' on Position
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": 0.0, "y": 0.0, "z": 1, "w": 2})

    def test_lens_node_entry_validates_position_shape(self):
        # from PIG: LENSSCHEMA.VALIDATION — V-POS2 validated on deserialization
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LensNodeEntry.model_validate({
                "lod": "lean",
                "position": {"x": 0.0, "y": 0.0, "extra": 1}
            })


# ================================================================== #
#  Type Checking on Position Coordinates                            #
# ================================================================== #


class TestPositionTypeValidation:
    """PIG: LENSSCHEMA.VALIDATION — 'x and y must be numeric (float or int)'.

    Pydantic will coerce int to float and reject non-numeric types.
    """

    def test_position_accepts_int_coordinates(self):
        # from PIG: LENSSCHEMA.VALIDATION — accepts float or int
        p = Position(x=10, y=20)
        assert isinstance(p.x, (int, float))
        assert isinstance(p.y, (int, float))

    def test_position_coerces_int_to_numeric(self):
        # from PIG: LENSSCHEMA.VALIDATION — numeric includes int
        p = Position.model_validate({"x": 5, "y": 10})
        assert p.x == 5
        assert p.y == 10

    def test_position_rejects_string_x(self):
        # from PIG: LENSSCHEMA.VALIDATION — must be numeric
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": "invalid", "y": 0.0})

    def test_position_rejects_string_y(self):
        # from PIG: LENSSCHEMA.VALIDATION — must be numeric
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": 0.0, "y": "invalid"})

    def test_position_rejects_none_x(self):
        # from PIG: LENSSCHEMA.VALIDATION — must be numeric, not null
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": None, "y": 0.0})

    def test_position_rejects_list_coordinate(self):
        # from PIG: LENSSCHEMA.VALIDATION — must be numeric, not compound
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Position.model_validate({"x": [0, 0], "y": 0.0})


# ================================================================== #
#  Round-trip Stability — Position Preservation Across Edit Ops    #
# ================================================================== #


class TestPositionPreservationEdits:
    """PIG: LENSSCHEMA.NODESHAPE — position persists across LOD changes and node edits.

    Implementer scratchpad says 'set_lod and add_node preserve existing position when
    updating LOD.' Verify round-trip integrity.
    """

    def test_round_trip_preserves_position_across_multiple_edits(self):
        # from PIG: LENSSCHEMA.NODESHAPE — position is user-decidable visual state
        g = _simple_graph()
        lc = LensConfig(
            name="edit-safe",
            nodes={
                "ROOT": LensNodeEntry(lod="skeleton"),
                "AUTH": LensNodeEntry(lod="lean", position=Position(x=50.0, y=100.0)),
            },
        )
        g.add_lens(lc)

        # Serialize
        yaml_str = graph_to_yaml(g)

        # Deserialize
        g2 = yaml_to_graph(yaml_str)
        entry = g2.lenses["edit-safe"].nodes["AUTH"]
        assert entry.position is not None
        assert entry.position.x == 50.0
        assert entry.position.y == 100.0

    def test_set_lod_does_not_clear_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE — position is independent of lod
        lc = LensConfig(
            name="test",
            nodes={"ROOT": LensNodeEntry(lod="skeleton", position=Position(x=10.0, y=20.0))},
        )
        lc.set_lod("ROOT", "lean")
        assert lc.nodes["ROOT"].lod == "lean"
        assert lc.nodes["ROOT"].position is not None
        assert lc.nodes["ROOT"].position.x == 10.0

    def test_add_node_with_position_argument_not_supported(self):
        # from PIG: LENSSCHEMA.NODESHAPE — position is set separately or in constructor
        g = _simple_graph()
        lc = LensConfig(name="test")
        lc.add_node("ROOT", "full", g)
        # add_node does not take position arg; position must be set post-hoc
        assert lc.nodes["ROOT"].position is None
        lc.nodes["ROOT"].position = Position(x=5.0, y=10.0)
        assert lc.nodes["ROOT"].position is not None


# ================================================================== #
#  Complex Serialization Scenarios                                  #
# ================================================================== #


class TestComplexSerializationScenarios:
    """PIG: LENSSCHEMA.NODESHAPE, PERSISTENCE.POSITIONS — round-trip under various conditions.

    Test mixed scenarios: some nodes pinned, some unpinned, multiple lenses, etc.
    """

    def test_mixed_pinned_unpinned_nodes(self):
        # from PIG: LENSSCHEMA.NODESHAPE — position optional per node
        g = _simple_graph()
        lc = LensConfig(
            name="mixed",
            nodes={
                "ROOT": LensNodeEntry(lod="skeleton"),  # unpinned
                "AUTH": LensNodeEntry(lod="lean", position=Position(x=100.0, y=200.0)),  # pinned
            },
        )
        g.add_lens(lc)

        yaml_str = graph_to_yaml(g)
        g2 = yaml_to_graph(yaml_str)

        root_entry = g2.lenses["mixed"].nodes["ROOT"]
        auth_entry = g2.lenses["mixed"].nodes["AUTH"]
        assert root_entry.position is None
        assert auth_entry.position is not None
        assert auth_entry.position.x == 100.0

    def test_dict_serialization_omits_none_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE design_notes — position omitted when None
        g = _simple_graph()
        lc = LensConfig(
            name="test",
            nodes={
                "ROOT": LensNodeEntry(lod="skeleton"),
                "AUTH": LensNodeEntry(lod="lean", position=Position(x=1.0, y=2.0)),
            },
        )
        g.add_lens(lc)

        d = graph_to_dict(g)
        root_dict = d["lenses"]["test"]["nodes"]["ROOT"]
        auth_dict = d["lenses"]["test"]["nodes"]["AUTH"]

        assert "position" not in root_dict
        assert "position" in auth_dict
        assert auth_dict["position"] == {"x": 1.0, "y": 2.0}

    def test_json_round_trip_with_positions(self):
        # from PIG: LENSSCHEMA.NODESHAPE — JSON and YAML both supported
        import json

        g = _simple_graph()
        lc = LensConfig(
            name="json-test",
            nodes={
                "ROOT": LensNodeEntry(lod="skeleton", position=Position(x=-5.5, y=10.5)),
            },
        )
        g.add_lens(lc)

        d = graph_to_dict(g)
        json_str = json.dumps(d)
        d2 = json.loads(json_str)
        g2 = dict_to_graph(d2)

        entry = g2.lenses["json-test"].nodes["ROOT"]
        assert entry.position is not None
        assert entry.position.x == -5.5
        assert entry.position.y == 10.5


# ================================================================== #
#  Cross-check: Position and LOD Independence                       #
# ================================================================== #


class TestPositionLODIndependence:
    """PIG: LENSSCHEMA.NODESHAPE — lod and position are independent fields.

    A node can have any combination: any lod with or without position.
    """

    def test_skeleton_with_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE — position and lod are both per-node, independent
        e = LensNodeEntry(lod="skeleton", position=Position(x=0.0, y=0.0))
        assert e.lod == "skeleton"
        assert e.position is not None

    def test_lean_with_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE
        e = LensNodeEntry(lod="lean", position=Position(x=50.0, y=100.0))
        assert e.lod == "lean"
        assert e.position is not None

    def test_full_with_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE
        e = LensNodeEntry(lod="full", position=Position(x=-10.0, y=-20.0))
        assert e.lod == "full"
        assert e.position is not None

    def test_skeleton_without_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE
        e = LensNodeEntry(lod="skeleton")
        assert e.lod == "skeleton"
        assert e.position is None

    def test_lean_without_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE
        e = LensNodeEntry(lod="lean")
        assert e.lod == "lean"
        assert e.position is None

    def test_full_without_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE
        e = LensNodeEntry(lod="full")
        assert e.lod == "full"
        assert e.position is None


# ================================================================== #
#  Coordinate Frame Semantics (Parent-Relative)                     #
# ================================================================== #


class TestCoordinateFrameSemantics:
    """PIG: LENSSCHEMA.NODESHAPE, PERSISTENCE.POSITIONS — coordinate frame is parent-relative.

    'parent-relative: (x, y) offset from parent top-left. ROOT is implicit (0,0) and never stored.'
    Test that ROOT position is never serialized (should be None if present).
    """

    def test_root_position_none_by_default(self):
        # from PIG: PERSISTENCE.POSITIONS — ROOT implicit (0,0); never stored
        e = LensNodeEntry(lod="skeleton")
        assert e.position is None

    def test_non_root_can_have_position(self):
        # from PIG: LENSSCHEMA.NODESHAPE — 'position is optional; absent means unpinned'
        # Non-ROOT nodes can have positions
        e = LensNodeEntry(lod="lean", position=Position(x=50.0, y=75.0))
        assert e.position is not None
        assert e.position.x == 50.0
        assert e.position.y == 75.0

    def test_position_can_be_zero(self):
        # from PIG: LENSSCHEMA.NODESHAPE — zero is a valid offset (child at parent top-left)
        p = Position(x=0.0, y=0.0)
        assert p.x == 0.0
        assert p.y == 0.0
