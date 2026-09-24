"""Export IntentGraph -> Obsidian vault folder.

Generates:
- ``nodes/`` directory with one ``.md`` per intentnode
- ``edges.yaml`` with all intentlinks
- ``viz/`` directory with one ``.canvas`` per non-leaf node
- ``viz/FULL_TREE.canvas`` — treemap-proportional full tree overview
- (optional) view canvases showing a custom working view (node set)
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from intentgraph.models.graph import IntentGraph
from intentgraph.models.layout import NodeLayout
from intentgraph.models.view import View
from intentgraph.models.lens import LOD, Lens
from intentgraph.models.node import IntentNode
from intentgraph.obsidian._format import (
    DEFAULT_LAYOUT,
    LayoutConfig,
    compute_grid_positions,
    compute_group_size,
    edge_id,
    file_node_id,
    group_id,
    node_filename,
    node_stem,
    to_canvas_id,
    uid_from_stem,
    yaml_literal_block,
    yaml_quote,
    yaml_str_list_multiline,
    _safe_literal_line,
)
from intentgraph.obsidian._plugins import PluginReport, ensure_vault_plugins
from intentgraph.obsidian._radial import RadialConfig, compute_radial_layout


# Key under a node's data_registry that holds its persisted Obsidian canvas
# layout. Obsidian-scoped on purpose: other projections (e.g. the VSCode
# extension's ``lenses.<name>.nodes.<uid>.position``) keep their own disjoint
# storage. Shape (all sub-keys optional):
#
#   obsidian_layout:
#     engine: radial | portal          # coordinate frame the boxes live in
#     computed: {x, y, width, height}  # box the last export WROTE to the canvas
#     pinned:   {x, y, width, height}  # human assertion — sticky until retracted
#     portal:                          # L1 nodes only: the branch's OVERVIEW portal
#       computed: {x, y}
#       pinned:   {x, y}               # position-only (portal size is plugin-forced)
#
# ``computed`` is the effective box the exporter last wrote to disk
# (``pinned ?? engine output``, after fit-height). That definition — not the raw
# engine output — is what makes pin detection sound: the question detection asks
# is "does the on-disk canvas differ from what *I* last wrote?" (a human edit),
# never "does it differ from what I would compute now?" (fit-height drift, a
# retracted pin's stale canvas — both false positives under a fresh recompute).
_LAYOUT_KEY = "obsidian_layout"

# Tolerance (px) when diffing an on-disk canvas box against the stored
# ``computed`` baseline: rounding deltas are not a pin.
_DETECT_TOLERANCE = 2

# Key under a node's data_registry that lists image samples to embed in the node
# body. Value: list of {"path": "<vault-relative image path>", "caption": "..."}.
# Export generates the "## Samples" section from this so the images are OWNED by
# the IntentGraph and survive re-export (rather than being bolted onto the vault).
_SAMPLES_KEY = "samples"


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def export_to_obsidian(
    graph: IntentGraph,
    output_dir: str | Path,
    *,
    layout_config: LayoutConfig | None = None,
    vault_root: str | Path | None = None,
    include_intentlinks: str = "all",
    include_ft_canvases: bool = True,
    write_snapshot: bool = False,
    graph_id: str | None = None,
    graph_file: str | None = None,
    exported_at: str | None = None,
    layout_engine: str = "grid",
    radial_config: RadialConfig | None = None,
    nav_links: str = "minimal",
    fit_height: bool = False,
    install_plugins: bool = True,
) -> PluginReport:
    """Write an IntentGraph to an Obsidian vault folder.

    Creates ``nodes/``, ``viz/``, and ``edges.yaml`` under *output_dir*.
    When *include_ft_canvases* is True (default), also writes ``viz/__FT_ROOT.canvas``
    and ``viz/_FT_{L1}.canvas`` for each L1 (leading _ so FT canvases sort to top).

    When *write_snapshot* is True, also writes ``.ig-sync.yaml`` with
    content hashes for lossless merge detection. Default is False for backward
    compatibility with existing tests and workflows.

    Parameters
    ----------
    graph : IntentGraph
        The graph to export.
    output_dir : str | Path
        Root directory for the vault.
    layout_config : LayoutConfig | None
        Optional grid layout overrides.
    vault_root : str | Path | None
        The Obsidian vault root (where ``.obsidian/`` lives).  Canvas
        ``"file"`` paths are resolved relative to this directory.  When
        *None*, defaults to *output_dir* (single-graph vault).
    include_intentlinks : str
        Which intentlinks to draw in FULL_TREE and FT canvases: ``"all"``,
        ``"siblings"``, or ``"none"``.
    include_ft_canvases : bool
        If True (default), write __FT_ROOT.canvas and _FT_{L1}.canvas.
    write_snapshot : bool
        If True, write ``.ig-sync.yaml`` with content hashes. Default False
        for backward compatibility. CLI passes True when needed.
    graph_id : str | None
        Optional graph identifier for the snapshot (defaults to None).
    graph_file : str | None
        Optional graph file path for the snapshot (defaults to None).
    exported_at : str | None
        ISO-8601 timestamp of export. If None and write_snapshot=True, defaults
        to datetime.now(datetime.UTC).isoformat().
    install_plugins : bool
        If True (default), install and enable the Obsidian community plugins
        this *layout_engine*'s canvases need to render (``portal`` requires
        Advanced Canvas) into the vault root's ``.obsidian/``. Obsidian has no
        global plugin install, so a generated vault must carry its own.

    Returns
    -------
    PluginReport
        What was installed/enabled, and which required plugins were missing
        from the local cache (``report.hint()`` renders an actionable message).
        Empty when the engine needs no plugins or *install_plugins* is False.
    """
    out = Path(output_dir).resolve()
    nodes_dir = out / "nodes"
    viz_dir = out / "viz"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    viz_dir.mkdir(parents=True, exist_ok=True)

    cfg = layout_config or DEFAULT_LAYOUT

    if vault_root is not None:
        vroot = Path(vault_root).resolve()
        nodes_prefix = str(out.relative_to(vroot) / "nodes")
    else:
        vroot = out
        nodes_prefix = "nodes"

    # 0a. Pin detection — read back the previous export's canvases (if this
    #     vault already exists) and record human moves/resizes as pins BEFORE
    #     anything is rewritten. Grid is inert (never stores a baseline).
    if layout_engine in _LAYOUT_ENGINES:
        detect_canvas_pins(graph, viz_dir, engine=layout_engine)

    # 0b. Compute the one global layout map (radial only), pinned boxes
    #     overriding fresh engine output. Grid/portal: {} (portal lays out
    #     per-branch in its generators).
    position_map = apply_global_layout(
        graph, engine=layout_engine, radial_config=radial_config,
    )

    # Fit-height needs each node's body (for image embeds). The body is fully
    # generated from the graph (## Samples), so build it in memory — canvases
    # are written before the markdown files now, since the boxes they end up
    # with must land in data_registry (hence frontmatter) as the new baseline.
    samples_bodies = (
        {n.uid: _format_samples(n) for n in graph.iter_nodes()}
        if fit_height else None
    )
    pinned_uids = (
        {n.uid for n in graph.iter_nodes()
         if _pinned_box(n, layout_engine) is not None}
        if layout_engine in _LAYOUT_ENGINES else set()
    )

    def _write_canvas(path: Path, canvas_json: str) -> str:
        """Write a canvas (fit-height post-processing when requested).

        Returns the JSON actually written, so the caller can capture the final
        boxes into ``obsidian_layout.computed``. Pinned nodes keep their pinned
        height — fit-height never overrides a human resize.
        """
        if fit_height:
            canvas_json = _apply_fit_height(
                canvas_json, graph, bodies=samples_bodies, vault_root=vroot,
                skip_uids=pinned_uids,
            )
        path.write_text(canvas_json, encoding="utf-8")
        return canvas_json

    id_to_uid = {file_node_id(n.uid): n.uid for n in graph.iter_nodes()}

    if layout_engine == "portal":
        # Portal mode: one vertical-tree canvas per L1 branch, plus an OVERVIEW
        # canvas with ROOT at the centre and each L1 embedded as a radial portal.
        roots = graph.roots()
        if roots:
            root = roots[0]
            l1_children = sorted(graph.children(root.uid), key=lambda c: c.uid)
            bboxes: dict[str, dict[str, int]] = {}
            written_boxes: dict[str, NodeLayout] = {}
            for l1 in l1_children:
                l1_json, bbox = _generate_l1_subtree_canvas(
                    graph, l1.uid, nodes_prefix=nodes_prefix,
                )
                final = _write_canvas(
                    viz_dir / f"{l1_canvas_stem(l1.uid)}.canvas", l1_json,
                )
                written_boxes.update(_capture_canvas_boxes(final, id_to_uid))
                bboxes[l1.uid] = bbox
            overview_json = generate_portal_overview_canvas(
                graph, bboxes, nodes_prefix=nodes_prefix,
            )
            # OVERVIEW's file-nodes are portals (.canvas) + ROOT; fit-height only
            # touches ROOT (portals are branch embeds, left as sized).
            final_overview = _write_canvas(viz_dir / "OVERVIEW.canvas", overview_json)
            written_boxes.update(_capture_canvas_boxes(final_overview, id_to_uid))
            portal_xy = {
                uid: (box.x, box.y)
                for uid, box in _capture_canvas_boxes(
                    final_overview,
                    {portal_node_id(l1.uid): l1.uid for l1 in l1_children},
                ).items()
            }
            _store_computed(graph, layout_engine, written_boxes, portal_xy)
    else:
        # 3. Write canvas files for non-leaf nodes
        for node in graph.iter_nodes():
            children = graph.children(node.uid)
            if children:
                canvas_json = _generate_canvas(node.uid, graph, cfg,
                                               nodes_prefix=nodes_prefix,
                                               position_map=position_map)
                _write_canvas(viz_dir / f"{node.uid}.canvas", canvas_json)

        # 4. Write FULL_TREE.canvas (the primary zoom-out overview). Under radial
        #    it reads from the shared global position_map so it is the one canvas
        #    the reader zooms out on to see the whole graph shape.
        full_tree_json = generate_full_tree_canvas(
            graph, nodes_prefix=nodes_prefix,
            include_intentlinks=include_intentlinks,
            position_map=position_map or None,
        )
        final_ft = _write_canvas(viz_dir / "FULL_TREE.canvas", full_tree_json)
        if layout_engine == "radial":
            # Global frame: FULL_TREE shows every node at its one global box —
            # capture the boxes as written (post fit-height) as the baseline.
            _store_computed(
                graph, layout_engine, _capture_canvas_boxes(final_ft, id_to_uid),
            )

        # 5. FT canvases (__FT_ROOT + _FT_{L1}) when requested
        if include_ft_canvases:
            roots = graph.roots()
            if roots:
                root = roots[0]
                l1_children = graph.children(root.uid)
                # __FT_ROOT is same layout as FULL_TREE
                _write_canvas(viz_dir / "__FT_ROOT.canvas", full_tree_json)
                # Per L1: _FT_{L1} (expanded subtree)
                for l1 in l1_children:
                    ft_l1_json = generate_full_tree_canvas(
                        graph, nodes_prefix=nodes_prefix,
                        include_intentlinks=include_intentlinks,
                        focus_l1_uid=l1.uid,
                        position_map=position_map or None,
                    )
                    _write_canvas(viz_dir / f"_FT_{l1.uid}.canvas", ft_l1_json)

    # 1. Write node markdown files — after the canvases, so the frontmatter
    #    carries the final obsidian_layout (computed = boxes as written).
    for node in graph.iter_nodes():
        content = _generate_node_markdown(
            node, graph, layout_engine=layout_engine, nav_links=nav_links,
        )
        path = nodes_dir / node_filename(node.uid, node.name)
        path.write_text(content, encoding="utf-8")

    # 2. Write edges.yaml
    edges_content = _generate_edges_yaml(graph)
    (out / "edges.yaml").write_text(edges_content, encoding="utf-8")

    # 6. Write snapshot for lossless merge detection (optional)
    if write_snapshot:
        from intentgraph.obsidian._snapshot import write_snapshot as write_snapshot_file
        from datetime import datetime, timezone
        ts = exported_at or datetime.now(timezone.utc).isoformat()
        write_snapshot_file(
            out,
            graph,
            graph_id=graph_id,
            graph_file=graph_file,
            exported_at=ts,
        )

    # 7. Provision the plugins this engine's canvases need to render. Goes to
    #    the VAULT ROOT (not output_dir): in a multi-graph vault the product_ig/
    #    and projection_ig/ subfolders share one .obsidian/.
    if install_plugins:
        return ensure_vault_plugins(vroot, layout_engine=layout_engine)
    return PluginReport()


# ------------------------------------------------------------------ #
#  Fit node height — content-based sizing model                       #
# ------------------------------------------------------------------ #
#
#  Obsidian renders a node's frontmatter as a Properties panel: a title, then one
#  row per field. We can't know exact pixels at export time, but the layout is
#  regular enough to model from measurements (calibrated against real rendered
#  heights at width 560):
#
#    height = BASE + Σ_field ( ROW_GAP + lines_field * LINE_H )
#      lines_field = ceil(chars / CHARS_PER_LINE)
#        · prose/scalar fields (intent, epistemic_state, design_notes, effort,
#          impl_pointers) are CLIPPED by Obsidian to PROSE_LINE_CAP lines.
#        · list fields (constraints, examples, history) render every item, so
#          their lines are summed per-item and NOT capped.
#      + FIT_MARGIN so the box never clips its content.
#
#  Constants fitted to 9 measured nodes (RMSE ~13px, zero clipping). Recalibrate
#  with the console instrument if the vault's CSS/width changes materially.

_FIT_BASE = 159          # title + "Properties" header + footer chrome
_FIT_ROW_GAP = 36        # vertical gap contributed per property row
_FIT_LINE_H = 19         # px per wrapped text line
_FIT_CHARS_PER_LINE = 50 # chars before wrap at the default node width (560px)
_FIT_PROSE_LINE_CAP = 3  # Obsidian clips a scalar property value to 3 lines
_FIT_MARGIN = 25         # safety pad so the model never under-shoots (no clip)
_FIT_MIN_HEIGHT = 120    # floor for a near-empty node

# Fields whose value renders as a multi-line list (uncapped), not a scalar.
_FIT_LIST_FIELDS = ("constraints", "examples", "history")

# The scalar/prose fields the export renders as single property values.
_FIT_PROSE_FIELDS = ("intent", "epistemic_state", "design_notes", "effort",
                     "impl_pointers")


def _field_char_count(value: Any) -> int:
    """Total character count a field contributes to the Properties panel."""
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value.strip())
    if isinstance(value, (list, tuple)):
        # each item stringified (HistoryEntry -> its parts) and summed
        total = 0
        for item in value:
            if isinstance(item, str):
                total += len(item.strip())
            else:  # HistoryEntry / object
                total += len(str(getattr(item, "note", "") or "")) + 20
        return total
    return len(str(value))


def _field_lines(value: Any, *, is_list: bool) -> int:
    """Rendered line count for one field's value, per the calibrated model."""
    if is_list:
        # Sum wrapped lines across every item (uncapped) + 1 line of separator each.
        items = value if isinstance(value, (list, tuple)) else []
        if not items:
            return 0
        lines = 0
        for item in items:
            chars = _field_char_count([item])
            lines += max(1, math.ceil(chars / _FIT_CHARS_PER_LINE))
        return lines
    chars = _field_char_count(value)
    if chars == 0:
        return 0
    raw = max(1, math.ceil(chars / _FIT_CHARS_PER_LINE))
    return min(_FIT_PROSE_LINE_CAP, raw)


# --- Body image embeds (## Samples etc.) ------------------------------------
# The node body can carry markdown image embeds the frontmatter model can't see.
# Measure each with Pillow, scale to the node's content width, and add its
# rendered height plus per-image caption + a one-off section-heading allowance.

_FIT_CONTENT_WIDTH = 520   # node width (560) minus horizontal padding
_FIT_IMAGE_MAX_H = 480     # Obsidian caps a very tall embed; keep boxes sane
_FIT_IMAGE_CAPTION = 40    # px for the bold caption line above each image
_FIT_IMAGE_GAP = 24        # px whitespace around each embed
_FIT_SECTION_HEADING = 60  # px for a "## Samples" heading when any embed exists

# Markdown image embeds: ![[path]] (wiki) and ![alt](path) (standard).
_EMBED_RE = re.compile(r"!\[\[([^\]|#]+)[^\]]*\]\]|!\[[^\]]*\]\(([^)]+)\)")

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")


def _extract_body_embeds(body: str) -> list[str]:
    """Return image paths embedded in a node's markdown body (in order)."""
    paths: list[str] = []
    for m in _EMBED_RE.finditer(body or ""):
        p = (m.group(1) or m.group(2) or "").strip()
        if p.lower().endswith(_IMAGE_EXTS):
            paths.append(p)
    return paths


def _image_render_height(image_path: Path) -> int:
    """Rendered height (px) of one embed, scaled to the node content width.

    Reads the image's real dimensions with Pillow. Returns 0 only for a genuinely
    broken embed — a missing file or a file Pillow cannot decode — so a bad link
    never inflates the box. Any other error propagates (we do not want to hide a
    real bug behind a silent zero, as a swallowed ImportError once did).
    """
    try:
        with Image.open(image_path) as im:
            w, h = im.size
    except (FileNotFoundError, IsADirectoryError, UnidentifiedImageError, OSError):
        return 0
    if not w or not h:
        return 0
    scaled = round(_FIT_CONTENT_WIDTH * h / w)
    return min(_FIT_IMAGE_MAX_H, scaled)


def _body_image_height(body: str, vault_root: Path) -> int:
    """Extra pixel height a node's body image embeds contribute, if any."""
    embeds = _extract_body_embeds(body)
    if not embeds:
        return 0
    total = _FIT_SECTION_HEADING
    for rel in embeds:
        img = (vault_root / rel)
        total += _FIT_IMAGE_CAPTION + _image_render_height(img) + _FIT_IMAGE_GAP
    return total


def estimate_node_height(node: IntentNode, *, extra_body_height: int = 0) -> int:
    """Estimate the Obsidian-rendered height (px) of a node, from its content.

    Sums a fixed base plus one row per non-empty frontmatter field, each row's
    height driven by its wrapped line count (prose capped at 3 lines, lists
    uncapped). ``extra_body_height`` accounts for non-frontmatter body content
    the model can't see from the node alone — e.g. embedded images in a
    ``## Samples`` section (computed by :func:`_body_image_height`). Errs
    slightly tall (``_FIT_MARGIN``) so a box never clips.
    """
    total = _FIT_BASE + _FIT_MARGIN
    for field in _FIT_PROSE_FIELDS:
        lines = _field_lines(getattr(node, field, None), is_list=False)
        if lines:
            total += _FIT_ROW_GAP + lines * _FIT_LINE_H
    for field in _FIT_LIST_FIELDS:
        lines = _field_lines(getattr(node, field, None), is_list=True)
        if lines:
            total += _FIT_ROW_GAP + lines * _FIT_LINE_H
    total += extra_body_height
    return max(_FIT_MIN_HEIGHT, total)


def _uid_from_node_file(file_path: str) -> str | None:
    """Recover a node uid from a canvas file-node's ``file`` path.

    ``"nodes/FUNCTION Functional Role.md"`` -> ``"FUNCTION"``. Portal file-nodes
    point at ``*.canvas`` (a branch view, not a single node) and yield None.
    """
    if not file_path.endswith(".md"):
        return None
    stem = file_path.rsplit("/", 1)[-1].removesuffix(".md")
    return uid_from_stem(stem)


def _apply_fit_height(
    canvas_json: str,
    graph: IntentGraph,
    *,
    nodes_dir: Path | None = None,
    vault_root: Path | None = None,
    bodies: dict[str, str] | None = None,
    skip_uids: set[str] | None = None,
) -> str:
    """Resize each markdown file-node to its estimated content height.

    Replaces the fixed tall default with a content-fitted height (see
    :func:`estimate_node_height`). Body image embeds (e.g. a ``## Samples``
    section) are measured when *vault_root* is given together with either
    *bodies* (in-memory ``{uid: body-markdown}``, used by the export before the
    ``.md`` files exist) or *nodes_dir* (read the written file). Group, portal,
    and other non-markdown nodes are left untouched, as is any node in
    *skip_uids* — a pinned box is a human assertion fit-height must not undo.
    """
    canvas = json.loads(canvas_json)
    for cnode in canvas.get("nodes", []):
        if cnode.get("type") != "file":
            continue
        uid = _uid_from_node_file(cnode.get("file", ""))
        node = graph.get_node_or_none(uid) if uid else None
        if node is None:
            continue  # portal embeds (.canvas) and unknown nodes untouched
        if skip_uids and node.uid in skip_uids:
            continue
        extra = 0
        if vault_root is not None:
            body: str | None = None
            if bodies is not None:
                body = bodies.get(node.uid)
            elif nodes_dir is not None:
                md_path = nodes_dir / node_filename(node.uid, node.name)
                if md_path.is_file():
                    body = md_path.read_text(encoding="utf-8")
            if body:
                extra = _body_image_height(body, vault_root)
        cnode["height"] = estimate_node_height(node, extra_body_height=extra)
    return json.dumps(canvas, indent=4)


# ------------------------------------------------------------------ #
#  Global layout — obsidian_layout storage, pin detection, precedence #
# ------------------------------------------------------------------ #
#
#  Every field renders as ``pinned ?? computed``-fresh: a pin (human assertion,
#  set by canvas read-back detection) beats the engine; otherwise the engine's
#  fresh output is used. After writing, the box actually written becomes the
#  new ``computed`` baseline (see _LAYOUT_KEY comment for why).
#
#  Pins are ENGINE-SCOPED: radial coordinates are global, portal branch
#  coordinates are branch-local — a pin only means something inside the frame
#  it was captured in. The ``engine`` field records that frame; a layout block
#  from a different engine is dropped, never misread.

# Engines that persist layout into data_registry. Grid stays fully inert so its
# output remains byte-identical to the pre-layout era (TestGridUnchanged).
_LAYOUT_ENGINES = ("radial", "portal")


def _layout_block(node: IntentNode) -> dict[str, Any]:
    """The node's ``data_registry.obsidian_layout`` block (empty dict if none)."""
    reg = node.data_registry or {}
    block = reg.get(_LAYOUT_KEY)
    return block if isinstance(block, dict) else {}


def _box_from_entry(entry: Any) -> NodeLayout | None:
    """Parse a ``{x,y,width,height}`` mapping into a NodeLayout, or None."""
    if not isinstance(entry, dict):
        return None
    try:
        return NodeLayout(**entry)
    except (TypeError, ValueError):
        return None


def _box_entry(box: NodeLayout) -> dict[str, int]:
    """Serialize a NodeLayout to the stored ``{x,y,width,height}`` mapping."""
    return {"x": box.x, "y": box.y, "width": box.width, "height": box.height}


def _pinned_box(node: IntentNode, engine: str) -> NodeLayout | None:
    """The node's pinned box, if one exists *in this engine's frame*."""
    block = _layout_block(node)
    if block.get("engine") != engine:
        return None
    return _box_from_entry(block.get("pinned"))


def _computed_box(node: IntentNode, engine: str) -> NodeLayout | None:
    """The box the last export of *engine* wrote for this node, if recorded."""
    block = _layout_block(node)
    if block.get("engine") != engine:
        return None
    return _box_from_entry(block.get("computed"))


def _portal_xy(node: IntentNode, engine: str, kind: str) -> tuple[int, int] | None:
    """An L1 node's stored portal position (``kind`` = computed|pinned)."""
    block = _layout_block(node)
    if block.get("engine") != engine:
        return None
    portal = block.get("portal")
    entry = portal.get(kind) if isinstance(portal, dict) else None
    if isinstance(entry, dict) and "x" in entry and "y" in entry:
        try:
            return int(entry["x"]), int(entry["y"])
        except (TypeError, ValueError):
            return None
    return None


def _update_layout_block(
    graph: IntentGraph,
    uid: str,
    engine: str,
    mutate: Any,
) -> None:
    """Apply *mutate(block)* to the node's layout block and write it back.

    A block recorded under a different engine describes a different coordinate
    frame — it is discarded (pins included) before mutating, never carried over.
    """
    node = graph.get_node_or_none(uid)
    if node is None:
        return
    block = dict(_layout_block(node))
    if block.get("engine") != engine:
        block = {}
    block["engine"] = engine
    mutate(block)
    reg = dict(node.data_registry or {})
    reg[_LAYOUT_KEY] = block
    graph.update_node(uid, data_registry=reg)


def _set_pinned(graph: IntentGraph, uid: str, engine: str, box: NodeLayout) -> None:
    def mutate(block: dict[str, Any]) -> None:
        block["pinned"] = _box_entry(box)
    _update_layout_block(graph, uid, engine, mutate)


def _set_portal_pinned(
    graph: IntentGraph, uid: str, engine: str, xy: tuple[int, int],
) -> None:
    def mutate(block: dict[str, Any]) -> None:
        portal = dict(block.get("portal") or {})
        portal["pinned"] = {"x": xy[0], "y": xy[1]}
        block["portal"] = portal
    _update_layout_block(graph, uid, engine, mutate)


def _store_computed(
    graph: IntentGraph,
    engine: str,
    boxes: dict[str, NodeLayout],
    portal_xy: dict[str, tuple[int, int]] | None = None,
) -> None:
    """Record the boxes this export actually wrote as the next detection baseline."""
    for uid, box in boxes.items():
        def mutate(block: dict[str, Any], _box: NodeLayout = box) -> None:
            block["computed"] = _box_entry(_box)
        _update_layout_block(graph, uid, engine, mutate)
    for uid, xy in (portal_xy or {}).items():
        def mutate(block: dict[str, Any], _xy: tuple[int, int] = xy) -> None:
            portal = dict(block.get("portal") or {})
            portal["computed"] = {"x": _xy[0], "y": _xy[1]}
            block["portal"] = portal
        _update_layout_block(graph, uid, engine, mutate)


def _capture_canvas_boxes(
    canvas_json: str,
    id_to_uid: dict[str, str],
) -> dict[str, NodeLayout]:
    """Extract per-uid boxes from a final (as-written) canvas JSON string."""
    boxes: dict[str, NodeLayout] = {}
    for cnode in json.loads(canvas_json).get("nodes", []):
        uid = id_to_uid.get(cnode.get("id", ""))
        if uid is None:
            continue
        box = _box_from_entry({k: cnode.get(k) for k in ("x", "y", "width", "height")})
        if box is not None:
            boxes[uid] = box
    return boxes


def detect_canvas_pins(
    graph: IntentGraph,
    viz_dir: str | Path,
    *,
    engine: str,
    tolerance: int = _DETECT_TOLERANCE,
) -> list[str]:
    """Read back a previously exported vault's canvases and pin human edits.

    For every canvas the current *engine* is about to (re)write, if the file
    already exists on disk, each real node box is compared against the node's
    stored ``obsidian_layout.computed`` — the box the last export wrote there:

    - no stored ``computed`` (first export, or a different engine's frame):
      never a pin;
    - on-disk box ≈ ``computed`` (within *tolerance*): untouched — fit-height
      drift and a just-retracted pin's stale canvas both land here;
    - otherwise a human moved/resized it: the on-disk box becomes ``pinned``
      (for a portal node, position only, onto its L1's ``portal.pinned``).

    Layout blocks recorded under a *different* engine are dropped up front —
    their coordinates live in another frame and must not be honored or diffed.
    Mutates the graph; returns the sorted uids that got (re)pinned.
    """
    if engine not in _LAYOUT_ENGINES:
        return []
    viz = Path(viz_dir)

    # Frame guard: discard stale-engine layout blocks (pins included).
    for node in list(graph.iter_nodes()):
        block = _layout_block(node)
        if block and block.get("engine") not in (None, engine):
            reg = dict(node.data_registry or {})
            reg.pop(_LAYOUT_KEY, None)
            graph.update_node(node.uid, data_registry=reg or None)

    id_to_uid = {file_node_id(n.uid): n.uid for n in graph.iter_nodes()}
    portal_ids: dict[str, str] = {}
    canvases: list[Path] = []
    if engine == "portal":
        roots = graph.roots()
        l1s = sorted(graph.children(roots[0].uid), key=lambda c: c.uid) if roots else []
        portal_ids = {portal_node_id(l1.uid): l1.uid for l1 in l1s}
        canvases.append(viz / "OVERVIEW.canvas")
        canvases.extend(viz / f"{l1_canvas_stem(l1.uid)}.canvas" for l1 in l1s)
    else:  # radial — global frame, same box on every canvas
        canvases.extend((viz / "FULL_TREE.canvas", viz / "__FT_ROOT.canvas"))
        roots = graph.roots()
        if roots:
            canvases.extend(
                viz / f"_FT_{l1.uid}.canvas" for l1 in graph.children(roots[0].uid)
            )
        canvases.extend(
            viz / f"{n.uid}.canvas" for n in graph.iter_nodes() if graph.children(n.uid)
        )

    pinned: set[str] = set()
    portal_pinned: set[str] = set()
    for cpath in canvases:
        if not cpath.is_file():
            continue
        try:
            cnodes = json.loads(cpath.read_text(encoding="utf-8")).get("nodes", [])
        except (json.JSONDecodeError, OSError):
            continue  # unreadable canvas: never a detection source
        for cnode in cnodes:
            cid = cnode.get("id", "")
            if cid in portal_ids:
                uid = portal_ids[cid]
                if uid in portal_pinned:
                    continue
                node = graph.get_node_or_none(uid)
                base = _portal_xy(node, engine, "computed") if node else None
                if base is None:
                    continue  # first export in this frame — never a pin
                x, y = cnode.get("x"), cnode.get("y")
                if x is None or y is None:
                    continue
                if abs(x - base[0]) > tolerance or abs(y - base[1]) > tolerance:
                    _set_portal_pinned(graph, uid, engine, (int(x), int(y)))
                    portal_pinned.add(uid)
            elif cid in id_to_uid:
                uid = id_to_uid[cid]
                if uid in pinned:
                    continue
                node = graph.get_node_or_none(uid)
                base = _computed_box(node, engine) if node else None
                if base is None:
                    continue  # first export in this frame — never a pin
                box = _box_from_entry(
                    {k: cnode.get(k) for k in ("x", "y", "width", "height")}
                )
                if box is None:
                    continue
                if (
                    abs(box.x - base.x) > tolerance
                    or abs(box.y - base.y) > tolerance
                    or abs(box.width - base.width) > tolerance
                    or abs(box.height - base.height) > tolerance
                ):
                    _set_pinned(graph, uid, engine, box)
                    pinned.add(uid)
    return sorted(pinned | portal_pinned)


def apply_global_layout(
    graph: IntentGraph,
    *,
    engine: str = "grid",
    radial_config: RadialConfig | None = None,
) -> dict[str, NodeLayout]:
    """Compute the whole-tree radial position map, honoring pinned boxes.

    For ``engine == "radial"``, computes a single global radial layout and
    overrides each node's box with its ``obsidian_layout.pinned`` when present
    (``pinned ?? computed-fresh``, every field). The map is NOT persisted here:
    the export records what it actually *writes* (post fit-height) back into
    ``obsidian_layout.computed`` so the next detection has a true baseline.

    For any other engine this returns ``{}`` — portal computes per-branch
    layouts in its own generators, and grid never touches ``data_registry``
    so its output stays byte-identical to before this feature.
    """
    if engine != "radial":
        return {}

    computed = compute_radial_layout(graph, radial_config)
    merged: dict[str, NodeLayout] = {}
    for node in graph.iter_nodes():
        pin = _pinned_box(node, engine)
        merged[node.uid] = pin if pin is not None else computed.get(node.uid)
    return merged


# ------------------------------------------------------------------ #
#  Node markdown generation                                          #
# ------------------------------------------------------------------ #

def _format_samples(node: IntentNode) -> str:
    """Render a node's image samples as a ``## Samples`` body section.

    Reads ``data_registry.samples`` — a list of ``{"path", "caption"?}`` — and
    emits a caption + ``![[path]]`` embed for each. Returns "" when there are
    none. Because this is generated from the graph, the images are owned by the
    IntentGraph and survive re-export.
    """
    reg = node.data_registry or {}
    samples = reg.get(_SAMPLES_KEY) or []
    if not samples:
        return ""
    lines = ["## Samples", ""]
    for s in samples:
        if isinstance(s, str):
            path, caption = s, ""
        elif isinstance(s, dict):
            path, caption = s.get("path", ""), s.get("caption", "")
        else:
            continue
        if not path:
            continue
        if caption:
            lines.append(f"**{caption}**")
            lines.append("")
        lines.append(f"![[{path}]]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _generate_node_markdown(
    node: IntentNode,
    graph: IntentGraph,
    *,
    layout_engine: str = "grid",
    nav_links: str = "minimal",
) -> str:
    """Generate the complete Obsidian markdown content for one node."""
    parts: list[str] = []
    parts.append(_format_frontmatter(node))
    nav = _format_navigation(
        node, graph, layout_engine=layout_engine, nav_links=nav_links,
    )
    if nav:
        parts.append("")
        parts.append(nav)
    samples = _format_samples(node)
    if samples:
        parts.append("")
        parts.append(samples)
    return "\n".join(parts)


def _format_frontmatter(node: IntentNode) -> str:
    """Format YAML frontmatter for a node (all content fields)."""
    lines: list[str] = ["---"]

    # intent (always, literal block)
    lines.append("intent: |")
    lines.extend(yaml_literal_block(node.intent))

    # epistemic_state (optional; literal block if multiline)
    if node.epistemic_state:
        if "\n" in node.epistemic_state:
            lines.append("epistemic_state: |")
            lines.extend(yaml_literal_block(node.epistemic_state))
        else:
            lines.append(f"epistemic_state: {yaml_quote(node.epistemic_state)}")

    # constraints (omit when empty — use literal block for multiline items)
    if node.constraints:
        lines.append("constraints:")
        lines.extend(yaml_str_list_multiline(node.constraints))

    # design_notes (literal block, omit if None for clean round-trip)
    if node.design_notes:
        lines.append("design_notes: |")
        lines.extend(yaml_literal_block(node.design_notes))

    # examples (omit when empty — use literal block for multiline items)
    if node.examples:
        lines.append("examples:")
        lines.extend(yaml_str_list_multiline(node.examples))

    # effort (omit if None; literal block if multiline)
    if node.effort is not None:
        if "\n" in node.effort:
            lines.append("effort: |")
            lines.extend(yaml_literal_block(node.effort))
        else:
            lines.append(f"effort: {yaml_quote(node.effort)}")

    # impl_pointers (omit when empty — list of pointer strings, formalism §4.2)
    if node.impl_pointers:
        lines.append("impl_pointers:")
        lines.extend(yaml_str_list_multiline(node.impl_pointers))

    # data_registry (omit when None/empty; emit as nested YAML)
    if node.data_registry:
        lines.append("data_registry:")
        # Serialize data_registry as indented YAML
        import yaml as yaml_lib
        registry_str = yaml_lib.dump(node.data_registry, default_flow_style=False, allow_unicode=True)
        # Indent each line by 2 spaces
        for line in registry_str.rstrip('\n').split('\n'):
            lines.append(f"  {line}")

    # history (omit when empty; note can be multiline — use literal block)
    if node.history:
        lines.append("history:")
        for h in node.history:
            lines.append(f"  - who: {yaml_quote(h.who)}")
            lines.append(f"    date: {yaml_quote(h.date)}")
            if "\n" in (h.note or ""):
                lines.append("    note: |")
                for line in (h.note or "").split("\n"):
                    lines.append(f"      {_safe_literal_line(line)}")
            else:
                lines.append(f"    note: {yaml_quote(h.note)}")

    lines.append("---")
    return "\n".join(lines)


def _l1_ancestor_uid(graph: IntentGraph, uid: str) -> str | None:
    """Return the L1 ancestor (child-of-root) of *uid*, or None for root/L1 itself.

    Walks up until the next step would be the root. Returns the node whose parent
    is the root — i.e. the branch this node lives in. For the root, returns None;
    for an L1 node, returns that L1 node's own uid.
    """
    current = graph.get_node_or_none(uid)
    if current is None or graph.parent(uid) is None:
        return None  # root
    while True:
        parent = graph.parent(current.uid)
        if parent is None or graph.parent(parent.uid) is None:
            # parent is the root -> current is the L1 branch node
            return current.uid
        current = parent


def _up_link(node: IntentNode, graph: IntentGraph, layout_engine: str) -> str | None:
    """Engine-aware UP wiki-link line for *node*, or None for the root.

    In *portal* mode the per-node canvases don't exist, so UP points at the
    OVERVIEW (for a branch head) or the branch's L1 canvas (for a deeper node).
    In grid/radial it points at the canvas one level above where the node appears.
    """
    parent = graph.parent(node.uid)
    if parent is None:
        return None
    if layout_engine == "portal":
        l1 = _l1_ancestor_uid(graph, node.uid)
        if l1 is None or l1 == node.uid:
            target, label = "OVERVIEW.canvas", "OVERVIEW"
        else:
            target, label = f"{l1_canvas_stem(l1)}.canvas", l1
        return f"UP: [[{target}|{label}]]"
    grandparent = graph.parent(parent.uid)
    up_canvas_uid = grandparent.uid if grandparent is not None else parent.uid
    return f"UP: [[{up_canvas_uid}.canvas|{up_canvas_uid}]]"


def _is_l1(node: IntentNode, graph: IntentGraph) -> bool:
    """True if *node* is a direct child of the root (an L1 branch head)."""
    parent = graph.parent(node.uid)
    return parent is not None and graph.parent(parent.uid) is None


def _format_navigation(
    node: IntentNode,
    graph: IntentGraph,
    *,
    layout_engine: str = "grid",
    nav_links: str = "minimal",
) -> str:
    """Format UP / DOWN / CONTAINS wiki-link navigation lines.

    ``nav_links`` controls how much navigation is emitted:

    - ``"minimal"`` (default): only an ``UP`` link, and only on L1 branch nodes.
      Everything else gets no navigation — the links otherwise eat vertical space
      on every node for little benefit (the OVERVIEW / portal doors and Obsidian's
      own graph view cover navigation).
    - ``"full"``: the classic engine-aware UP / DOWN / CONTAINS on every node.
    - ``"none"``: no navigation lines at all.

    In *portal* mode the per-node/per-L1 canvases don't exist; UP/DOWN are
    retargeted at the OVERVIEW / ``L1_{uid}.canvas`` so no link dangles.
    """
    if nav_links == "none":
        return ""

    if nav_links == "minimal":
        # Only L1 nodes get an UP link; nothing else anywhere.
        if _is_l1(node, graph):
            up = _up_link(node, graph, layout_engine)
            return up or ""
        return ""

    # --- nav_links == "full": UP + DOWN + CONTAINS, engine-aware ---
    lines: list[str] = []
    parent = graph.parent(node.uid)
    children = graph.children(node.uid)

    up = _up_link(node, graph, layout_engine)
    if up is not None:
        lines.append(up)

    if children:
        if layout_engine == "portal":
            if parent is None:
                down_target = "OVERVIEW.canvas"
            else:
                l1 = _l1_ancestor_uid(graph, node.uid) or node.uid
                down_target = f"{l1_canvas_stem(l1)}.canvas"
        else:
            down_target = f"{node.uid}.canvas"
        lines.append(f"DOWN: [[{down_target}|EXPLODE]]")
        child_links = [f"[[{node_stem(c.uid, c.name)}]]" for c in children]
        lines.append(f"CONTAINS: {'  |  '.join(child_links)}")

    return "\n".join(lines)


# ------------------------------------------------------------------ #
#  edges.yaml generation                                             #
# ------------------------------------------------------------------ #

def _generate_edges_yaml(graph: IntentGraph) -> str:
    """Generate edges.yaml — the vault's authoritative edge record.

    Contains both **treearcs** (``type: treearc``, the parent→child tree
    structure) and **intentlinks** (``type: intentlink``). Treearcs are written
    first and are the source of truth for tree reconstruction on import, so the
    navigation wiki-links in node bodies are purely cosmetic and may be omitted
    (``--nav-links minimal|none``) without breaking round-trips.
    """
    lines: list[str] = []

    # Treearcs first — the tree structure, independent of display nav links.
    for node in graph.iter_nodes():
        for child in graph.children(node.uid):
            lines.append(f"- from: {node.uid}")
            lines.append(f"  to: {child.uid}")
            lines.append(f"  type: treearc")
            lines.append("")

    for link in graph.iter_links():
        lines.append(f"- from: {link.src}")
        lines.append(f"  to: {link.dst}")
        lines.append(f"  type: intentlink")
        # uid is preserved for round-trip fidelity
        lines.append(f"  uid: {yaml_quote(link.uid)}")
        # intent: use yaml_quote for safe escaping
        lines.append(f"  intent: {yaml_quote(link.intent)}")
        # Optional extended fields (new in the core library)
        if link.shape:
            lines.append(f"  shape: {json.dumps(link.shape)}")
        if link.parent:
            lines.append(f"  parent: {link.parent}")
        lines.append("")  # blank line between entries

    return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Canvas generation                                                 #
# ------------------------------------------------------------------ #

def _generate_canvas(
    parent_uid: str,
    graph: IntentGraph,
    config: LayoutConfig,
    *,
    nodes_prefix: str = "nodes",
    position_map: dict[str, NodeLayout] | None = None,
) -> str:
    """Generate Obsidian Canvas JSON for a parent node's children.

    When *position_map* is provided (radial layout), child positions are looked
    up from the single global map so a node sits at the same coordinates here as
    on the full-tree canvas, and the group boundary is the bounding box of those
    global positions. When it is empty/None (grid layout), the legacy per-canvas
    grid is used unchanged.
    """
    parent = graph.get_node(parent_uid)
    children = graph.children(parent_uid)

    if not children:
        return json.dumps({"nodes": [], "edges": []}, indent=4)

    use_global = bool(position_map)

    # Canvas nodes: group + file references
    canvas_nodes: list[dict[str, Any]] = []

    if not use_global:
        positions = compute_grid_positions(len(children), config)
        group_size = compute_group_size(len(children), config)
        canvas_nodes.append({
            "id": group_id(parent_uid),
            "x": config.group_offset_x,
            "y": config.group_offset_y,
            "width": group_size["width"],
            "height": group_size["height"],
            "type": "group",
            "label": parent.name,
        })

    # Child file-reference nodes
    child_uids: set[str] = set()
    child_boxes: list[NodeLayout] = []
    for i, child in enumerate(children):
        child_uids.add(child.uid)
        if use_global:
            nl = position_map.get(child.uid)
            if nl is None:
                continue
            x, y, w, h = nl.x, nl.y, nl.width, nl.height
            child_boxes.append(nl)
        else:
            x, y = positions[i]["x"], positions[i]["y"]
            w, h = config.node_width, config.node_height
        canvas_nodes.append({
            "id": file_node_id(child.uid),
            "type": "file",
            "file": f"{nodes_prefix}/{node_filename(child.uid, child.name)}",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
        })

    if use_global and child_boxes:
        # Group boundary = bounding box of children's global positions + padding.
        pad = 80
        min_x = min(b.x for b in child_boxes) - pad
        min_y = min(b.y for b in child_boxes) - pad - 60  # extra for label
        max_x = max(b.x + b.width for b in child_boxes) + pad
        max_y = max(b.y + b.height for b in child_boxes) + pad
        canvas_nodes.insert(0, {
            "id": group_id(parent_uid),
            "x": min_x,
            "y": min_y,
            "width": max_x - min_x,
            "height": max_y - min_y,
            "type": "group",
            "label": parent.name,
        })

    # Canvas edges: intentlinks between displayed siblings. Under radial, let
    # Obsidian auto-route (no fixed sides); under grid keep the exact legacy
    # key order so grid output stays byte-identical.
    canvas_edges: list[dict[str, Any]] = []
    for link in graph.iter_links():
        if link.src in child_uids and link.dst in child_uids:
            if use_global:
                canvas_edges.append({
                    "id": edge_id(link.src, link.dst),
                    "fromNode": file_node_id(link.src),
                    "toNode": file_node_id(link.dst),
                    "label": link.intent,
                })
            else:
                canvas_edges.append({
                    "id": edge_id(link.src, link.dst),
                    "fromNode": file_node_id(link.src),
                    "fromSide": "right",
                    "toNode": file_node_id(link.dst),
                    "toSide": "left",
                    "label": link.intent,
                })

    canvas = {"nodes": canvas_nodes, "edges": canvas_edges}
    return json.dumps(canvas, indent=4)


# ------------------------------------------------------------------ #
#  View canvas generation                                             #
# ------------------------------------------------------------------ #
#
#  Algorithm:
#  1. From the view nodes, walk UP to collect all ancestors (nodes
#     that are not in the view but are on the path to the root).
#  2. Each ancestor becomes a visual GROUP containing its children from
#     the visible set (view_uids ∪ ancestor_uids).
#  3. Each view node becomes a file-reference NODE inside its
#     ancestor's group.
#  4. Intentlinks are included when BOTH endpoints are in the visible
#     set.  Edges route to the group boundary for ancestors, or to the
#     file node for view nodes.
#
#  This is recursive and handles arbitrary nesting depth.
#

# Layout constants
_FILE_W, _FILE_H = 600, 560              # view nodes at top level
_INNER_FILE_W, _INNER_FILE_H = 500, 400  # view nodes inside groups
_GROUP_PAD = 80                           # padding inside group boundary
_GROUP_LABEL_H = 60                       # room for group label text
_CELL_GAP = 100                           # gap between grid cells
_GRID_COLS = 3                            # max columns per grid level

# Position tolerance for detecting user-moved nodes (pixels)
_PIN_TOLERANCE = 5


class _VizItem:
    """Internal: a node in the visual tree (either a group or a file)."""

    __slots__ = ("uid", "name", "is_group", "children", "w", "h", "x", "y")

    def __init__(self, uid: str, name: str, is_group: bool) -> None:
        self.uid = uid
        self.name = name
        self.is_group = is_group
        self.children: list[_VizItem] = []
        self.w = 0
        self.h = 0
        self.x = 0
        self.y = 0


def _collect_ancestors(view: View) -> set[str]:
    """Walk up from each view node to collect all non-view ancestors."""
    graph = view.graph
    view_uids = set(view.node_uids)
    ancestor_uids: set[str] = set()
    for uid in view_uids:
        current = graph.parent(uid)
        while current is not None:
            if current.uid in view_uids:
                break
            ancestor_uids.add(current.uid)
            current = graph.parent(current.uid)
    return ancestor_uids


def _build_viz_tree(
    view: View,
    ancestor_uids: set[str],
) -> list[_VizItem]:
    """Build the visual tree of _VizItem nodes for a view.

    Returns the top-level items (roots of the visual tree).
    """
    graph = view.graph
    view_uids = set(view.node_uids)
    visible_uids = view_uids | ancestor_uids

    viz_items: dict[str, _VizItem] = {}
    for uid in visible_uids:
        node = graph.get_node(uid)
        viz_items[uid] = _VizItem(uid, node.name, is_group=(uid in ancestor_uids))

    for uid in visible_uids:
        p = graph.parent(uid)
        if p is not None and p.uid in visible_uids:
            viz_items[p.uid].children.append(viz_items[uid])

    for vi in viz_items.values():
        vi.children.sort(key=lambda c: c.uid)

    top_items = [
        viz_items[uid]
        for uid in visible_uids
        if graph.parent(uid) is None or graph.parent(uid).uid not in visible_uids
    ]
    top_items.sort(key=lambda vi: vi.uid)
    return top_items


def compute_auto_layout(view: View) -> dict[str, NodeLayout]:
    """Compute grid positions for all visible nodes in a view.

    Visible nodes = view nodes + their ancestors up to the root.
    Ancestors become groups; view nodes become file-reference nodes.
    This is a **pure function** — no side effects, no file I/O.

    Parameters
    ----------
    view : View
        The view to compute layout for.

    Returns
    -------
    dict[str, NodeLayout]
        Mapping from node uid to computed position/size for every
        visible node (both view nodes and ancestor groups).
    """
    ancestor_uids = _collect_ancestors(view)
    top_items = _build_viz_tree(view, ancestor_uids)

    # Bottom-up: compute sizes
    for vi in top_items:
        _compute_size(vi, depth=0)

    # Top-down: assign positions
    cursor_x = _GROUP_PAD
    cursor_y = _GROUP_PAD
    for vi in top_items:
        _assign_positions(vi, cursor_x, cursor_y)
        cursor_x += vi.w + _CELL_GAP

    # Collect into NodeLayout dict
    result: dict[str, NodeLayout] = {}
    for vi in top_items:
        _collect_layouts(vi, result)
    return result


def export_view_canvas(
    view: View,
    output_path: str | Path,
    *,
    layout_config: LayoutConfig | None = None,
    nodes_prefix: str = "nodes",
) -> None:
    """Generate an Obsidian Canvas showing a working view.

    The algorithm:

    1. Collect every **ancestor** between the view nodes and the root.
       Each ancestor becomes a visual **group** labeled with its node name.
    2. View nodes become file-reference nodes placed inside their
       nearest ancestor group.
    3. All intentlinks whose **both** endpoints are in the visible set
       (view nodes + ancestors) are drawn.  Edges route to the group
       boundary for ancestors, or to the file node for view nodes.

    Parameters
    ----------
    view : View
        The view to visualize.
    output_path : str | Path
        Where to write the ``.canvas`` file.
    layout_config : LayoutConfig | None
        Reserved for future override.
    """
    graph = view.graph
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    view_uids = set(view.node_uids)
    ancestor_uids = _collect_ancestors(view)
    visible_uids = view_uids | ancestor_uids

    # --- Compute auto layout ---
    merged: dict[str, NodeLayout] = compute_auto_layout(view)

    # --- Build canvas nodes ---
    canvas_nodes: list[dict[str, Any]] = []
    for uid in visible_uids:
        node = graph.get_node(uid)
        nl = merged[uid]
        if uid in ancestor_uids:
            canvas_nodes.append({
                "id": group_id(uid),
                "x": nl.x,
                "y": nl.y,
                "width": nl.width,
                "height": nl.height,
                "type": "group",
                "label": node.name,
            })
        else:
            canvas_nodes.append({
                "id": file_node_id(uid),
                "type": "file",
                "file": f"{nodes_prefix}/{node_filename(uid, node.name)}",
                "x": nl.x,
                "y": nl.y,
                "width": nl.width,
                "height": nl.height,
            })

    # Sort canvas nodes for deterministic output (groups first, then by id)
    canvas_nodes.sort(key=lambda n: (0 if n["type"] == "group" else 1, n["id"]))

    # --- Intentlinks where both endpoints are visible ---
    canvas_edges: list[dict[str, Any]] = []
    for link in graph.iter_links():
        if link.src in visible_uids and link.dst in visible_uids:
            src_canvas = (
                group_id(link.src) if link.src in ancestor_uids
                else file_node_id(link.src)
            )
            dst_canvas = (
                group_id(link.dst) if link.dst in ancestor_uids
                else file_node_id(link.dst)
            )
            if src_canvas == dst_canvas:
                continue
            canvas_edges.append({
                "id": edge_id(link.src, link.dst),
                "fromNode": src_canvas,
                "fromSide": "right",
                "toNode": dst_canvas,
                "toSide": "left",
                "label": link.intent,
            })

    canvas = {"nodes": canvas_nodes, "edges": canvas_edges}
    path.write_text(json.dumps(canvas, indent=4), encoding="utf-8")


def detect_pinned_positions(
    view: View,
    canvas_path: str | Path,
    *,
    tolerance: int = _PIN_TOLERANCE,
) -> dict[str, NodeLayout]:
    """Read positions from a canvas file and detect user-moved nodes.

    Compares every node's position in the canvas against the auto-computed
    layout.  Returns only those positions that differ from auto (beyond
    ``tolerance`` pixels), i.e. the **pinned** positions.

    Parameters
    ----------
    view : View
        The view the canvas was generated from.
    canvas_path : str | Path
        Path to the ``.canvas`` file.
    tolerance : int
        Maximum pixel difference considered "same as auto" (default 5).

    Returns
    -------
    dict[str, NodeLayout]
        Sparse dict of user-pinned positions only.
    """
    canvas_path = Path(canvas_path)
    canvas = json.loads(canvas_path.read_text(encoding="utf-8"))
    auto = compute_auto_layout(view)

    # Build canvas-id -> uid mapping
    ancestor_uids = _collect_ancestors(view)
    view_uids = set(view.node_uids)
    visible_uids = view_uids | ancestor_uids

    id_to_uid: dict[str, str] = {}
    for uid in visible_uids:
        if uid in ancestor_uids:
            id_to_uid[group_id(uid)] = uid
        else:
            id_to_uid[file_node_id(uid)] = uid

    # Read positions from canvas and compare against auto
    pinned: dict[str, NodeLayout] = {}
    for cnode in canvas.get("nodes", []):
        uid = id_to_uid.get(cnode.get("id", ""))
        if uid is None:
            continue
        canvas_nl = NodeLayout(
            x=cnode["x"],
            y=cnode["y"],
            width=cnode.get("width", 600),
            height=cnode.get("height", 560),
        )
        auto_nl = auto.get(uid)
        if auto_nl is None:
            # Node in canvas but not in auto — store it
            pinned[uid] = canvas_nl
            continue
        # Compare with tolerance
        if (
            abs(canvas_nl.x - auto_nl.x) > tolerance
            or abs(canvas_nl.y - auto_nl.y) > tolerance
            or abs(canvas_nl.width - auto_nl.width) > tolerance
            or abs(canvas_nl.height - auto_nl.height) > tolerance
        ):
            pinned[uid] = canvas_nl

    return pinned


# ---- Recursive layout helpers ----

def _compute_size(vi: _VizItem, depth: int) -> None:
    """Bottom-up: compute width/height for a VizItem and all descendants."""
    if not vi.is_group:
        if depth == 0:
            vi.w, vi.h = _FILE_W, _FILE_H
        else:
            vi.w, vi.h = _INNER_FILE_W, _INNER_FILE_H
        return

    for child in vi.children:
        _compute_size(child, depth + 1)

    if not vi.children:
        vi.w, vi.h = _FILE_W, _FILE_H
        return

    max_cw = max(c.w for c in vi.children)
    max_ch = max(c.h for c in vi.children)
    n = len(vi.children)
    cols = min(n, _GRID_COLS)
    rows = (n + cols - 1) // cols

    inner_w = cols * max_cw + (cols - 1) * _CELL_GAP
    inner_h = rows * max_ch + (rows - 1) * _CELL_GAP

    vi.w = inner_w + 2 * _GROUP_PAD
    vi.h = inner_h + 2 * _GROUP_PAD + _GROUP_LABEL_H


def _assign_positions(vi: _VizItem, ox: int, oy: int) -> None:
    """Top-down: assign (x, y) positions for a VizItem and descendants."""
    vi.x = ox
    vi.y = oy

    if not vi.is_group or not vi.children:
        return

    max_cw = max(c.w for c in vi.children)
    max_ch = max(c.h for c in vi.children)
    cols = min(len(vi.children), _GRID_COLS)

    start_x = vi.x + _GROUP_PAD
    start_y = vi.y + _GROUP_PAD + _GROUP_LABEL_H

    for i, child in enumerate(vi.children):
        col = i % cols
        row = i // cols
        cell_x = start_x + col * (max_cw + _CELL_GAP)
        cell_y = start_y + row * (max_ch + _CELL_GAP)
        cx = cell_x + (max_cw - child.w) // 2
        cy = cell_y + (max_ch - child.h) // 2
        _assign_positions(child, cx, cy)


def _collect_layouts(vi: _VizItem, out: dict[str, NodeLayout]) -> None:
    """Recursively collect NodeLayout from a positioned _VizItem tree."""
    out[vi.uid] = NodeLayout(x=vi.x, y=vi.y, width=vi.w, height=vi.h)
    for child in vi.children:
        _collect_layouts(child, out)


def _flatten(
    vi: _VizItem,
    out: list[dict[str, Any]],
    *,
    nodes_prefix: str = "nodes",
) -> None:
    """Recursively flatten the VizItem tree into canvas node dicts."""
    if vi.is_group:
        out.append({
            "id": group_id(vi.uid),
            "x": vi.x,
            "y": vi.y,
            "width": vi.w,
            "height": vi.h,
            "type": "group",
            "label": vi.name,
        })
    else:
        out.append({
            "id": file_node_id(vi.uid),
            "type": "file",
            "file": f"{nodes_prefix}/{node_filename(vi.uid, vi.name)}",
            "x": vi.x,
            "y": vi.y,
            "width": vi.w,
            "height": vi.h,
        })

    for child in vi.children:
        _flatten(child, out, nodes_prefix=nodes_prefix)


# ------------------------------------------------------------------ #
#  FULL_TREE canvas — bottom-up layout with fixed node sizes          #
# ------------------------------------------------------------------ #
#
#  All nodes: fixed 560×650. No nesting/groups.
#  Sibling gap: 100px (room for intentlinks).
#  Cousin gap: 200px (nodes at same level with different parents).
#  Canvas width is COMPUTED bottom-up from leaf count + gaps.
#  Parents are centered over their children's span.
#  Each L1 branch gets a distinct color inherited by descendants.
#

_FT_NODE_W = 560
_FT_NODE_H = 650
_FT_SIBLING_GAP = 100            # gap between children of same parent
_FT_COUSIN_GAP = 200             # gap between subtrees of different parents
_FT_BAND_GAP = 150               # vertical gap between level bands
_FT_COLORS = ["1", "2", "3", "4", "5", "6"]  # Obsidian color codes, cycled


def _subtree_span(graph: IntentGraph, uid: str) -> int:
    """Bottom-up: compute horizontal span needed for a subtree.

    Leaf: NODE_W.
    Parent: sum(child spans) + SIBLING_GAP between each child.
    This gives the space needed to lay out all descendants without overlap.
    """
    children = graph.children(uid)
    if not children:
        return _FT_NODE_W
    child_spans = [_subtree_span(graph, c.uid) for c in children]
    return sum(child_spans) + _FT_SIBLING_GAP * (len(children) - 1)


def _assign_x(
    graph: IntentGraph,
    uid: str,
    left_x: int,
    positions: dict[str, int],
) -> None:
    """Top-down: assign x positions. Each node is centered over its children.

    For leaves, x = left_x (left edge of allocated span).
    For parents, children are placed left-to-right within the span,
    then parent x is set to center over children.
    """
    children = graph.children(uid)
    if not children:
        positions[uid] = left_x
        return

    # Place children left-to-right within this subtree's span
    cursor = left_x
    for i, child in enumerate(children):
        _assign_x(graph, child.uid, cursor, positions)
        cursor += _subtree_span(graph, child.uid)
        if i < len(children) - 1:
            cursor += _FT_SIBLING_GAP

    # Center parent over children span
    first_child_x = positions[children[0].uid]
    last_child_x = positions[children[-1].uid]
    children_center = (first_child_x + last_child_x + _FT_NODE_W) / 2
    positions[uid] = int(children_center - _FT_NODE_W / 2)


def _node_depth(graph: IntentGraph, uid: str) -> int:
    """Depth of a node (root=0)."""
    depth = 0
    current = graph.parent(uid)
    while current is not None:
        depth += 1
        current = graph.parent(current.uid)
    return depth


def _l1_color_map(graph: IntentGraph, root_uid: str) -> dict[str, str]:
    """Build uid -> color mapping. Each L1 branch gets a color, inherited."""
    color_map: dict[str, str] = {}
    l1_children = graph.children(root_uid)

    def _paint(uid: str, color: str) -> None:
        color_map[uid] = color
        for child in graph.children(uid):
            _paint(child.uid, color)

    for i, child in enumerate(l1_children):
        color = _FT_COLORS[i % len(_FT_COLORS)]
        _paint(child.uid, color)

    return color_map


def generate_full_tree_canvas(
    graph: IntentGraph,
    *,
    nodes_prefix: str = "nodes",
    canvas_width: int = 0,  # ignored, kept for API compat
    include_intentlinks: str = "all",
    focus_l1_uid: str | None = None,
    position_map: dict[str, NodeLayout] | None = None,
) -> str:
    """Generate a FULL_TREE.canvas with bottom-up computed layout.

    All nodes are 560×650 file-reference nodes (no groups/nesting).
    Siblings spaced 100px, cousins 200px.
    Canvas width is computed from tree shape.
    Each L1 branch has a distinct color inherited by descendants.
    Parents are centered over their children.

    When focus_l1_uid is set, only that L1's subtree is expanded; other L1
    nodes appear as leaves (single node each).

    Parameters
    ----------
    graph : IntentGraph
        The graph to visualize.
    nodes_prefix : str
        Vault-relative path prefix for node markdown files.
    canvas_width : int
        Ignored (width is computed). Kept for backwards compatibility.
    include_intentlinks : str
        Which intentlinks to draw: ``"all"`` (every link), ``"siblings"``
        (only links between nodes sharing a parent), or ``"none"`` (skip).
    focus_l1_uid : str | None
        If set, only this L1's subtree is expanded; other L1 nodes are leaves.

    Returns
    -------
    str
        Canvas JSON string.
    """
    roots = graph.roots()
    if not roots:
        return json.dumps({"nodes": [], "edges": []}, indent=4)

    root = roots[0]
    use_global = bool(position_map)
    positions: dict[str, int] = {}
    l1_children = graph.children(root.uid)

    if use_global:
        # Radial: every node's position comes from the one global map. The
        # whole tree is always the overview, so focus_l1_uid does not collapse
        # anything here (the radial full-tree IS the zoom-out view).
        positions = {uid: nl.x for uid, nl in position_map.items()}
    elif l1_children:
        cursor = 0
        for i, child in enumerate(l1_children):
            if focus_l1_uid is not None and child.uid != focus_l1_uid:
                # Collapsed L1: single node
                positions[child.uid] = cursor
                cursor += _FT_NODE_W
            else:
                _assign_x(graph, child.uid, cursor, positions)
                cursor += _subtree_span(graph, child.uid)
            if i < len(l1_children) - 1:
                cursor += _FT_COUSIN_GAP

        first_x = positions[l1_children[0].uid]
        last_x = positions[l1_children[-1].uid]
        root_center = (first_x + last_x + _FT_NODE_W) / 2
        positions[root.uid] = int(root_center - _FT_NODE_W / 2)
    else:
        positions[root.uid] = 0

    color_map = _l1_color_map(graph, root.uid)

    canvas_nodes: list[dict[str, Any]] = []
    for node_obj in graph.iter_nodes():
        uid = node_obj.uid
        if uid not in positions:
            continue
        if use_global:
            nl = position_map[uid]
            x, y, w, h = nl.x, nl.y, nl.width, nl.height
        else:
            depth = _node_depth(graph, uid)
            x = positions[uid]
            y = depth * (_FT_NODE_H + _FT_BAND_GAP)
            w, h = _FT_NODE_W, _FT_NODE_H
        entry: dict[str, Any] = {
            "id": file_node_id(uid),
            "type": "file",
            "file": f"{nodes_prefix}/{node_filename(uid, node_obj.name)}",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
        }
        if uid in color_map:
            entry["color"] = color_map[uid]
        canvas_nodes.append(entry)

    canvas_edges: list[dict[str, Any]] = []
    for node_obj in graph.iter_nodes():
        if node_obj.uid not in positions:
            continue
        for child in graph.children(node_obj.uid):
            if child.uid not in positions:
                continue
            if use_global:
                # Radial: auto-route (fixed bottom->top sides are wrong on rings).
                canvas_edges.append({
                    "id": f"arc_{edge_id(node_obj.uid, child.uid)}",
                    "fromNode": file_node_id(node_obj.uid),
                    "toNode": file_node_id(child.uid),
                })
            else:
                canvas_edges.append({
                    "id": f"arc_{edge_id(node_obj.uid, child.uid)}",
                    "fromNode": file_node_id(node_obj.uid),
                    "fromSide": "bottom",
                    "toNode": file_node_id(child.uid),
                    "toSide": "top",
                })

    # Step 6: intentlink edges (horizontal, distinct from treearcs)
    if include_intentlinks != "none":
        for link in graph.iter_links():
            if link.src not in positions or link.dst not in positions:
                continue
            if include_intentlinks == "siblings":
                src_parent = graph.parent(link.src)
                dst_parent = graph.parent(link.dst)
                src_pid = src_parent.uid if src_parent else None
                dst_pid = dst_parent.uid if dst_parent else None
                if src_pid != dst_pid:
                    continue
            canvas_edges.append({
                "id": f"ilink_{edge_id(link.src, link.dst)}",
                "fromNode": file_node_id(link.src),
                "fromSide": "right",
                "toNode": file_node_id(link.dst),
                "toSide": "left",
                "label": link.intent,
            })

    canvas = {"nodes": canvas_nodes, "edges": canvas_edges}
    return json.dumps(canvas, indent=4)


# ------------------------------------------------------------------ #
#  Portal (nested) layout                                             #
# ------------------------------------------------------------------ #
#
#  Two composed regimes:
#   - Each L1 branch (L1 + all descendants) is rendered as its own canvas,
#     laid out as a clean *vertical tree* (reuses _assign_x/_subtree_span).
#   - The OVERVIEW canvas places ROOT at the centre and one *portal* node per
#     L1 (an Advanced-Canvas file-node with "portal": true embedding that L1's
#     canvas) arranged radially around ROOT, each sized to its subtree's bbox.
#
#  Portals render as embedded canvases only in the Advanced Canvas plugin; in
#  vanilla Obsidian a portal file-node degrades to a plain link tile.

# Per-L1 subtree canvas: tighter than FULL_TREE (no cousin gaps needed — one
# branch only). Reuses the FT node size + band gap for visual continuity.
_L1_MARGIN = 120  # padding around the subtree inside its canvas


def l1_canvas_stem(l1_uid: str) -> str:
    """Vault filename stem for an L1 subtree canvas (no extension)."""
    return f"L1_{l1_uid}"


def portal_node_id(l1_uid: str) -> str:
    """Canvas node id for the portal embedding an L1 subtree."""
    return f"portal_{to_canvas_id(l1_uid)}"


def _generate_l1_subtree_canvas(
    graph: IntentGraph,
    l1_uid: str,
    *,
    nodes_prefix: str = "nodes",
) -> tuple[str, dict[str, int]]:
    """Render one L1 + all descendants as a vertical tree canvas.

    Returns ``(canvas_json, bbox)`` where bbox is
    ``{"width": int, "height": int}`` of the laid-out content (used to size the
    portal that embeds it). The subtree is rooted at *l1_uid* (depth 0 = the L1
    node itself), so the canvas contains exactly this branch.
    """
    # Horizontal positions for the whole subtree, rooted at the L1.
    positions: dict[str, int] = {}
    _assign_x(graph, l1_uid, 0, positions)

    l1_depth = _node_depth(graph, l1_uid)
    color_map = _l1_color_map(graph, graph.roots()[0].uid) if graph.roots() else {}

    # Collect every node in this subtree (BFS from the L1).
    subtree_uids: list[str] = []
    stack = [l1_uid]
    while stack:
        uid = stack.pop()
        subtree_uids.append(uid)
        stack.extend(c.uid for c in graph.children(uid))

    canvas_nodes: list[dict[str, Any]] = []
    min_x = min(positions[u] for u in subtree_uids)

    effective: dict[str, NodeLayout] = {}
    for uid in subtree_uids:
        node_obj = graph.get_node(uid)
        rel_depth = _node_depth(graph, uid) - l1_depth
        fresh = NodeLayout(
            x=positions[uid] - min_x + _L1_MARGIN,
            y=rel_depth * (_FT_NODE_H + _FT_BAND_GAP) + _L1_MARGIN,
            width=_FT_NODE_W,
            height=_FT_NODE_H,
        )
        # A pinned box (human move/resize in this branch canvas) wins whole.
        box = _pinned_box(node_obj, "portal") or fresh
        effective[uid] = box
        entry: dict[str, Any] = {
            "id": file_node_id(uid),
            "type": "file",
            "file": f"{nodes_prefix}/{node_filename(uid, node_obj.name)}",
            "x": box.x,
            "y": box.y,
            "width": box.width,
            "height": box.height,
        }
        if uid in color_map:
            entry["color"] = color_map[uid]
        canvas_nodes.append(entry)

    # Treearc edges within the subtree (vertical: bottom -> top).
    canvas_edges: list[dict[str, Any]] = []
    subtree_set = set(subtree_uids)
    for uid in subtree_uids:
        for child in graph.children(uid):
            if child.uid not in subtree_set:
                continue
            canvas_edges.append({
                "id": f"arc_{edge_id(uid, child.uid)}",
                "fromNode": file_node_id(uid),
                "fromSide": "bottom",
                "toNode": file_node_id(child.uid),
                "toSide": "top",
            })

    # Content bbox from the boxes actually placed (pins can stretch it).
    bb_min_x = min(b.x for b in effective.values())
    bb_max_x = max(b.x + b.width for b in effective.values())
    bb_min_y = min(b.y for b in effective.values())
    bb_max_y = max(b.y + b.height for b in effective.values())
    bbox = {
        "width": (bb_max_x - bb_min_x) + 2 * _L1_MARGIN,
        "height": (bb_max_y - bb_min_y) + 2 * _L1_MARGIN,
    }
    canvas = {"nodes": canvas_nodes, "edges": canvas_edges}
    return json.dumps(canvas, indent=4), bbox


def generate_portal_overview_canvas(
    graph: IntentGraph,
    bboxes: dict[str, dict[str, int]],
    *,
    nodes_prefix: str = "nodes",
    viz_prefix: str = "viz",
    ring_gap: int = 400,
) -> str:
    """Render the OVERVIEW: ROOT centre + one L1 portal each, placed radially.

    *bboxes* maps L1 uid -> ``{"width","height"}`` (from
    :func:`_generate_l1_subtree_canvas`). Portals are sized to their subtree
    bbox; the ring radius grows so the largest portal cannot overlap its
    neighbour. Treearc edges connect ROOT to each portal.
    """
    roots = graph.roots()
    if not roots:
        return json.dumps({"nodes": [], "edges": []}, indent=4)
    root = roots[0]
    l1_children = sorted(graph.children(root.uid), key=lambda c: c.uid)
    color_map = _l1_color_map(graph, root.uid)

    n = len(l1_children)
    canvas_nodes: list[dict[str, Any]] = []
    canvas_edges: list[dict[str, Any]] = []

    # ROOT node at centre — unless a human pinned its box on the OVERVIEW.
    root_w, root_h = _FT_NODE_W, _FT_NODE_H
    root_fresh = NodeLayout(
        x=-root_w // 2, y=-root_h // 2, width=root_w, height=root_h,
    )
    root_box = _pinned_box(root, "portal") or root_fresh
    canvas_nodes.append({
        "id": file_node_id(root.uid),
        "type": "file",
        "file": f"{nodes_prefix}/{node_filename(root.uid, root.name)}",
        "x": root_box.x,
        "y": root_box.y,
        "width": root_box.width,
        "height": root_box.height,
    })

    if n == 0:
        return json.dumps({"nodes": canvas_nodes, "edges": canvas_edges}, indent=4)

    # Ring radius: large enough that the biggest portal's half-diagonal plus the
    # root's extent fits without portals colliding. Use the max portal diagonal
    # and the angular step to derive a safe radius.
    import math
    max_diag = max(
        math.hypot(bboxes[c.uid]["width"], bboxes[c.uid]["height"])
        for c in l1_children
    )
    angle_step = 2 * math.pi / n
    # Chord between adjacent portal centres must exceed max portal size; solve
    # radius from chord = 2 r sin(step/2) >= max_diag.
    chord_r = (max_diag + ring_gap) / (2 * math.sin(angle_step / 2)) if n > 1 else 0.0
    radius = max(chord_r, max_diag / 2 + root_h + ring_gap)

    for i, l1 in enumerate(l1_children):
        bbox = bboxes[l1.uid]
        pw, ph = bbox["width"], bbox["height"]
        # Distribute evenly around a full circle, starting at the top (-90deg).
        theta = -math.pi / 2 + i * angle_step
        cx = radius * math.cos(theta)
        cy = radius * math.sin(theta)
        # A pinned portal position (human drag on the OVERVIEW ring) wins.
        # Position only: portal size is plugin-forced to the content bbox.
        pin_xy = _portal_xy(l1, "portal", "pinned")
        px, py = pin_xy if pin_xy is not None else (
            int(round(cx - pw / 2)), int(round(cy - ph / 2)),
        )
        entry: dict[str, Any] = {
            "id": portal_node_id(l1.uid),
            "type": "file",
            "file": f"{viz_prefix}/{l1_canvas_stem(l1.uid)}.canvas",
            "portal": True,
            "x": px,
            "y": py,
            "width": pw,
            "height": ph,
        }
        if l1.uid in color_map:
            entry["color"] = color_map[l1.uid]
        canvas_nodes.append(entry)

        canvas_edges.append({
            "id": f"arc_{edge_id(root.uid, l1.uid)}",
            "fromNode": file_node_id(root.uid),
            "toNode": portal_node_id(l1.uid),
        })

    canvas = {"nodes": canvas_nodes, "edges": canvas_edges}
    return json.dumps(canvas, indent=4)


# ------------------------------------------------------------------ #
#  Lens canvas export                                                  #
# ------------------------------------------------------------------ #
#
#  Same bottom-up treemap layout as FULL_TREE, but:
#  - Node sizes vary by LOD (skeleton: 300×150, lean: 560×400, full: 560×650)
#  - Skeleton nodes rendered as text-only canvas nodes (no .md file)
#  - Lean nodes get .md with intent + epistemic_state only
#  - Full nodes get .md with all fields
#  - IntentLinks follow lens visibility rules (both endpoints ≥ lean)
#

_LENS_SIZES: dict[str, tuple[int, int]] = {
    "skeleton": (300, 150),
    "lean": (560, 400),
    "full": (560, 650),
}


def _format_lean_frontmatter(node: IntentNode) -> str:
    """Format YAML frontmatter with only intent + epistemic_state."""
    lines: list[str] = ["---"]
    lines.append("intent: |")
    lines.extend(yaml_literal_block(node.intent))
    if node.epistemic_state:
        lines.append(f"epistemic_state: {yaml_quote(node.epistemic_state)}")
    lines.append("---")
    return "\n".join(lines)


def _lens_children(treearcs: list[tuple[str, str]], uid: str) -> list[str]:
    """Get sorted children of a node from treearc list."""
    return sorted(child for parent, child in treearcs if parent == uid)


def _lens_parent(treearcs: list[tuple[str, str]], uid: str) -> str | None:
    """Get parent of a node from treearc list."""
    for parent, child in treearcs:
        if child == uid:
            return parent
    return None


def _lens_roots(treearcs: list[tuple[str, str]], all_uids: set[str]) -> list[str]:
    """Find root nodes (no parent in treearcs)."""
    children = {child for _, child in treearcs}
    return sorted(uid for uid in all_uids if uid not in children)


def _lens_depth(treearcs: list[tuple[str, str]], uid: str) -> int:
    """Depth of a node (root=0)."""
    depth = 0
    current = uid
    while True:
        p = _lens_parent(treearcs, current)
        if p is None:
            return depth
        depth += 1
        current = p


def _lens_subtree_span(
    treearcs: list[tuple[str, str]],
    uid: str,
    lod_map: dict[str, LOD],
) -> int:
    """Bottom-up: compute horizontal span for a subtree with variable node widths."""
    children = _lens_children(treearcs, uid)
    if not children:
        w, _ = _LENS_SIZES[lod_map.get(uid, LOD.skeleton).value]
        return w
    child_spans = [_lens_subtree_span(treearcs, c, lod_map) for c in children]
    return sum(child_spans) + _FT_SIBLING_GAP * (len(children) - 1)


def _lens_assign_x(
    treearcs: list[tuple[str, str]],
    uid: str,
    left_x: int,
    positions: dict[str, int],
    lod_map: dict[str, LOD],
) -> None:
    """Top-down: assign x positions with variable node widths."""
    children = _lens_children(treearcs, uid)
    if not children:
        positions[uid] = left_x
        return

    cursor = left_x
    for i, child in enumerate(children):
        _lens_assign_x(treearcs, child, cursor, positions, lod_map)
        cursor += _lens_subtree_span(treearcs, child, lod_map)
        if i < len(children) - 1:
            cursor += _FT_SIBLING_GAP

    # Center parent over children span
    first_x = positions[children[0]]
    last_x = positions[children[-1]]
    last_w, _ = _LENS_SIZES[lod_map.get(children[-1], LOD.skeleton).value]
    my_w, _ = _LENS_SIZES[lod_map.get(uid, LOD.skeleton).value]
    children_center = (first_x + last_x + last_w) / 2
    positions[uid] = int(children_center - my_w / 2)


def _lens_l1_color_map(
    treearcs: list[tuple[str, str]],
    root_uid: str,
) -> dict[str, str]:
    """Build uid -> color mapping for lens. Each L1 branch gets a color."""
    color_map: dict[str, str] = {}
    l1_children = _lens_children(treearcs, root_uid)

    def _paint(uid: str, color: str) -> None:
        color_map[uid] = color
        for child in _lens_children(treearcs, uid):
            _paint(child, color)

    for i, child in enumerate(l1_children):
        color = _FT_COLORS[i % len(_FT_COLORS)]
        _paint(child, color)

    return color_map


def export_lens_canvas(
    lens: Lens,
    output_dir: str | Path,
    *,
    vault_root: str | Path | None = None,
    include_intentlinks: str = "all",
) -> None:
    """Export a Lens as an Obsidian canvas with LOD-aware node rendering.

    Creates a single ``.canvas`` file plus LOD-filtered ``.md`` files for
    lean and full nodes.  Skeleton nodes appear as text-only canvas cards.

    Output structure::

        output_dir/
            nodes/              # lean + full .md files
                {uid} {name}.md
            LENS_{name}.canvas

    Parameters
    ----------
    lens : Lens
        The lens to export.
    output_dir : str | Path
        Output directory (e.g. ``projection_ig/lens_myview/``).
    vault_root : str | Path | None
        Obsidian vault root for computing file paths.
    include_intentlinks : str
        ``"all"`` (every visible link), ``"siblings"`` (same parent only),
        or ``"none"``.
    """
    out = Path(output_dir).resolve()
    nodes_dir = out / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    # Compute vault-relative nodes prefix
    if vault_root is not None:
        vroot = Path(vault_root).resolve()
        nodes_prefix = str(out.relative_to(vroot) / "nodes")
    else:
        nodes_prefix = "nodes"

    # Build LOD map: uid -> LOD
    lod_map: dict[str, LOD] = {
        uid: meta.lod for uid, meta in lens.node_metadata.items()
    }

    # 1. Write LOD-filtered .md files (lean + full only)
    for uid, node in lens.nodes.items():
        lod = lod_map.get(uid, LOD.skeleton)
        if lod == LOD.skeleton:
            continue
        if lod == LOD.lean:
            content = _format_lean_frontmatter(node)
        else:  # full
            content = _format_frontmatter(node)
        path = nodes_dir / node_filename(uid, node.name)
        path.write_text(content, encoding="utf-8")

    # 2. Layout computation (same algorithm as FULL_TREE, variable sizes)
    treearcs = lens.treearcs
    all_uids = set(lens.nodes.keys())
    roots = _lens_roots(treearcs, all_uids)

    if not roots:
        canvas_json = json.dumps({"nodes": [], "edges": []}, indent=4)
        (out / f"LENS_{lens.meta.name}.canvas").write_text(
            canvas_json, encoding="utf-8")
        return

    root = roots[0]

    # X positions
    positions: dict[str, int] = {}
    l1_children = _lens_children(treearcs, root)

    if l1_children:
        cursor = 0
        for i, child in enumerate(l1_children):
            _lens_assign_x(treearcs, child, cursor, positions, lod_map)
            cursor += _lens_subtree_span(treearcs, child, lod_map)
            if i < len(l1_children) - 1:
                cursor += _FT_COUSIN_GAP

        # Center root over L1 children
        first_x = positions[l1_children[0]]
        last_x = positions[l1_children[-1]]
        last_w, _ = _LENS_SIZES[lod_map.get(l1_children[-1], LOD.skeleton).value]
        root_w, _ = _LENS_SIZES[lod_map.get(root, LOD.skeleton).value]
        root_center = (first_x + last_x + last_w) / 2
        positions[root] = int(root_center - root_w / 2)
    else:
        positions[root] = 0

    # Color map
    color_map = _lens_l1_color_map(treearcs, root)

    # 3. Build canvas nodes
    canvas_nodes: list[dict[str, Any]] = []
    for uid, node in lens.nodes.items():
        if uid not in positions:
            continue
        lod = lod_map.get(uid, LOD.skeleton)
        w, h = _LENS_SIZES[lod.value]
        depth = _lens_depth(treearcs, uid)
        y = depth * (_FT_NODE_H + _FT_BAND_GAP)

        if lod == LOD.skeleton:
            entry: dict[str, Any] = {
                "id": file_node_id(uid),
                "type": "text",
                "text": f"{uid}\n{node.name}",
                "x": positions[uid],
                "y": y,
                "width": w,
                "height": h,
            }
        else:
            entry = {
                "id": file_node_id(uid),
                "type": "file",
                "file": f"{nodes_prefix}/{node_filename(uid, node.name)}",
                "x": positions[uid],
                "y": y,
                "width": w,
                "height": h,
            }

        if uid in color_map:
            entry["color"] = color_map[uid]
        canvas_nodes.append(entry)

    # 4. Treearc edges
    canvas_edges: list[dict[str, Any]] = []
    for parent_uid, child_uid in treearcs:
        if parent_uid in positions and child_uid in positions:
            canvas_edges.append({
                "id": f"arc_{edge_id(parent_uid, child_uid)}",
                "fromNode": file_node_id(parent_uid),
                "fromSide": "bottom",
                "toNode": file_node_id(child_uid),
                "toSide": "top",
            })

    # 5. IntentLink edges (both endpoints must be ≥ lean)
    if include_intentlinks != "none":
        for link in lens.intentlinks.values():
            src_lod = lod_map.get(link.src, LOD.skeleton)
            dst_lod = lod_map.get(link.dst, LOD.skeleton)
            if src_lod < LOD.lean or dst_lod < LOD.lean:
                continue
            if link.src not in positions or link.dst not in positions:
                continue
            if include_intentlinks == "siblings":
                src_p = _lens_parent(treearcs, link.src)
                dst_p = _lens_parent(treearcs, link.dst)
                if src_p != dst_p:
                    continue
            canvas_edges.append({
                "id": f"ilink_{edge_id(link.src, link.dst)}",
                "fromNode": file_node_id(link.src),
                "fromSide": "right",
                "toNode": file_node_id(link.dst),
                "toSide": "left",
                "label": link.intent,
            })

    canvas = {"nodes": canvas_nodes, "edges": canvas_edges}
    canvas_path = out / f"LENS_{lens.meta.name}.canvas"
    canvas_path.write_text(json.dumps(canvas, indent=4), encoding="utf-8")
