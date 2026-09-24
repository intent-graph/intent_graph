"""Global radial (multi-ring) layout for the Obsidian Canvas export.

Lays the *entire* tree out once into a single ``{uid -> NodeLayout}`` map so a
reader can zoom out to see the whole graph shape and zoom into any region while
the map stays stable — every canvas reads from this one coordinate space rather
than recomputing its own.

The algorithm is the angular generalisation of the horizontal tree layout in
``_export.py`` (``_subtree_span`` / ``_assign_x``): the conserved quantity is
*angle* instead of *x*, and depth maps to ring *radius* instead of a y-band.

Two passes:

1. **Bottom-up leaf count** — each subtree's angular weight is its number of
   leaves (a bushy branch earns a wider wedge than a shallow one).
2. **Top-down angle + radius** — the root owns the used arc; each node hands its
   children sub-wedges in proportion to their leaf counts; ``(angle, radius)`` is
   converted to a top-left ``(x, y)`` for JSON Canvas.

Pure, dependency-free (``math`` + core models only), deterministic: children are
ordered by uid so output does not depend on insertion order.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from intentgraph.models.layout import NodeLayout
from intentgraph.models.graph import IntentGraph
from intentgraph.models.node import IntentNode


@dataclass(frozen=True)
class RadialConfig:
    """Configuration for the global radial Canvas layout.

    Angles are in degrees; ``0`` points east (right), increasing clockwise in
    Canvas coordinates (y grows downward). The default sweep is a half-circle:
    the tree fans across the upper 180 deg and only spills toward a full circle
    when there are too many L1 branches to seat within their minimum wedge.
    """

    node_width: int = 560
    node_height: int = 560
    ring_gap: int = 900
    center_x: int = 0
    center_y: int = 0
    start_angle_deg: float = 0.0
    total_sweep_deg: float = 180.0
    min_wedge_deg: float = 22.5     # 1/8 of a half-circle — lower angular budget per L1
    max_wedge_deg: float = 30.0     # 1/6 of a half-circle — upper angular budget per L1
    ring_scale: float = 1.0         # extra multiplier on the overlap-driven radius
    ring_node_pad: float = 0.3      # fraction of ring_gap kept as chord padding


def compute_radial_layout(
    graph: IntentGraph,
    config: RadialConfig | None = None,
) -> dict[str, NodeLayout]:
    """Lay out the whole tree once into a polar coordinate map.

    Root sits at the centre; a node at tree-depth *d* sits on ring *d*. Returns a
    ``{uid: NodeLayout}`` covering every node reachable from the first root. Pure
    — no I/O, no graph mutation.
    """
    cfg = config or RadialConfig()

    roots = graph.roots()
    if not roots:
        return {}
    root = min(roots, key=lambda n: n.uid)  # deterministic when multiple roots

    # Pass 1: leaf counts (memoised) + per-depth node histogram.
    leaf_count: dict[str, int] = {}
    depth_hist: dict[int, int] = defaultdict(int)

    def _measure(uid: str, depth: int) -> int:
        depth_hist[depth] += 1
        kids = _sorted_children(graph, uid)
        if not kids:
            leaf_count[uid] = 1
            return 1
        total = sum(_measure(c.uid, depth + 1) for c in kids)
        leaf_count[uid] = total
        return total

    _measure(root.uid, 0)

    # Determine the arc actually used, applying the angular budget to L1.
    l1 = _sorted_children(graph, root.uid)
    arc = _used_arc(len(l1), cfg)

    # Precompute a radius per depth that guarantees non-overlap on each ring.
    radius_at = _radius_table(depth_hist, arc, cfg)

    # Pass 2: assign [a0, a1] wedges top-down; place each node at its wedge mid.
    positions: dict[str, NodeLayout] = {}

    def _assign(uid: str, a0: float, a1: float, depth: int) -> None:
        mid = (a0 + a1) / 2.0
        positions[uid] = _polar_to_layout(mid, radius_at[depth], cfg)
        kids = _sorted_children(graph, uid)
        if not kids:
            return
        total = leaf_count[uid]
        cursor = a0
        span = a1 - a0
        for child in kids:
            frac = leaf_count[child.uid] / total
            child_span = span * frac
            _assign(child.uid, cursor, cursor + child_span, depth + 1)
            cursor += child_span

    # Centre the used arc within the configured sweep window.
    start = cfg.start_angle_deg + (cfg.total_sweep_deg - arc) / 2.0 \
        if arc <= cfg.total_sweep_deg else cfg.start_angle_deg
    _assign(root.uid, start, start + arc, 0)

    return positions


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _sorted_children(graph: IntentGraph, uid: str) -> list[IntentNode]:
    """Children ordered by uid — makes the layout independent of insertion order."""
    return sorted(graph.children(uid), key=lambda c: c.uid)


def _used_arc(n_l1: int, cfg: RadialConfig) -> float:
    """Total arc (degrees) the tree fans across, from the L1 angular budget.

    - Few L1 branches: keep the configured sweep (they under-fill — fine), but do
      not let a single branch sprawl wider than ``max_wedge``.
    - Enough branches to exceed the sweep at ``min_wedge`` each: spill toward a
      full circle, capped at 360.
    """
    if n_l1 <= 0:
        return cfg.total_sweep_deg
    desired = n_l1 * cfg.min_wedge_deg
    if desired <= cfg.total_sweep_deg:
        # They fit; clamp so a tiny fan-out doesn't span the whole sweep.
        return min(cfg.total_sweep_deg, n_l1 * cfg.max_wedge_deg)
    return min(360.0, desired)


def _radius_table(
    depth_hist: dict[int, int],
    arc_deg: float,
    cfg: RadialConfig,
) -> dict[int, float]:
    """Radius per depth: base band spacing, widened so a crowded ring can't overlap.

    A ring at depth *d* must seat ``depth_hist[d]`` nodes along the used arc; if
    that requires more circumference than the base radius offers, the radius is
    pushed out accordingly.
    """
    arc_rad = math.radians(arc_deg) if arc_deg > 0 else math.radians(360.0)
    chord = cfg.node_width + cfg.ring_gap * cfg.ring_node_pad
    table: dict[int, float] = {}
    max_depth = max(depth_hist) if depth_hist else 0
    for d in range(max_depth + 1):
        if d == 0:
            table[0] = 0.0
            continue
        base = d * cfg.ring_gap
        n = depth_hist.get(d, 1)
        needed_circumference = n * chord
        r_min = needed_circumference / arc_rad if arc_rad > 0 else base
        table[d] = max(base, r_min * cfg.ring_scale)
    return table


def _polar_to_layout(angle_deg: float, radius: float, cfg: RadialConfig) -> NodeLayout:
    """Convert a polar (angle, radius) placement to a top-left NodeLayout box."""
    rad = math.radians(angle_deg)
    cx = cfg.center_x + radius * math.cos(rad)
    cy = cfg.center_y + radius * math.sin(rad)
    return NodeLayout(
        x=int(round(cx - cfg.node_width / 2.0)),
        y=int(round(cy - cfg.node_height / 2.0)),
        width=cfg.node_width,
        height=cfg.node_height,
    )
