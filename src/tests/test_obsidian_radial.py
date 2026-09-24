"""Tests for the global radial Canvas layout (intentgraph.obsidian._radial).

Test strategy:
1. Geometry: root at centre; children fan onto rings by depth.
2. Non-overlap: a crowded ring seats its nodes without collision.
3. Angular budget: few L1 branches don't sprawl; >8 spill toward a full circle.
4. Wedge weighting: a bushy subtree earns a wider wedge than a sparse sibling.
5. Determinism: identical output regardless of child insertion order.
6. Edge cases: single node, deep narrow chain.
"""

from __future__ import annotations

import itertools
import math

import pytest

from intentgraph.models.graph import IntentGraph
from intentgraph.obsidian._radial import RadialConfig, compute_radial_layout

CFG = RadialConfig()


# ------------------------------------------------------------------ #
#  Helpers                                                           #
# ------------------------------------------------------------------ #

def _center(nl, cfg: RadialConfig = CFG) -> tuple[float, float]:
    """Recover a node's centre point from its top-left NodeLayout box."""
    return (nl.x + cfg.node_width / 2.0, nl.y + cfg.node_height / 2.0)


def _angle_deg(nl, cfg: RadialConfig = CFG) -> float:
    cx, cy = _center(nl, cfg)
    return math.degrees(math.atan2(cy - cfg.center_y, cx - cfg.center_x))


def _radius(nl, cfg: RadialConfig = CFG) -> float:
    cx, cy = _center(nl, cfg)
    return math.hypot(cx - cfg.center_x, cy - cfg.center_y)


def _star_graph(n: int) -> IntentGraph:
    """ROOT with *n* leaf children."""
    g = IntentGraph(meta={"name": "star"})
    g.add_node("ROOT", "Root", "root intent")
    for i in range(n):
        g.add_node_under(f"N{i:02}", f"N{i}", "leaf intent", parent_uid="ROOT")
    return g


# ------------------------------------------------------------------ #
#  Fixtures                                                          #
# ------------------------------------------------------------------ #

@pytest.fixture
def single_node() -> IntentGraph:
    g = IntentGraph(meta={"name": "single"})
    g.add_node("ROOT", "Root", "the only node")
    return g


@pytest.fixture
def bushy_graph() -> IntentGraph:
    """ROOT -> A,B,C,D ; A has three leaves (so A's subtree is bushier)."""
    g = IntentGraph(meta={"name": "bushy"})
    g.add_node("ROOT", "Root", "root intent")
    for k in ("A", "B", "C", "D"):
        g.add_node_under(k, k, f"{k} intent", parent_uid="ROOT")
    for i in (1, 2, 3):
        g.add_node_under(f"A.{i}", f"A{i}", "leaf intent", parent_uid="A")
    return g


@pytest.fixture
def chain_graph() -> IntentGraph:
    """ROOT -> C -> C.1 -> C.1.1 (deep narrow chain)."""
    g = IntentGraph(meta={"name": "chain"})
    g.add_node("ROOT", "Root", "root intent")
    g.add_node_under("C", "C", "c intent", parent_uid="ROOT")
    g.add_node_under("C.1", "C1", "c1 intent", parent_uid="C")
    g.add_node_under("C.1.1", "C11", "c11 intent", parent_uid="C.1")
    return g


# ------------------------------------------------------------------ #
#  Tests                                                             #
# ------------------------------------------------------------------ #

class TestRadialGeometry:
    def test_root_at_center(self, bushy_graph):
        pos = compute_radial_layout(bushy_graph)
        cx, cy = _center(pos["ROOT"])
        assert (cx, cy) == pytest.approx((CFG.center_x, CFG.center_y))

    def test_children_on_outer_ring(self, bushy_graph):
        pos = compute_radial_layout(bushy_graph)
        r_root = _radius(pos["ROOT"])
        r_l1 = _radius(pos["A"])
        r_l2 = _radius(pos["A.1"])
        assert r_root == pytest.approx(0.0, abs=1.0)
        assert r_l1 > r_root
        assert r_l2 > r_l1  # deeper => further out

    def test_covers_every_node(self, bushy_graph):
        pos = compute_radial_layout(bushy_graph)
        assert set(pos) == {n.uid for n in bushy_graph.iter_nodes()}

    def test_integer_coordinates(self, bushy_graph):
        pos = compute_radial_layout(bushy_graph)
        for nl in pos.values():
            assert isinstance(nl.x, int) and isinstance(nl.y, int)


class TestNonOverlap:
    def test_wide_fanout_no_overlap(self):
        pos = compute_radial_layout(_star_graph(20))
        boxes = [nl for uid, nl in pos.items() if uid != "ROOT"]
        min_dist = min(
            math.hypot(a.x - b.x, a.y - b.y)
            for a, b in itertools.combinations(boxes, 2)
        )
        assert min_dist > CFG.node_width  # centres farther apart than a node is wide


class TestAngularBudget:
    def test_small_fanout_does_not_sprawl(self):
        # 2 L1 nodes must not span the whole 180-degree sweep; each gets <= max_wedge.
        pos = compute_radial_layout(_star_graph(2))
        a0 = _angle_deg(pos["N00"])
        a1 = _angle_deg(pos["N01"])
        assert abs(a0 - a1) <= 2 * CFG.max_wedge_deg + 1e-6

    def test_many_l1_spill_beyond_half_circle(self):
        # >8 L1 nodes spill past 180 toward a full circle.
        pos = compute_radial_layout(_star_graph(16))
        angles = sorted(_angle_deg(nl) for uid, nl in pos.items() if uid != "ROOT")
        span = angles[-1] - angles[0]
        assert span > 180.0


class TestWedgeWeighting:
    def test_bushy_subtree_gets_wider_wedge(self, bushy_graph):
        # A has 3 leaves vs B/C/D with 1 each => A owns a wider angular wedge,
        # visible as a larger gap between A and its neighbour than between the
        # single-leaf siblings.
        pos = compute_radial_layout(bushy_graph)
        ang = {k: _angle_deg(pos[k]) for k in ("A", "B", "C", "D")}
        gap_ab = abs(ang["A"] - ang["B"])
        gap_cd = abs(ang["C"] - ang["D"])
        assert gap_ab > gap_cd


class TestDeterminism:
    def test_stable_across_insertion_order(self):
        g1 = IntentGraph(meta={"name": "o1"})
        g1.add_node("ROOT", "R", "r")
        for k in ("A", "B", "C"):
            g1.add_node_under(k, k, "x", parent_uid="ROOT")

        g2 = IntentGraph(meta={"name": "o2"})
        g2.add_node("ROOT", "R", "r")
        for k in ("C", "A", "B"):  # different insertion order
            g2.add_node_under(k, k, "x", parent_uid="ROOT")

        assert compute_radial_layout(g1) == compute_radial_layout(g2)


class TestEdgeCases:
    def test_single_node(self, single_node):
        pos = compute_radial_layout(single_node)
        assert set(pos) == {"ROOT"}
        assert _radius(pos["ROOT"]) == pytest.approx(0.0, abs=1.0)

    def test_deep_chain_is_straight_spoke(self, chain_graph):
        pos = compute_radial_layout(chain_graph)
        angles = [round(_angle_deg(pos[u]), 3) for u in ("C", "C.1", "C.1.1")]
        assert len(set(angles)) == 1  # all on one ray

    def test_empty_graph(self):
        g = IntentGraph(meta={"name": "empty"})
        assert compute_radial_layout(g) == {}
