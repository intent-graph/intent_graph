"""Tests for ig-tool lens internal subcommands.

Covers: list, show, create, delete, add-node, remove-node, set-lod,
add-link, remove-link, set-default, unset-default, project, reintegrate,
validate (lens-specific), set-position, clear-position.

These are integration tests that call cmd_lens() directly to avoid
subprocess overhead while still exercising the full dispatch path.
"""

from __future__ import annotations

import argparse
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


def _make_args(**kwargs: Any) -> argparse.Namespace:
    """Build a minimal Namespace for cmd_lens dispatch.

    Uses ``lens_file`` (not ``lens``) for the legacy -l agent-I/O file path,
    and ``lens_name`` for the --lens NAME internal-lens selector (H-B rename).
    """
    defaults = {
        "graph": None,
        "lens_file": None,   # legacy -l LENS_FILE path (H-B: was "lens")
        "lens_name": None,   # --lens NAME internal-lens selector
        "uid": None,
        "lod": None,
        "output": None,
        "input": None,
        "name": None,
        "description": None,
        "target": None,
        "budget": None,
        "scope_root": None,
        "depth": None,
        "x": None,
        "y": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _entry(lod: str, x: float | None = None, y: float | None = None) -> LensNodeEntry:
    """Helper: build a LensNodeEntry for use in fixtures."""
    pos = Position(x=x, y=y) if x is not None and y is not None else None
    return LensNodeEntry(lod=lod, position=pos)


# ================================================================== #
#  Fixtures                                                           #
# ================================================================== #


@pytest.fixture
def auth_graph(tmp_path: Path) -> tuple[IntentGraph, Path]:
    """Small auth graph saved to a temp file."""
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


# ================================================================== #
#  lens create + list                                                 #
# ================================================================== #


class TestLensCreateAndList:
    def test_create_empty_lens(self, auth_graph: tuple[IntentGraph, Path], capsys):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        args = _make_args(action="create", graph=str(fp), name="my-lens")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        assert "my-lens" in g2.lenses

    def test_list_shows_lenses(self, auth_graph: tuple[IntentGraph, Path], capsys):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        g.add_lens(LensConfig(name="lens-a"))
        g.add_lens(LensConfig(name="lens-b"))
        save_graph(g, fp)

        args = _make_args(action="list", graph=str(fp))
        cmd_graph_lens(args)
        out = capsys.readouterr().out
        assert "lens_count: 2" in out

    def test_delete_lens(self, auth_graph: tuple[IntentGraph, Path]):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        g.add_lens(LensConfig(name="to-delete"))
        save_graph(g, fp)

        args = _make_args(action="delete", graph=str(fp), lens_name="to-delete")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        assert "to-delete" not in g2.lenses


# ================================================================== #
#  add-node / remove-node / set-lod / add-link / remove-link          #
# ================================================================== #


class TestLensNodeLinkMutations:
    def test_add_node_ancestor_fill(self, auth_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS C1: add-node auto-inserts ancestors at skeleton."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        g.add_lens(LensConfig(name="test"))
        save_graph(g, fp)

        args = _make_args(action="add-node", graph=str(fp),
                          lens_name="test", uid="AUTH.1.1", lod="full")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        lc = g2.lenses["test"]
        assert "AUTH.1.1" in lc.nodes
        assert lc.nodes["AUTH.1.1"].lod == "full"
        assert lc.nodes["AUTH.1.1"].position is None
        assert "AUTH.1" in lc.nodes
        assert "AUTH" in lc.nodes
        assert "ROOT" in lc.nodes

    def test_remove_node_purges_descendants(self, auth_graph: tuple[IntentGraph, Path]):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        lc = LensConfig(
            name="test",
            nodes={
                "ROOT": _entry("skeleton"),
                "AUTH": _entry("lean"),
                "AUTH.1": _entry("full"),
                "AUTH.1.1": _entry("full"),
            },
            intentlinks=["AUTH.1_AUTH.1.1"],
        )
        g.add_lens(lc)
        save_graph(g, fp)

        args = _make_args(action="remove-node", graph=str(fp),
                          lens_name="test", uid="AUTH")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        lc2 = g2.lenses["test"]
        assert "AUTH" not in lc2.nodes
        assert "AUTH.1" not in lc2.nodes
        assert "AUTH.1.1" not in lc2.nodes
        assert "AUTH.1_AUTH.1.1" not in lc2.intentlinks

    def test_add_link_success(self, auth_graph: tuple[IntentGraph, Path]):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        lc = LensConfig(
            name="test",
            nodes={
                "ROOT": _entry("skeleton"),
                "AUTH": _entry("lean"),
                "AUTH.1": _entry("full"),
                "AUTH.1.1": _entry("full"),
            },
        )
        g.add_lens(lc)
        save_graph(g, fp)

        args = _make_args(action="add-link", graph=str(fp),
                          lens_name="test", uid="AUTH.1_AUTH.1.1")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        assert "AUTH.1_AUTH.1.1" in g2.lenses["test"].intentlinks

    def test_remove_link(self, auth_graph: tuple[IntentGraph, Path]):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        lc = LensConfig(
            name="test",
            nodes={
                "ROOT": _entry("skeleton"),
                "AUTH": _entry("lean"),
                "AUTH.1": _entry("full"),
                "AUTH.1.1": _entry("full"),
            },
            intentlinks=["AUTH.1_AUTH.1.1"],
        )
        g.add_lens(lc)
        save_graph(g, fp)

        args = _make_args(action="remove-link", graph=str(fp),
                          lens_name="test", uid="AUTH.1_AUTH.1.1")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        assert "AUTH.1_AUTH.1.1" not in g2.lenses["test"].intentlinks

    def test_set_lod_internal(self, auth_graph: tuple[IntentGraph, Path]):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        lc = LensConfig(name="test", nodes={
            "ROOT": _entry("skeleton"),
            "AUTH": _entry("lean"),
        })
        g.add_lens(lc)
        save_graph(g, fp)

        args = _make_args(action="set-lod", graph=str(fp),
                          lens_name="test", uid="AUTH", lod="full")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        assert g2.lenses["test"].nodes["AUTH"].lod == "full"


# ================================================================== #
#  set-default / unset-default                                        #
# ================================================================== #


class TestDefaultLens:
    def test_set_default(self, auth_graph: tuple[IntentGraph, Path]):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        g.add_lens(LensConfig(name="primary"))
        save_graph(g, fp)

        args = _make_args(action="set-default", graph=str(fp), lens_name="primary")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        assert g2.meta.get("default_lens") == "primary"

    def test_unset_default(self, auth_graph: tuple[IntentGraph, Path]):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        g.add_lens(LensConfig(name="primary"))
        g.meta["default_lens"] = "primary"
        save_graph(g, fp)

        args = _make_args(action="unset-default", graph=str(fp))
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        assert "default_lens" not in g2.meta


# ================================================================== #
#  project + reintegrate (AC16, AC17, AC18)                          #
# ================================================================== #


class TestProjectReintegrate:
    def _make_lensed_graph(self, fp: Path) -> IntentGraph:
        g = IntentGraph(meta={"name": "test"})
        g.add_node("ROOT", "Root", "Root")
        g.add_node_under("AUTH", "Auth", "Handles auth", parent_uid="ROOT")
        g.add_node_under("AUTH.1", "Creds", "Validates creds", parent_uid="AUTH")
        g.add_link("AUTH", "AUTH.1", "Auth delegates to creds")
        lc = LensConfig(
            name="auth-view",
            nodes={
                "ROOT": _entry("skeleton"),
                "AUTH": _entry("lean"),
                "AUTH.1": _entry("full"),
            },
            intentlinks=["AUTH_AUTH.1"],
        )
        g.add_lens(lc)
        save_graph(g, fp)
        return g

    def test_ac16_project_valid_ig(self, tmp_path: Path):
        """AC16: lens project produces a valid IG."""
        from ig_agents.cli_lens_commands import cmd_graph_lens
        from intentgraph.validation import validate_lenses

        source_fp = tmp_path / "source.ig.yaml"
        self._make_lensed_graph(source_fp)

        out_fp = tmp_path / "reduced.ig.yaml"
        args = _make_args(action="project", graph=str(source_fp),
                          lens_name="auth-view", output=str(out_fp))
        cmd_graph_lens(args)

        assert out_fp.exists()
        g2 = load_graph(out_fp)
        assert g2.meta.get("derived_from") is not None
        assert g2.meta["derived_from"]["via_lens"] == "auth-view"
        assert "ROOT" in g2.nodes
        assert "AUTH" in g2.nodes
        assert "AUTH.1" in g2.nodes
        assert "AUTH_AUTH.1" in g2.links
        # validate should pass
        issues = validate_lenses(g2)
        errors = [i for i in issues if i["severity"] == "error"]
        assert errors == []

    def test_ac17_reintegrate_content_edit(self, tmp_path: Path):
        """AC17: reintegrate applies content edits to parent."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        source_fp = tmp_path / "source.ig.yaml"
        self._make_lensed_graph(source_fp)

        out_fp = tmp_path / "reduced.ig.yaml"
        args = _make_args(action="project", graph=str(source_fp),
                          lens_name="auth-view", output=str(out_fp))
        cmd_graph_lens(args)

        # Modify the derived IG directly via the Python API
        reduced = load_graph(out_fp)
        reduced.update_node("AUTH.1", intent="Updated intent via reintegration")
        save_graph(reduced, out_fp)

        # Reintegrate
        parent_out_fp = tmp_path / "parent_updated.ig.yaml"
        args2 = _make_args(action="reintegrate", input=str(out_fp),
                           output=str(parent_out_fp))
        cmd_graph_lens(args2)

        parent = load_graph(parent_out_fp)
        assert parent.nodes["AUTH.1"].intent == "Updated intent via reintegration"

    def test_ac17_reintegrate_add_node(self, tmp_path: Path):
        """AC17: reintegrate adds new nodes from derived IG to parent."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        source_fp = tmp_path / "source.ig.yaml"
        self._make_lensed_graph(source_fp)

        out_fp = tmp_path / "reduced.ig.yaml"
        args = _make_args(action="project", graph=str(source_fp),
                          lens_name="auth-view", output=str(out_fp))
        cmd_graph_lens(args)

        # Add a new node to the derived IG
        reduced = load_graph(out_fp)
        reduced.add_node_under("AUTH.2", "MFA", "Multi-factor auth", parent_uid="AUTH")
        # Update the via_lens to include the new node
        reduced.lenses["auth-view"].nodes["AUTH.2"] = _entry("lean")
        save_graph(reduced, out_fp)

        parent_out_fp = tmp_path / "parent_updated.ig.yaml"
        args2 = _make_args(action="reintegrate", input=str(out_fp),
                           output=str(parent_out_fp))
        cmd_graph_lens(args2)

        parent = load_graph(parent_out_fp)
        assert "AUTH.2" in parent.nodes
        assert parent.nodes["AUTH.2"].name == "MFA"

    def test_ac17_reintegrate_add_link(self, tmp_path: Path):
        """AC17: reintegrate adds new links from derived IG to parent."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        source_fp = tmp_path / "source.ig.yaml"
        self._make_lensed_graph(source_fp)

        out_fp = tmp_path / "reduced.ig.yaml"
        args = _make_args(action="project", graph=str(source_fp),
                          lens_name="auth-view", output=str(out_fp))
        cmd_graph_lens(args)

        # Add a new link to the derived IG
        reduced = load_graph(out_fp)
        reduced.add_link("AUTH.1", "AUTH", "Feedback to auth orchestrator",
                         uid="AUTH.1_AUTH_feedback")
        reduced.lenses["auth-view"].intentlinks.append("AUTH.1_AUTH_feedback")
        save_graph(reduced, out_fp)

        parent_out_fp = tmp_path / "parent_updated.ig.yaml"
        args2 = _make_args(action="reintegrate", input=str(out_fp),
                           output=str(parent_out_fp))
        cmd_graph_lens(args2)

        parent = load_graph(parent_out_fp)
        assert "AUTH.1_AUTH_feedback" in parent.links

    def test_ac18_reintegrate_rejects_node_deletion(self, tmp_path: Path):
        """AC18: reintegrate errors on node deletion."""
        from ig_agents.cli_lens_commands import cmd_graph_lens
        import sys

        source_fp = tmp_path / "source.ig.yaml"
        self._make_lensed_graph(source_fp)

        out_fp = tmp_path / "reduced.ig.yaml"
        args = _make_args(action="project", graph=str(source_fp),
                          lens_name="auth-view", output=str(out_fp))
        cmd_graph_lens(args)

        # Remove AUTH.1 from derived IG to simulate deletion
        reduced = load_graph(out_fp)
        # Manually remove from underlying structure (bypass API safety)
        del reduced._nodes["AUTH.1"]
        reduced._nodes["AUTH"].children_uids = []
        # Remove from treearcs by saving/reloading with cleaned data
        save_graph(reduced, out_fp)

        parent_out_fp = tmp_path / "should_fail.ig.yaml"
        args2 = _make_args(action="reintegrate", input=str(out_fp),
                           output=str(parent_out_fp))

        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args2)
        assert exc_info.value.code == 1

    def test_ac18_reintegrate_rejects_reparenting(self, tmp_path: Path):
        """AC18: reintegrate errors on treearc reparenting."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        source_fp = tmp_path / "source.ig.yaml"
        self._make_lensed_graph(source_fp)

        out_fp = tmp_path / "reduced.ig.yaml"
        args = _make_args(action="project", graph=str(source_fp),
                          lens_name="auth-view", output=str(out_fp))
        cmd_graph_lens(args)

        # Reparent AUTH.1 under ROOT (instead of AUTH)
        reduced = load_graph(out_fp)
        # Bypass normal API to simulate reparenting
        reduced._nodes["AUTH.1"].parent_uid = "ROOT"
        reduced._nodes["AUTH"].children_uids = []
        reduced._nodes["ROOT"].children_uids.append("AUTH.1")
        save_graph(reduced, out_fp)

        parent_out_fp = tmp_path / "should_fail.ig.yaml"
        args2 = _make_args(action="reintegrate", input=str(out_fp),
                           output=str(parent_out_fp))

        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args2)
        assert exc_info.value.code == 1

    def test_coordinated_deletion_bypass_is_rejected(self, tmp_path: Path):
        """H-A regression: coordinated deletion (node removed from BOTH derived nodes
        list AND the embedded lens dict) must be caught by comparing against the
        *parent* lens node set, not the (now-edited) derived lens node set.

        E5 tester finding: prior to fix, this scenario would silently succeed.
        """
        from ig_agents.cli_lens_commands import cmd_graph_lens

        source_fp = tmp_path / "source.ig.yaml"
        self._make_lensed_graph(source_fp)

        out_fp = tmp_path / "reduced.ig.yaml"
        args = _make_args(action="project", graph=str(source_fp),
                          lens_name="auth-view", output=str(out_fp))
        cmd_graph_lens(args)

        # Coordinated deletion: remove AUTH.1 from BOTH the derived nodes list
        # AND the embedded lens dict — the bypass scenario.
        reduced = load_graph(out_fp)
        # Remove from nodes structure
        del reduced._nodes["AUTH.1"]
        reduced._nodes["AUTH"].children_uids = []
        # Also remove from the embedded lens config (the bypass path)
        del reduced.lenses["auth-view"].nodes["AUTH.1"]
        # Remove any intentlinks that referenced AUTH.1
        reduced.lenses["auth-view"].intentlinks = [
            luid for luid in reduced.lenses["auth-view"].intentlinks
            if "AUTH.1" not in luid
        ]
        save_graph(reduced, out_fp)

        parent_out_fp = tmp_path / "should_fail.ig.yaml"
        args2 = _make_args(action="reintegrate", input=str(out_fp),
                           output=str(parent_out_fp))

        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args2)
        assert exc_info.value.code == 1


# ================================================================== #
#  lens validate                                                      #
# ================================================================== #


class TestLensValidateCLI:
    def test_validate_clean_lens_ok(self, auth_graph: tuple[IntentGraph, Path], capsys):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        lc = LensConfig(
            name="good",
            nodes={
                "ROOT": _entry("skeleton"),
                "AUTH": _entry("lean"),
                "AUTH.1": _entry("full"),
                "AUTH.1.1": _entry("full"),
            },
            intentlinks=["AUTH.1_AUTH.1.1"],
        )
        g.add_lens(lc)
        save_graph(g, fp)

        args = _make_args(action="validate", graph=str(fp))
        cmd_graph_lens(args)
        out = capsys.readouterr().out
        assert "status: ok" in out

    def test_validate_broken_lens_exits_1(
        self, auth_graph: tuple[IntentGraph, Path]
    ):
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        # V-L1: reference non-existent node
        lc = LensConfig(name="bad", nodes={"NONEXISTENT": _entry("full")})
        g.add_lens(lc)
        save_graph(g, fp)

        args = _make_args(action="validate", graph=str(fp))
        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args)
        assert exc_info.value.code == 1


# ================================================================== #
#  set-position / clear-position / add-node with position             #
# ================================================================== #
# All assertions in this section derive from PIG LENSSCHEMA.IGCMDS   #
# and LENSSCHEMA.VALIDATION constraints.                               #


class TestPositionCommands:
    """PIG LENSSCHEMA.IGCMDS: set-position, clear-position, add-node --x/--y."""

    @pytest.fixture
    def lensed_graph(self, auth_graph: tuple[IntentGraph, Path]) -> tuple[IntentGraph, Path]:
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

    # ---- set-position ----

    def test_set_position_sets_position(self, lensed_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: set-position sets x, y on an existing node entry."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        args = _make_args(action="set-position", graph=str(fp),
                          lens_name="view", uid="AUTH.1", x=100.0, y=200.0)
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        entry = g2.lenses["view"].nodes["AUTH.1"]
        assert entry.position is not None
        assert entry.position.x == 100.0
        assert entry.position.y == 200.0
        # LOD must be preserved (set-lod must not alter position, and vice versa)
        assert entry.lod == "full"

    def test_set_position_overwrites_existing(self, lensed_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: set-position overwrites a previous position."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        # Set initial position
        args1 = _make_args(action="set-position", graph=str(fp),
                           lens_name="view", uid="AUTH.1", x=10.0, y=20.0)
        cmd_graph_lens(args1)
        # Overwrite
        args2 = _make_args(action="set-position", graph=str(fp),
                           lens_name="view", uid="AUTH.1", x=99.5, y=88.0)
        cmd_graph_lens(args2)

        g2 = load_graph(fp)
        entry = g2.lenses["view"].nodes["AUTH.1"]
        assert entry.position.x == 99.5
        assert entry.position.y == 88.0

    def test_set_position_nan_rejected(self, lensed_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.VALIDATION V-POS1: NaN rejected at CLI layer."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        args = _make_args(action="set-position", graph=str(fp),
                          lens_name="view", uid="AUTH.1",
                          x=float("nan"), y=200.0)
        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args)
        assert exc_info.value.code == 1

    def test_set_position_inf_rejected(self, lensed_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.VALIDATION V-POS1: Infinity rejected at CLI layer."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        args = _make_args(action="set-position", graph=str(fp),
                          lens_name="view", uid="AUTH.1",
                          x=float("inf"), y=200.0)
        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args)
        assert exc_info.value.code == 1

    def test_set_position_nonexistent_uid_error(self, lensed_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: set-position on UID not in lens raises error."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        args = _make_args(action="set-position", graph=str(fp),
                          lens_name="view", uid="DOES.NOT.EXIST",
                          x=1.0, y=2.0)
        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args)
        assert exc_info.value.code == 1

    # ---- clear-position ----

    def test_clear_position_removes_position(self, lensed_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: clear-position removes the position field."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        # First set a position
        args1 = _make_args(action="set-position", graph=str(fp),
                           lens_name="view", uid="AUTH.1", x=50.0, y=75.0)
        cmd_graph_lens(args1)

        # Now clear it
        args2 = _make_args(action="clear-position", graph=str(fp),
                           lens_name="view", uid="AUTH.1")
        cmd_graph_lens(args2)

        g2 = load_graph(fp)
        entry = g2.lenses["view"].nodes["AUTH.1"]
        # Position must be absent (None) — per omission rule, key omitted in YAML
        assert entry.position is None
        # Node entry must still exist (clear-position does NOT remove the node)
        assert "AUTH.1" in g2.lenses["view"].nodes
        # LOD preserved
        assert entry.lod == "full"

    def test_clear_position_idempotent(self, lensed_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: clear-position on unpinned node is a no-op (idempotent)."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        # AUTH.1.1 has no position — clearing is a no-op
        args = _make_args(action="clear-position", graph=str(fp),
                          lens_name="view", uid="AUTH.1.1")
        cmd_graph_lens(args)  # must not raise

        g2 = load_graph(fp)
        assert g2.lenses["view"].nodes["AUTH.1.1"].position is None

    def test_clear_position_omitted_in_yaml(self, lensed_graph: tuple[IntentGraph, Path]):
        """Serialization omission rule: cleared position must be absent from YAML output."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        # Pin then unpin AUTH.1
        cmd_graph_lens(_make_args(action="set-position", graph=str(fp),
                            lens_name="view", uid="AUTH.1", x=1.0, y=2.0))
        cmd_graph_lens(_make_args(action="clear-position", graph=str(fp),
                            lens_name="view", uid="AUTH.1"))

        raw = fp.read_text()
        # The 'position' key must not appear anywhere for AUTH.1
        # (exclude_none serialization ensures this)
        data = yaml.safe_load(raw)
        node_entry = data["lenses"]["view"]["nodes"]["AUTH.1"]
        assert "position" not in node_entry

    def test_clear_position_nonexistent_uid_error(self, lensed_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: clear-position on UID not in lens raises error."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = lensed_graph
        args = _make_args(action="clear-position", graph=str(fp),
                          lens_name="view", uid="DOES.NOT.EXIST")
        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args)
        assert exc_info.value.code == 1

    # ---- add-node with position ----

    def test_add_node_with_position(self, auth_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: add-node with --x --y creates entry with position."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        g.add_lens(LensConfig(name="test"))
        save_graph(g, fp)

        args = _make_args(action="add-node", graph=str(fp),
                          lens_name="test", uid="AUTH.1.1", lod="full",
                          x=100.0, y=200.0)
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        entry = g2.lenses["test"].nodes["AUTH.1.1"]
        assert entry.lod == "full"
        assert entry.position is not None
        assert entry.position.x == 100.0
        assert entry.position.y == 200.0

    def test_add_node_without_position_unchanged(self, auth_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: add-node without --x/--y → position is None (existing behavior)."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        g.add_lens(LensConfig(name="test"))
        save_graph(g, fp)

        args = _make_args(action="add-node", graph=str(fp),
                          lens_name="test", uid="AUTH.1.1", lod="full")
        cmd_graph_lens(args)

        g2 = load_graph(fp)
        entry = g2.lenses["test"].nodes["AUTH.1.1"]
        assert entry.lod == "full"
        assert entry.position is None

    def test_add_node_partial_position_error(self, auth_graph: tuple[IntentGraph, Path]):
        """PIG LENSSCHEMA.IGCMDS: providing only --x without --y is an error."""
        from ig_agents.cli_lens_commands import cmd_graph_lens

        g, fp = auth_graph
        g.add_lens(LensConfig(name="test"))
        save_graph(g, fp)

        args = _make_args(action="add-node", graph=str(fp),
                          lens_name="test", uid="AUTH.1.1", lod="full",
                          x=100.0)  # y missing
        with pytest.raises(SystemExit) as exc_info:
            cmd_graph_lens(args)
        assert exc_info.value.code == 1
