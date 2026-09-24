"""Integration tests for radial layout through the Obsidian export pipeline.

Test strategy:
1. Persistence: radial export writes positions into data_registry.positions.
2. Global stability: a node has the same coordinates on every canvas it appears.
3. Radial edges auto-route (no fixed fromSide/toSide).
4. Pin override: a user-moved position survives merge + re-export.
5. Backward-compat: --layout grid (the default) is byte-identical to before,
   and never writes data_registry.positions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from intentgraph.models.graph import IntentGraph
from intentgraph.obsidian import (
    export_to_obsidian,
    load_snapshot,
    merge_obsidian_into_graph,
)
from intentgraph.obsidian._format import file_node_id


# ------------------------------------------------------------------ #
#  Fixtures                                                          #
# ------------------------------------------------------------------ #

@pytest.fixture
def sample_graph() -> IntentGraph:
    """ROOT -> DISCOVER, PARSE, ERRORS ; PARSE has two leaves; one intentlink."""
    g = IntentGraph(meta={"name": "sample"})
    g.add_node("ROOT", "System", "top-level goal")
    for k in ("DISCOVER", "PARSE", "ERRORS"):
        g.add_node_under(k, k.title(), f"{k} intent", parent_uid="ROOT")
    g.add_node_under("PARSE.1", "Lexer", "lexing intent", parent_uid="PARSE")
    g.add_node_under("PARSE.2", "Grammar", "grammar intent", parent_uid="PARSE")
    g.add_link("DISCOVER", "PARSE", "discovered files feed the parser")
    return g


def _canvas(vault: Path, name: str) -> dict:
    return json.loads((vault / "viz" / f"{name}.canvas").read_text())


# ------------------------------------------------------------------ #
#  Persistence + stability                                           #
# ------------------------------------------------------------------ #

class TestRadialPersistence:
    def test_layout_written_to_frontmatter(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="radial")
        node_file = next((vault / "nodes").glob("PARSE.1 *.md"))
        text = node_file.read_text()
        assert "data_registry:" in text
        assert "obsidian_layout:" in text
        assert "computed:" in text
        assert "engine: radial" in text

    def test_layout_written_onto_graph_object(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="radial")
        reg = sample_graph.get_node("PARSE.1").data_registry or {}
        block = reg.get("obsidian_layout", {})
        assert block.get("engine") == "radial"
        assert {"x", "y", "width", "height"} <= set(block.get("computed", {}))
        # No pin on a fresh export — computed only.
        assert "pinned" not in block

    def test_computed_matches_canvas_as_written(self, tmp_path, sample_graph):
        # The stored baseline is the box the export actually wrote to disk.
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="radial")
        ft = {n["id"]: n for n in _canvas(vault, "FULL_TREE")["nodes"]}
        box = ft[file_node_id("PARSE.1")]
        stored = sample_graph.get_node("PARSE.1").data_registry["obsidian_layout"]["computed"]
        assert (stored["x"], stored["y"], stored["width"], stored["height"]) == (
            box["x"], box["y"], box["width"], box["height"])

    def test_global_stability_same_coords_everywhere(self, tmp_path, sample_graph):
        # A node must sit at identical coordinates on the full-tree canvas and on
        # its parent's per-node canvas — the "one position everywhere" goal.
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="radial")
        nid = file_node_id("PARSE.1")
        ft = {n["id"]: (n["x"], n["y"]) for n in _canvas(vault, "FULL_TREE")["nodes"]}
        pc = {n["id"]: (n["x"], n["y"])
              for n in _canvas(vault, "PARSE")["nodes"] if n["type"] == "file"}
        assert ft[nid] == pc[nid]

    def test_root_centered(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="radial")
        ft = {n["id"]: n for n in _canvas(vault, "FULL_TREE")["nodes"]}
        root = ft[file_node_id("ROOT")]
        # Root box centre is the layout centre (0,0): top-left = -w/2, -h/2.
        assert root["x"] == -root["width"] // 2
        assert root["y"] == -root["height"] // 2


class TestRadialEdges:
    def test_treearc_edges_autoroute(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="radial")
        arcs = [e for e in _canvas(vault, "FULL_TREE")["edges"]
                if e["id"].startswith("arc_")]
        assert arcs
        for e in arcs:
            assert "fromSide" not in e and "toSide" not in e


# ------------------------------------------------------------------ #
#  Pin override                                                      #
# ------------------------------------------------------------------ #

class TestPinOverride:
    def test_canvas_move_detected_and_survives_reexport(self, tmp_path, sample_graph):
        # The primary pin gesture: a human drags a node on a canvas. The next
        # export reads the canvas back, records the move as a pin, and honors it.
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="radial")

        canvas_path = vault / "viz" / "FULL_TREE.canvas"
        canvas = json.loads(canvas_path.read_text())
        for n in canvas["nodes"]:
            if n["id"] == file_node_id("PARSE"):
                n["x"] = 99999
        canvas_path.write_text(json.dumps(canvas, indent=4))

        # Re-export into the SAME vault: detection pins, render honors.
        export_to_obsidian(sample_graph, vault, layout_engine="radial")
        ft = {n["id"]: n for n in _canvas(vault, "FULL_TREE")["nodes"]}
        assert ft[file_node_id("PARSE")]["x"] == 99999
        block = sample_graph.get_node("PARSE").data_registry["obsidian_layout"]
        assert block["pinned"]["x"] == 99999

        # And into a brand-new vault: the pin lives in the graph, not the vault.
        vault2 = tmp_path / "vault2"
        export_to_obsidian(sample_graph, vault2, layout_engine="radial")
        ft2 = {n["id"]: n for n in _canvas(vault2, "FULL_TREE")["nodes"]}
        assert ft2[file_node_id("PARSE")]["x"] == 99999

    def test_frontmatter_pin_survives_merge_and_reexport(self, tmp_path, sample_graph):
        # The frontmatter gesture: a human writes a pinned block in the node's
        # .md; merge carries it into the graph; re-export honors it.
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="radial",
                           write_snapshot=True, graph_id="sample")

        node_file = next((vault / "nodes").glob("PARSE *.md"))
        text = node_file.read_text()
        moved = re.sub(
            r"(obsidian_layout:\n)",
            "\\g<1>    pinned:\n      height: 560\n      width: 560\n"
            "      x: 99999\n      y: 1185\n",
            text,
            count=1,
        )
        assert "x: 99999" in moved
        node_file.write_text(moved)

        merge_obsidian_into_graph(vault, sample_graph, snapshot=load_snapshot(vault))
        block = sample_graph.get_node("PARSE").data_registry["obsidian_layout"]
        assert block["pinned"]["x"] == 99999

        vault2 = tmp_path / "vault2"
        export_to_obsidian(sample_graph, vault2, layout_engine="radial")
        ft = {n["id"]: n for n in _canvas(vault2, "FULL_TREE")["nodes"]}
        assert ft[file_node_id("PARSE")]["x"] == 99999


# ------------------------------------------------------------------ #
#  Backward compatibility                                            #
# ------------------------------------------------------------------ #

class TestGridUnchanged:
    def test_grid_default_writes_no_layout(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault)  # default engine = grid
        for node_file in (vault / "nodes").glob("*.md"):
            assert "obsidian_layout:" not in node_file.read_text()
        assert not any(
            (n.data_registry or {}).get("obsidian_layout")
            for n in sample_graph.iter_nodes()
        )

    def test_grid_output_byte_identical(self, tmp_path, sample_graph):
        # Explicit grid vs the previous default must be byte-for-byte equal.
        import copy
        g1 = copy.deepcopy(sample_graph)
        g2 = copy.deepcopy(sample_graph)
        v1 = tmp_path / "v1"
        v2 = tmp_path / "v2"
        export_to_obsidian(g1, v1)
        export_to_obsidian(g2, v2, layout_engine="grid")
        for name in ("FULL_TREE", "PARSE"):
            assert _canvas(v1, name) == _canvas(v2, name)
