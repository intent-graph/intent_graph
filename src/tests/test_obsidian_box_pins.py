"""Feature 2 — whole-box pins + portal position pins (obsidian_layout).

End-to-end tests of the pin lifecycle across the portal engine (the primary
mode) and the shared machinery:

1. Detection — a human move/resize of a real canvas box is read back on the
   next export and recorded as ``data_registry.obsidian_layout.pinned``.
2. Honor — ``pinned ?? computed`` for every field; portal positions (x/y only)
   pin onto their L1 node's ``obsidian_layout.portal``.
3. Baseline — ``computed`` stores the box the export actually WROTE (post
   fit-height), so fit-height drift and a retracted pin's stale canvas are
   never mis-detected as human edits.
4. Retraction — delete the ``pinned`` block in the node's frontmatter, merge,
   re-export into the same vault: the node returns to computed layout.
5. Frames — pins are engine-scoped; switching engines drops them instead of
   misreading coordinates from another frame.
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
from intentgraph.obsidian._export import portal_node_id


# ------------------------------------------------------------------ #
#  Fixtures + helpers                                                 #
# ------------------------------------------------------------------ #

@pytest.fixture
def sample_graph() -> IntentGraph:
    """ROOT -> DISCOVER, PARSE ; PARSE has two leaves."""
    g = IntentGraph(meta={"name": "sample"})
    g.add_node("ROOT", "System", "top-level goal")
    for k in ("DISCOVER", "PARSE"):
        g.add_node_under(k, k.title(), f"{k} intent", parent_uid="ROOT")
    g.add_node_under("PARSE.1", "Lexer", "lexing intent", parent_uid="PARSE")
    g.add_node_under("PARSE.2", "Grammar", "grammar intent", parent_uid="PARSE")
    return g


def _canvas(vault: Path, name: str) -> dict:
    return json.loads((vault / "viz" / f"{name}.canvas").read_text())


def _canvas_node(vault: Path, canvas: str, node_id: str) -> dict:
    for n in _canvas(vault, canvas)["nodes"]:
        if n["id"] == node_id:
            return n
    raise AssertionError(f"{node_id} not in {canvas}.canvas")


def _edit_canvas_node(vault: Path, canvas: str, node_id: str, **fields) -> None:
    """Simulate a human move/resize: patch one node's box in a canvas file."""
    path = vault / "viz" / f"{canvas}.canvas"
    data = json.loads(path.read_text())
    for n in data["nodes"]:
        if n["id"] == node_id:
            n.update(fields)
            break
    else:
        raise AssertionError(f"{node_id} not in {canvas}.canvas")
    path.write_text(json.dumps(data, indent=4))


def _layout(graph: IntentGraph, uid: str) -> dict:
    return (graph.get_node(uid).data_registry or {}).get("obsidian_layout", {})


# ------------------------------------------------------------------ #
#  1+2. Detection + honor — portal engine                             #
# ------------------------------------------------------------------ #

class TestPortalBoxPins:
    def test_first_export_never_pins(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        for n in sample_graph.iter_nodes():
            block = _layout(sample_graph, n.uid)
            assert "pinned" not in block
            assert "pinned" not in (block.get("portal") or {})
            assert block.get("engine") == "portal"
            assert "computed" in block

    def test_branch_node_resize_survives_reexport(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        nid = file_node_id("PARSE.1")
        box = _canvas_node(vault, "L1_PARSE", nid)
        new_w, new_h = box["width"] + 300, box["height"] + 150
        _edit_canvas_node(vault, "L1_PARSE", nid, width=new_w, height=new_h)

        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        survived = _canvas_node(vault, "L1_PARSE", nid)
        assert (survived["width"], survived["height"]) == (new_w, new_h)
        assert _layout(sample_graph, "PARSE.1")["pinned"]["width"] == new_w

    def test_branch_node_move_survives_reexport(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        nid = file_node_id("PARSE.2")
        _edit_canvas_node(vault, "L1_PARSE", nid, x=7777, y=8888)

        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        survived = _canvas_node(vault, "L1_PARSE", nid)
        assert (survived["x"], survived["y"]) == (7777, 8888)

    def test_root_box_on_overview_pins(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        nid = file_node_id("ROOT")
        _edit_canvas_node(vault, "OVERVIEW", nid, x=-3000, y=-2500)

        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        survived = _canvas_node(vault, "OVERVIEW", nid)
        assert (survived["x"], survived["y"]) == (-3000, -2500)

    def test_pin_survives_export_to_new_vault(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        nid = file_node_id("PARSE.1")
        _edit_canvas_node(vault, "L1_PARSE", nid, x=4242)
        export_to_obsidian(sample_graph, vault, layout_engine="portal")

        # The pin lives in the graph — a brand-new vault honors it too.
        vault2 = tmp_path / "vault2"
        export_to_obsidian(sample_graph, vault2, layout_engine="portal")
        assert _canvas_node(vault2, "L1_PARSE", nid)["x"] == 4242

    def test_tolerance_rounding_delta_is_not_a_pin(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        nid = file_node_id("PARSE.1")
        box = _canvas_node(vault, "L1_PARSE", nid)
        _edit_canvas_node(vault, "L1_PARSE", nid, x=box["x"] + 1, y=box["y"] - 1)

        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        assert "pinned" not in _layout(sample_graph, "PARSE.1")


class TestPortalPositionPins:
    def test_portal_move_survives_reexport(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        pid = portal_node_id("PARSE")
        _edit_canvas_node(vault, "OVERVIEW", pid, x=12000, y=-9000)

        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        survived = _canvas_node(vault, "OVERVIEW", pid)
        assert (survived["x"], survived["y"]) == (12000, -9000)
        assert _layout(sample_graph, "PARSE")["portal"]["pinned"] == {
            "x": 12000, "y": -9000,
        }

    def test_portal_resize_is_ignored(self, tmp_path, sample_graph):
        # Portal size is plugin-forced to the content bbox: position-only pins.
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        pid = portal_node_id("PARSE")
        original = _canvas_node(vault, "OVERVIEW", pid)
        _edit_canvas_node(vault, "OVERVIEW", pid, width=original["width"] + 500)

        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        survived = _canvas_node(vault, "OVERVIEW", pid)
        assert survived["width"] == original["width"]
        assert "pinned" not in (_layout(sample_graph, "PARSE").get("portal") or {})


# ------------------------------------------------------------------ #
#  3. Baseline — computed = box as written; drift is invisible        #
# ------------------------------------------------------------------ #

class TestDriftGuard:
    def test_fit_height_drift_is_not_a_pin(self, tmp_path, sample_graph, monkeypatch):
        # Export with fit-height, then force the height model to recompute
        # differently (as a _FIT_* recalibration would). The untouched node
        # must NOT be mis-detected as a human resize.
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           fit_height=True)
        from intentgraph.obsidian import _export as ex
        monkeypatch.setattr(ex, "_FIT_BASE", ex._FIT_BASE + 40)

        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           fit_height=True)
        for uid in ("PARSE", "PARSE.1", "PARSE.2", "DISCOVER", "ROOT"):
            assert "pinned" not in _layout(sample_graph, uid), uid

        # And the new estimate was applied (the node was not frozen).
        nid = file_node_id("PARSE.1")
        box = _canvas_node(vault, "L1_PARSE", nid)
        stored = _layout(sample_graph, "PARSE.1")["computed"]
        assert stored["height"] == box["height"]

    def test_pinned_height_beats_fit_height(self, tmp_path, sample_graph):
        # fit-height must never undo a human resize.
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           fit_height=True)
        nid = file_node_id("PARSE.1")
        _edit_canvas_node(vault, "L1_PARSE", nid, height=999)

        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           fit_height=True)
        assert _canvas_node(vault, "L1_PARSE", nid)["height"] == 999


# ------------------------------------------------------------------ #
#  4. Retraction — delete the pinned frontmatter block, merge         #
# ------------------------------------------------------------------ #

def _delete_pinned_block(vault: Path, glob: str) -> None:
    """Simulate the retraction gesture: remove ``pinned:`` from frontmatter."""
    node_file = next((vault / "nodes").glob(glob))
    text = node_file.read_text()
    stripped = re.sub(r"\n    pinned:\n(?:      [^\n]*\n)+", "\n", text, count=1)
    assert stripped != text, "no pinned block found to delete"
    node_file.write_text(stripped)


class TestRetraction:
    def test_delete_pinned_then_merge_returns_to_computed(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           write_snapshot=True, graph_id="sample")
        nid = file_node_id("PARSE.1")
        original = dict(_canvas_node(vault, "L1_PARSE", nid))

        # Pin it via a canvas move + re-export.
        _edit_canvas_node(vault, "L1_PARSE", nid, x=5555)
        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           write_snapshot=True, graph_id="sample")
        assert _layout(sample_graph, "PARSE.1")["pinned"]["x"] == 5555

        # Retract: delete the pinned block in the node's frontmatter, merge.
        _delete_pinned_block(vault, "PARSE.1 *.md")
        merge_obsidian_into_graph(vault, sample_graph,
                                  snapshot=load_snapshot(vault))
        assert "pinned" not in _layout(sample_graph, "PARSE.1")

        # Re-export into the SAME vault: the stale canvas (still at the old
        # pin) must not re-pin — the node returns to computed layout.
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        back = _canvas_node(vault, "L1_PARSE", nid)
        assert back["x"] == original["x"]
        assert "pinned" not in _layout(sample_graph, "PARSE.1")

    def test_delete_portal_pinned_then_merge_returns_to_ring(self, tmp_path, sample_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           write_snapshot=True, graph_id="sample")
        pid = portal_node_id("PARSE")
        original = dict(_canvas_node(vault, "OVERVIEW", pid))

        _edit_canvas_node(vault, "OVERVIEW", pid, x=12000, y=-9000)
        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           write_snapshot=True, graph_id="sample")
        assert _layout(sample_graph, "PARSE")["portal"]["pinned"]["x"] == 12000

        node_file = next((vault / "nodes").glob("PARSE *.md"))
        text = node_file.read_text()
        stripped = re.sub(r"\n      pinned:\n(?:        [^\n]*\n)+", "\n",
                          text, count=1)
        assert stripped != text
        node_file.write_text(stripped)
        merge_obsidian_into_graph(vault, sample_graph,
                                  snapshot=load_snapshot(vault))
        assert "pinned" not in (_layout(sample_graph, "PARSE").get("portal") or {})

        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        back = _canvas_node(vault, "OVERVIEW", pid)
        assert (back["x"], back["y"]) == (original["x"], original["y"])


# ------------------------------------------------------------------ #
#  5. Round-trip + frames                                             #
# ------------------------------------------------------------------ #

class TestRoundTrip:
    def test_move_merge_reload_reexport_pin_holds(self, tmp_path, sample_graph):
        # move -> export (detect) -> merge -> serialize/reload -> re-export.
        from intentgraph.serial.json_yaml import graph_to_json, json_to_graph

        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           write_snapshot=True, graph_id="sample")
        nid = file_node_id("PARSE.1")
        _edit_canvas_node(vault, "L1_PARSE", nid, x=6060, y=7070)
        export_to_obsidian(sample_graph, vault, layout_engine="portal",
                           write_snapshot=True, graph_id="sample")

        merge_obsidian_into_graph(vault, sample_graph,
                                  snapshot=load_snapshot(vault))
        reloaded = json_to_graph(graph_to_json(sample_graph))
        assert _layout(reloaded, "PARSE.1")["pinned"]["x"] == 6060

        vault2 = tmp_path / "vault2"
        export_to_obsidian(reloaded, vault2, layout_engine="portal")
        survived = _canvas_node(vault2, "L1_PARSE", nid)
        assert (survived["x"], survived["y"]) == (6060, 7070)


class TestEngineFrames:
    def test_engine_switch_drops_foreign_frame_pins(self, tmp_path, sample_graph):
        # A portal-frame pin means nothing in radial coordinates: switching
        # engines drops the block instead of misreading it.
        vault = tmp_path / "vault"
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        nid = file_node_id("PARSE.1")
        _edit_canvas_node(vault, "L1_PARSE", nid, x=4242)
        export_to_obsidian(sample_graph, vault, layout_engine="portal")
        assert _layout(sample_graph, "PARSE.1")["pinned"]["x"] == 4242

        vault2 = tmp_path / "radial_vault"
        export_to_obsidian(sample_graph, vault2, layout_engine="radial")
        block = _layout(sample_graph, "PARSE.1")
        assert block["engine"] == "radial"
        assert "pinned" not in block
