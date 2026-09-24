"""Tests for --nav-links modes, --fit-height, and treearc-based round-trip.

Test strategy:
1. nav-links minimal (default): only L1 nodes get UP; nothing else.
2. nav-links full: UP/DOWN/CONTAINS restored.
3. nav-links none: no navigation lines at all.
4. Tree round-trips from edges.yaml treearcs regardless of nav mode (the
   structural fix that lets minimal be the default without breaking import).
5. fit-height: file-nodes get a shorter, content-estimated pixel height
   (frontmatter estimate + Pillow-measured body images); groups/portals
   untouched; off by default.
"""

from __future__ import annotations

import json

import pytest

from intentgraph.models.graph import IntentGraph
from intentgraph.obsidian import export_to_obsidian, import_from_obsidian


@pytest.fixture
def three_level() -> IntentGraph:
    """ROOT -> A,B ; A -> A.1 -> A.1.1 (so there are L1, L2, L3 nodes)."""
    g = IntentGraph(meta={"name": "three"})
    g.add_node("ROOT", "System", "top goal")
    g.add_node_under("A", "Alpha", "alpha intent", parent_uid="ROOT")
    g.add_node_under("B", "Beta", "beta intent", parent_uid="ROOT")
    g.add_node_under("A.1", "Alpha One", "a1 intent", parent_uid="A")
    g.add_node_under("A.1.1", "Alpha One One", "a11 intent", parent_uid="A.1")
    return g


def _nav_of(vault, glob_pat: str) -> str:
    return next((vault / "nodes").glob(glob_pat)).read_text()


# ------------------------------------------------------------------ #
#  nav-links modes                                                   #
# ------------------------------------------------------------------ #

class TestNavLinksMinimal:
    def test_only_l1_gets_up(self, tmp_path, three_level):
        vault = tmp_path / "v"
        export_to_obsidian(three_level, vault)  # default minimal
        # L1 nodes (A, B): UP only.
        for uid, name in (("A", "Alpha"), ("B", "Beta")):
            md = _nav_of(vault, f"{uid} *.md")
            assert "UP:" in md
            assert "DOWN:" not in md and "CONTAINS:" not in md
        # ROOT and deeper nodes: no nav at all.
        assert "UP:" not in _nav_of(vault, "ROOT *.md")
        assert "UP:" not in _nav_of(vault, "A.1 *.md")
        assert "UP:" not in _nav_of(vault, "A.1.1 *.md")


class TestNavLinksFull:
    def test_full_restores_all(self, tmp_path, three_level):
        vault = tmp_path / "v"
        export_to_obsidian(three_level, vault, nav_links="full")
        root = _nav_of(vault, "ROOT *.md")
        assert "DOWN:" in root and "CONTAINS:" in root
        a = _nav_of(vault, "A *.md")
        assert "UP:" in a and "DOWN:" in a and "CONTAINS:" in a
        deep = _nav_of(vault, "A.1.1 *.md")  # leaf: UP only
        assert "UP:" in deep and "DOWN:" not in deep


class TestNavLinksNone:
    def test_none_strips_everything(self, tmp_path, three_level):
        vault = tmp_path / "v"
        export_to_obsidian(three_level, vault, nav_links="none")
        for pat in ("ROOT *.md", "A *.md", "B *.md", "A.1 *.md", "A.1.1 *.md"):
            md = _nav_of(vault, pat)
            assert "UP:" not in md and "DOWN:" not in md and "CONTAINS:" not in md


# ------------------------------------------------------------------ #
#  Tree round-trips from treearcs regardless of nav mode             #
# ------------------------------------------------------------------ #

class TestTreearcRoundTrip:
    @pytest.mark.parametrize("nav", ["minimal", "full", "none"])
    def test_tree_reconstructs_from_edges_yaml(self, tmp_path, three_level, nav):
        vault = tmp_path / "v"
        export_to_obsidian(three_level, vault, nav_links=nav)
        imported = import_from_obsidian(vault)
        assert set(imported.get_node("ROOT").children_uids) == {"A", "B"}
        assert set(imported.get_node("A").children_uids) == {"A.1"}
        assert imported.get_node("A.1.1").parent_uid == "A.1"

    def test_edges_yaml_has_treearcs(self, tmp_path, three_level):
        import yaml
        vault = tmp_path / "v"
        export_to_obsidian(three_level, vault, nav_links="none")
        edges = yaml.safe_load((vault / "edges.yaml").read_text())
        arcs = {(e["from"], e["to"]) for e in edges if e.get("type") == "treearc"}
        # Even with NO nav links, the full tree is recorded as treearcs.
        assert arcs == {("ROOT", "A"), ("ROOT", "B"), ("A", "A.1"), ("A.1", "A.1.1")}


# ------------------------------------------------------------------ #
#  fit-height                                                        #
# ------------------------------------------------------------------ #

class TestFitHeight:
    def test_off_by_default_keeps_generator_height(self, tmp_path, three_level):
        vault = tmp_path / "v"
        export_to_obsidian(three_level, vault)  # no fit_height
        canvas = json.loads((vault / "viz" / "FULL_TREE.canvas").read_text())
        file_nodes = [n for n in canvas["nodes"] if n["type"] == "file"]
        assert file_nodes
        # Without fit, nodes keep the generator's fixed tall height.
        assert all(n["height"] == 650 for n in file_nodes)

    def test_fit_shrinks_height_to_content(self, tmp_path, three_level):
        # --fit-height replaces the fixed 650 with a content-fitted, shorter box.
        vault = tmp_path / "v"
        export_to_obsidian(three_level, vault, fit_height=True)
        canvas = json.loads((vault / "viz" / "FULL_TREE.canvas").read_text())
        file_nodes = [n for n in canvas["nodes"] if n["type"] == "file"]
        assert file_nodes
        for n in file_nodes:
            assert n["height"] < 650      # shorter than the fixed default
            assert n["height"] >= 120     # but not degenerate

    def test_taller_content_gets_taller_box(self, tmp_path):
        # A node with more field content must be sized taller than a sparse one.
        g = IntentGraph(meta={"name": "h"})
        g.add_node("ROOT", "Root", "top")
        g.add_node_under("SHORT", "Short", "brief.", parent_uid="ROOT")
        g.add_node_under(
            "LONG", "Long", "x" * 140, parent_uid="ROOT",
            epistemic_state="y" * 140, design_notes="z" * 140,
            examples=["a" * 200, "b" * 200],
        )
        vault = tmp_path / "v"
        export_to_obsidian(g, vault, fit_height=True)
        canvas = json.loads((vault / "viz" / "FULL_TREE.canvas").read_text())
        h = {n["file"].split("/")[-1].split(" ")[0]: n["height"]
             for n in canvas["nodes"] if n["type"] == "file"}
        assert h["LONG"] > h["SHORT"]

    def test_portal_root_fitted_portals_untouched(self, tmp_path, three_level):
        vault = tmp_path / "v"
        export_to_obsidian(three_level, vault, layout_engine="portal", fit_height=True)
        ov = json.loads((vault / "viz" / "OVERVIEW.canvas").read_text())
        root = [n for n in ov["nodes"] if not n.get("portal")][0]
        portals = [n for n in ov["nodes"] if n.get("portal")]
        assert root["height"] < 650                    # ROOT is a real node -> fitted
        assert all(p["height"] > 650 for p in portals)  # portals sized to subtree bbox
