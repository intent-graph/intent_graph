"""Integration tests for the portal (nested) Obsidian layout.

Test strategy:
1. Structure: portal export writes one L1_{uid}.canvas per branch + OVERVIEW.
2. OVERVIEW: ROOT file-node at centre + one portal per L1 (portal:true), no
   overlap, ROOT->portal edges.
3. L1 canvas: a vertical tree of exactly one branch (L1 + descendants).
4. Navigation: no UP/DOWN wiki-link points at a canvas that doesn't exist
   (the dangling-link regression).
5. Grid/radial navigation is unaffected.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from intentgraph.models.graph import IntentGraph
from intentgraph.obsidian import export_to_obsidian
from intentgraph.obsidian._format import file_node_id


@pytest.fixture
def branchy_graph() -> IntentGraph:
    """ROOT with 3 L1 branches of differing width/depth."""
    g = IntentGraph(meta={"name": "branchy"})
    g.add_node("ROOT", "System", "top-level goal")
    for k in ("ALPHA", "BETA", "GAMMA"):
        g.add_node_under(k, k.title(), f"{k} intent", parent_uid="ROOT")
    for i in (1, 2, 3, 4):
        g.add_node_under(f"ALPHA.{i}", f"A{i}", "leaf", parent_uid="ALPHA")
    g.add_node_under("BETA.1", "B1", "leaf", parent_uid="BETA")
    g.add_node_under("BETA.1.1", "B11", "deep leaf", parent_uid="BETA.1")
    return g


def _viz(vault: Path, name: str) -> dict:
    return json.loads((vault / "viz" / f"{name}.canvas").read_text())


# ------------------------------------------------------------------ #
#  Structure                                                         #
# ------------------------------------------------------------------ #

class TestPortalStructure:
    def test_writes_overview_and_l1_canvases(self, tmp_path, branchy_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, layout_engine="portal")
        viz = vault / "viz"
        assert (viz / "OVERVIEW.canvas").exists()
        for l1 in ("ALPHA", "BETA", "GAMMA"):
            assert (viz / f"L1_{l1}.canvas").exists()
        # Portal mode does NOT write per-node or FULL_TREE canvases.
        assert not (viz / "FULL_TREE.canvas").exists()
        assert not (viz / "ALPHA.canvas").exists()

    def test_overview_has_root_and_portals(self, tmp_path, branchy_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, layout_engine="portal")
        ov = _viz(vault, "OVERVIEW")
        portals = [n for n in ov["nodes"] if n.get("portal")]
        non_portals = [n for n in ov["nodes"] if not n.get("portal")]
        assert len(portals) == 3
        assert len(non_portals) == 1  # ROOT
        assert non_portals[0]["id"] == file_node_id("ROOT")
        # Every portal embeds an L1 canvas and carries portal:true.
        for p in portals:
            assert p["portal"] is True
            assert p["file"].endswith(".canvas")
            assert "L1_" in p["file"]
        # One ROOT->portal edge per branch.
        assert len(ov["edges"]) == 3

    def test_portals_do_not_overlap(self, tmp_path, branchy_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, layout_engine="portal")
        portals = [n for n in _viz(vault, "OVERVIEW")["nodes"] if n.get("portal")]

        def overlap(a, b) -> bool:
            return not (
                a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
            )

        for i in range(len(portals)):
            for j in range(i + 1, len(portals)):
                assert not overlap(portals[i], portals[j])

    def test_l1_canvas_contains_only_its_branch(self, tmp_path, branchy_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, layout_engine="portal")
        beta = _viz(vault, "L1_BETA")
        files = {n["file"] for n in beta["nodes"]}
        # BETA + BETA.1 + BETA.1.1, and nothing from other branches.
        assert any("BETA.1.1" in f for f in files)
        assert all("ALPHA" not in f and "GAMMA" not in f for f in files)
        # Content is a vertical tree: edges route bottom -> top.
        assert beta["edges"]
        assert all(e.get("fromSide") == "bottom" and e.get("toSide") == "top"
                   for e in beta["edges"])


# ------------------------------------------------------------------ #
#  Navigation (dangling-link regression)                             #
# ------------------------------------------------------------------ #

class TestPortalNavigation:
    def _canvas_link_targets(self, vault: Path) -> set[str]:
        targets: set[str] = set()
        for md in (vault / "nodes").glob("*.md"):
            for m in re.finditer(r"\[\[([^\]|]+\.canvas)", md.read_text()):
                targets.add(m.group(1))
        return targets

    def test_no_dangling_canvas_links(self, tmp_path, branchy_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, layout_engine="portal")
        for target in self._canvas_link_targets(vault):
            assert (vault / "viz" / target).exists(), f"dangling link: {target}"

    def test_root_down_points_to_overview(self, tmp_path, branchy_graph):
        # Engine-aware DOWN target is a full-nav concern.
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, layout_engine="portal", nav_links="full")
        root_md = next((vault / "nodes").glob("ROOT *.md")).read_text()
        assert "DOWN: [[OVERVIEW.canvas|EXPLODE]]" in root_md

    def test_l1_up_is_overview_down_is_branch(self, tmp_path, branchy_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, layout_engine="portal", nav_links="full")
        alpha_md = next((vault / "nodes").glob("ALPHA *.md")).read_text()
        assert "UP: [[OVERVIEW.canvas|OVERVIEW]]" in alpha_md
        assert "DOWN: [[L1_ALPHA.canvas|EXPLODE]]" in alpha_md

    def test_deep_node_up_is_its_branch(self, tmp_path, branchy_graph):
        # Full nav so a deep (non-L1) node still gets an UP link to assert on.
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, layout_engine="portal", nav_links="full")
        deep_md = next((vault / "nodes").glob("BETA.1.1 *.md")).read_text()
        assert "UP: [[L1_BETA.canvas|BETA]]" in deep_md


# ------------------------------------------------------------------ #
#  Other engines unaffected                                          #
# ------------------------------------------------------------------ #

class TestOtherEnginesUnaffected:
    def test_grid_still_uses_per_node_canvases(self, tmp_path, branchy_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(branchy_graph, vault, nav_links="full")  # default grid engine
        assert (vault / "viz" / "FULL_TREE.canvas").exists()
        assert (vault / "viz" / "ALPHA.canvas").exists()
        assert not (vault / "viz" / "OVERVIEW.canvas").exists()
        root_md = next((vault / "nodes").glob("ROOT *.md")).read_text()
        assert "DOWN: [[ROOT.canvas|EXPLODE]]" in root_md
