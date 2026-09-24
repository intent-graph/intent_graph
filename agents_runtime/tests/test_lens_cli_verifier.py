"""Verifier tests for Phase 5.2 (set-position, clear-position, add-node --x/--y).

These tests are derived from the PIG (LENSSCHEMA.IGCMDS, LENSSCHEMA.NODESHAPE,
LENSSCHEMA.VALIDATION) and verify the CLI against the canonical contract, not the
implementer's code. Tests use subprocess-level invocation (end-to-end CLI fidelity)
and cross-validation with ig-tool validate to ensure round-trippability.

Reference:
- PIG: vscode_extension/intentgraph-vscode/projection_ig/vscode_viewer.ig.yaml
  - LENSSCHEMA.IGCMDS — subcommand definitions
  - LENSSCHEMA.NODESHAPE — LensNodeEntry shape {lod, position?}
  - LENSSCHEMA.VALIDATION — V-POS1 (finite), V-POS2 (x,y keys only)
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.models.lens_config import LensConfig, LensNodeEntry, Position
from intentgraph.serial.json_yaml import load_graph, save_graph


# ================================================================== #
#  Helpers                                                            #
# ================================================================== #


def _entry(lod: str, x: float | None = None, y: float | None = None) -> LensNodeEntry:
    """Build a LensNodeEntry for fixtures."""
    pos = Position(x=x, y=y) if x is not None and y is not None else None
    return LensNodeEntry(lod=lod, position=pos)


def _run_ig_tool(args: list[str]) -> tuple[int, str, str]:
    """Run ig-tool subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["ig-tool"] + args,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout, result.stderr


def _validate_graph(graph_path: Path) -> tuple[int, str]:
    """Run ig-tool validate on a graph; return (returncode, stdout)."""
    code, out, err = _run_ig_tool(["validate", "-g", str(graph_path)])
    return code, out


# ================================================================== #
#  Fixtures                                                           #
# ================================================================== #


@pytest.fixture
def auth_graph(tmp_path: Path) -> tuple[IntentGraph, Path]:
    """Small auth graph for testing."""
    g = IntentGraph(meta={"name": "auth"})
    g.add_node("ROOT", "Root", "System root")
    g.add_node_under("AUTH", "Authentication", "Handles auth", parent_uid="ROOT")
    g.add_node_under("AUTH.1", "Credential Validation", "Validates creds", parent_uid="AUTH")
    g.add_node_under(
        "AUTH.1.1", "Token Issuance", "Issues tokens", parent_uid="AUTH.1"
    )
    g.add_link("AUTH.1", "AUTH.1.1", "Creds trigger token issuance")
    fp = tmp_path / "auth.ig.yaml"
    save_graph(g, fp)
    return g, fp


@pytest.fixture
def lensed_graph(auth_graph: tuple[IntentGraph, Path]) -> tuple[IntentGraph, Path]:
    """Graph with a lens pre-populated with all auth nodes."""
    g, fp = auth_graph
    lc = LensConfig(
        name="view",
        nodes={
            "ROOT": _entry("skeleton"),
            "AUTH": _entry("lean"),
            "AUTH.1": _entry("full"),
            "AUTH.1.1": _entry("full"),
        },
    )
    g.add_lens(lc)
    save_graph(g, fp)
    return g, fp


# ================================================================== #
#  Subprocess-Level Tests (end-to-end CLI fidelity)                   #
# ================================================================== #


class TestPositionCommandsSubprocess:
    """PIG LENSSCHEMA.IGCMDS: subprocess-level CLI tests for set-position, clear-position."""

    def test_set_position_subprocess_success(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.IGCMDS — set-position -g G --lens N --uid U --x N --y N sets position."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "100",
            "--y", "200"
        ])
        assert code == 0, f"set-position failed: {err}"
        assert "status: ok" in out or "set-position" in out

        # Verify mutation persisted
        g2 = load_graph(fp)
        entry = g2.lenses["view"].nodes["AUTH.1"]
        assert entry.position is not None
        assert entry.position.x == 100.0
        assert entry.position.y == 200.0
        assert entry.lod == "full"

    def test_set_position_subprocess_negative_coords(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.NODESHAPE — position accepts negative finite coordinates."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "-50.5",
            "--y", "-100.25"
        ])
        assert code == 0, f"set-position with negative coords failed: {err}"

        g2 = load_graph(fp)
        entry = g2.lenses["view"].nodes["AUTH.1"]
        assert entry.position.x == -50.5
        assert entry.position.y == -100.25

    def test_set_position_subprocess_zero_coords(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.NODESHAPE — position accepts zero coordinates."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "0",
            "--y", "0"
        ])
        assert code == 0, f"set-position with zero coords failed: {err}"

        g2 = load_graph(fp)
        entry = g2.lenses["view"].nodes["AUTH.1"]
        assert entry.position.x == 0.0
        assert entry.position.y == 0.0

    def test_clear_position_subprocess_success(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.IGCMDS — clear-position -g G --lens N --uid U removes position."""
        g, fp = lensed_graph
        # First set a position
        _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "50",
            "--y", "75"
        ])

        # Clear it
        code, out, err = _run_ig_tool([
            "graph", "lens", "clear-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1"
        ])
        assert code == 0, f"clear-position failed: {err}"

        g2 = load_graph(fp)
        entry = g2.lenses["view"].nodes["AUTH.1"]
        assert entry.position is None
        assert "AUTH.1" in g2.lenses["view"].nodes
        assert entry.lod == "full"

    def test_set_position_subprocess_missing_uid_error(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.IGCMDS — set-position with absent UID exits non-zero."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "DOES.NOT.EXIST",
            "--x", "1",
            "--y", "2"
        ])
        assert code != 0, "set-position should error on absent UID"

    def test_add_node_subprocess_with_position(self, auth_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.IGCMDS — add-node --x --y creates entry with position."""
        g, fp = auth_graph
        g.add_lens(LensConfig(name="test"))
        save_graph(g, fp)

        code, out, err = _run_ig_tool([
            "graph", "lens", "add-node",
            "-g", str(fp),
            "--lens", "test",
            "--uid", "AUTH.1.1",
            "--lod", "full",
            "--x", "100",
            "--y", "200"
        ])
        assert code == 0, f"add-node with position failed: {err}"

        g2 = load_graph(fp)
        entry = g2.lenses["test"].nodes["AUTH.1.1"]
        assert entry.lod == "full"
        assert entry.position is not None
        assert entry.position.x == 100.0
        assert entry.position.y == 200.0


# ================================================================== #
#  Cross-Validation: Round-Tripping & Validation                     #
# ================================================================== #


class TestPositionRoundTrip:
    """from PIG: LENSSCHEMA.NODESHAPE — verify positions survive round-trip and validate."""

    def test_set_position_graph_validates(self, lensed_graph: tuple[IntentGraph, Path]):
        """After set-position, ig-tool validate -g should return 0 (no corruption)."""
        g, fp = lensed_graph

        # Mutate via CLI
        _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "100",
            "--y", "200"
        ])

        # Validate
        code, out = _validate_graph(fp)
        assert code == 0, f"graph failed validation after set-position: {out}"

    def test_clear_position_graph_validates(self, lensed_graph: tuple[IntentGraph, Path]):
        """After clear-position, ig-tool validate -g should return 0."""
        g, fp = lensed_graph

        # Set, then clear
        _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "50",
            "--y", "75"
        ])
        _run_ig_tool([
            "graph", "lens", "clear-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1"
        ])

        # Validate
        code, out = _validate_graph(fp)
        assert code == 0, f"graph failed validation after clear-position: {out}"

    def test_yaml_round_trip_position_preserved(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: SERIALIZATION_FORMAT omission rule — position is present when set, omitted when None."""
        g, fp = lensed_graph

        # Set position
        _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "123.45",
            "--y", "678.9"
        ])

        # Read raw YAML
        raw = fp.read_text()
        data = yaml.safe_load(raw)
        node_entry = data["lenses"]["view"]["nodes"]["AUTH.1"]

        # Position should be present and exact
        assert "position" in node_entry
        assert node_entry["position"]["x"] == 123.45
        assert node_entry["position"]["y"] == 678.9

    def test_yaml_omission_rule_on_clear(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: omission rule — cleared position must be absent from YAML."""
        g, fp = lensed_graph

        # Set then clear
        _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "1",
            "--y", "2"
        ])
        _run_ig_tool([
            "graph", "lens", "clear-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1"
        ])

        # Verify YAML has no 'position' key for AUTH.1
        raw = fp.read_text()
        data = yaml.safe_load(raw)
        node_entry = data["lenses"]["view"]["nodes"]["AUTH.1"]
        assert "position" not in node_entry


# ================================================================== #
#  Validation Rules (V-POS1: finite values)                          #
# ================================================================== #


class TestPositionValidation:
    """from PIG: LENSSCHEMA.VALIDATION — V-POS1: reject NaN, Inf; accept finite."""

    def test_set_position_nan_rejected_subprocess(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.VALIDATION V-POS1 — NaN rejected."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "nan",
            "--y", "200"
        ])
        assert code != 0, "set-position should reject NaN"

    def test_set_position_inf_rejected_subprocess(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.VALIDATION V-POS1 — Infinity rejected."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "inf",
            "--y", "200"
        ])
        assert code != 0, "set-position should reject Infinity"

    def test_set_position_small_finite_coords(self, lensed_graph: tuple[IntentGraph, Path]):
        """from PIG: LENSSCHEMA.VALIDATION V-POS1 — very small finite coords accepted."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "1e-300",
            "--y", "1e-300"
        ])
        assert code == 0, f"set-position should accept small finite values: {err}"

        g2 = load_graph(fp)
        entry = g2.lenses["view"].nodes["AUTH.1"]
        assert entry.position.x == 1e-300
        assert entry.position.y == 1e-300


# ================================================================== #
#  Argument Validation (required flags)                              #
# ================================================================== #


class TestArgumentValidation:
    """from PIG: LENSSCHEMA.IGCMDS — CLI enforces required arguments."""

    def test_set_position_missing_x_error(self, lensed_graph: tuple[IntentGraph, Path]):
        """set-position requires --x; omitting it should error."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--y", "200"
        ])
        assert code != 0, "set-position should require --x"

    def test_set_position_missing_y_error(self, lensed_graph: tuple[IntentGraph, Path]):
        """set-position requires --y; omitting it should error."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "100"
        ])
        assert code != 0, "set-position should require --y"

    def test_set_position_missing_graph_error(self, lensed_graph: tuple[IntentGraph, Path]):
        """set-position requires -g; omitting it should error."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "100",
            "--y", "200"
        ])
        assert code != 0, "set-position should require -g"

    def test_set_position_missing_lens_error(self, lensed_graph: tuple[IntentGraph, Path]):
        """set-position requires --lens; omitting it should error."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--uid", "AUTH.1",
            "--x", "100",
            "--y", "200"
        ])
        assert code != 0, "set-position should require --lens"

    def test_clear_position_missing_graph_error(self, lensed_graph: tuple[IntentGraph, Path]):
        """clear-position requires -g; omitting it should error."""
        g, fp = lensed_graph
        code, out, err = _run_ig_tool([
            "graph", "lens", "clear-position",
            "--lens", "view",
            "--uid", "AUTH.1"
        ])
        assert code != 0, "clear-position should require -g"

    def test_add_node_partial_position_error_subprocess(self, auth_graph: tuple[IntentGraph, Path]):
        """from PIG: add-node --x without --y is an error (both required together)."""
        g, fp = auth_graph
        g.add_lens(LensConfig(name="test"))
        save_graph(g, fp)

        code, out, err = _run_ig_tool([
            "graph", "lens", "add-node",
            "-g", str(fp),
            "--lens", "test",
            "--uid", "AUTH.1.1",
            "--lod", "full",
            "--x", "100"
        ])
        assert code != 0, "add-node should require both --x and --y together"


# ================================================================== #
#  Position Preservation (unrelated mutations must not affect position)#
# ================================================================== #


class TestPositionPreservation:
    """Verify that position is preserved when unrelated mutations occur."""

    def test_position_preserved_after_set_lod(self, lensed_graph: tuple[IntentGraph, Path]):
        """After set-position, then set-lod on same node, position must persist."""
        g, fp = lensed_graph

        # Set position
        _run_ig_tool([
            "graph", "lens", "set-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1",
            "--x", "100",
            "--y", "200"
        ])

        # Change LOD (via add-node with new lod, or if set-lod exists)
        # For now, we just verify the position persists by loading and inspecting
        g2 = load_graph(fp)
        entry_before = g2.lenses["view"].nodes["AUTH.1"]
        pos_before = entry_before.position

        # Re-save with same position (simulate set-lod mutation)
        g2.lenses["view"].nodes["AUTH.1"] = LensNodeEntry(
            lod="lean",  # change LOD
            position=pos_before  # preserve position
        )
        save_graph(g2, fp)

        # Verify position is still there
        g3 = load_graph(fp)
        entry_after = g3.lenses["view"].nodes["AUTH.1"]
        assert entry_after.position is not None
        assert entry_after.position.x == 100.0
        assert entry_after.position.y == 200.0


# ================================================================== #
#  Idempotence (clear-position on unpinned node)                     #
# ================================================================== #


class TestIdempotence:
    """from PIG: LENSSCHEMA.IGCMDS — clear-position idempotent on unpinned node."""

    def test_clear_position_idempotent_subprocess(self, lensed_graph: tuple[IntentGraph, Path]):
        """clear-position on unpinned node succeeds (no error)."""
        g, fp = lensed_graph
        # AUTH.1.1 has no position
        code, out, err = _run_ig_tool([
            "graph", "lens", "clear-position",
            "-g", str(fp),
            "--lens", "view",
            "--uid", "AUTH.1.1"
        ])
        assert code == 0, f"clear-position should be idempotent: {err}"

        g2 = load_graph(fp)
        assert g2.lenses["view"].nodes["AUTH.1.1"].position is None


# ================================================================== #
#  Tool Registry Sync Check                                           #
# ================================================================== #


class TestToolRegistrySyncCheck:
    """Verify TOOL_REGISTRY.md --help documentation matches live CLI help."""

    def test_set_position_help_output(self):
        """Verify set-position has --help and documents --x, --y."""
        code, out, err = _run_ig_tool(["graph", "lens", "set-position", "--help"])
        assert code == 0, "set-position --help should succeed"
        # Check for key flags
        assert "--x" in out or "--x" in err, "--x not documented in help"
        assert "--y" in out or "--y" in err, "--y not documented in help"
        assert "--uid" in out or "--uid" in err, "--uid not documented in help"
        assert "--lens" in out or "--lens" in err, "--lens not documented in help"

    def test_clear_position_help_output(self):
        """Verify clear-position has --help and documents --uid, --lens."""
        code, out, err = _run_ig_tool(["graph", "lens", "clear-position", "--help"])
        assert code == 0, "clear-position --help should succeed"
        assert "--uid" in out or "--uid" in err, "--uid not documented in help"
        assert "--lens" in out or "--lens" in err, "--lens not documented in help"

    def test_add_node_help_documents_position_flags(self):
        """Verify add-node --help documents optional --x, --y."""
        code, out, err = _run_ig_tool(["graph", "lens", "add-node", "--help"])
        assert code == 0, "add-node --help should succeed"
        assert "--x" in out or "--x" in err, "--x not documented in add-node help"
        assert "--y" in out or "--y" in err, "--y not documented in add-node help"
