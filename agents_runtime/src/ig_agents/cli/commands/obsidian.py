"""ig-tool ``obsidian`` command: export/import/diff/merge/canvas operations.

``cmd_obsidian`` dispatches across 8 actions (export, import, diff, merge,
export-canvas, export-tree, detect-pins, export-lens-canvas). export-canvas
and detect-pins select their working view with ``--nodes``.

Includes the in-progress radial-canvas-layout WIP in ``_obsidian_export``
(``--layout``/``--radial-ring-gap``/``--radial-sweep``, delegating to
``intentgraph.obsidian.RadialConfig``) carried along as-is, uncommitted
mid-development state and all — not reverted, not "cleaned up".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from intentgraph.serial.json_yaml import save_graph
from intentgraph.models.view import View
from intentgraph.obsidian import (
    detect_pinned_positions,
    diff_obsidian_vs_graph,
    export_lens_canvas,
    export_to_obsidian,
    export_view_canvas,
    generate_full_tree_canvas,
    import_from_obsidian,
    load_snapshot,
    SNAPSHOT_FILENAME,
    merge_obsidian_into_graph,
    graph_hash,
)

# _die, _load_graph, _write_output, _summary — single canonical copies in
# cli/common.py.
from ig_agents.cli.common import _die, _load_graph, _save_graph, _write_output, _summary


def add_parser(sub: Any) -> None:
    """Register the ``obsidian`` subcommand (8 actions) on *sub*."""
    p_obs = sub.add_parser(
        "obsidian",
        help="Obsidian vault operations (export, import, diff, merge, export-canvas, export-tree, detect-pins, export-lens-canvas)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Sub-subcommands:\n"
            "  obsidian export             IG → vault (.md per node + edges.yaml + .canvas)\n"
            "  obsidian import             vault → IG (fresh import)\n"
            "  obsidian diff               compare vault against reference graph\n"
            "  obsidian merge              vault → IG (merge edits back, content-only)\n"
            "  obsidian export-canvas      working view (--nodes) → single .canvas file\n"
            "  obsidian export-tree        ROOT + L1 canvas (renamed from full-tree)\n"
            "  obsidian export-lens-canvas lens → LOD-aware canvas (renamed from lens-canvas)\n"
            "  obsidian detect-pins        find user-moved nodes for re-import\n"
            "Notes:\n"
            "  - Accepts both .json and .yaml graphs (no conversion needed).\n"
        ),
    )
    obs_sub = p_obs.add_subparsers(dest="action", required=True)

    # obsidian export
    p_obs_exp = obs_sub.add_parser(
        "export",
        help="Export IntentGraph to Obsidian vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  ig-tool obsidian export -g graph.yaml -o vault/ --force\n"
            "  ig-tool obsidian export -g pig.json -o multi_vault/projection_ig/ \\\n"
            "      --vault-root multi_vault/ --intentlinks siblings\n"
            "Notes:\n"
            "  - Accepts both YAML and JSON graphs.\n"
            "  - --vault-root is needed when the vault root differs from the output dir.\n"
            "  - --intentlinks: 'all' (default), 'siblings' only, or 'none'.\n"
        ),
    )
    p_obs_exp.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_obs_exp.add_argument("-o", "--output", required=True, metavar="VAULT_DIR", help="Output vault directory")
    p_obs_exp.add_argument("--vault-root", metavar="VAULT_ROOT", help="Obsidian vault root directory (for multi-graph vaults). Canvas file paths will be relative to this directory. Defaults to output directory.")
    p_obs_exp.add_argument("--force", action="store_true", help="Overwrite existing vault directory")
    p_obs_exp.add_argument("--intentlinks", choices=["all", "siblings", "none"], default="all",
                          help="Which intentlinks to draw in _FT_* / __FT_ROOT canvases: all (default), siblings only, or none")
    p_obs_exp.add_argument("--no-ft-canvases", action="store_true",
                          help="Do not write __FT_ROOT.canvas and _FT_{L1}.canvas (export writes them by default)")
    p_obs_exp.add_argument("--layout", choices=["grid", "radial", "portal"], default="grid",
                          help="Canvas layout engine: 'grid' (default, legacy 3-column), 'radial' "
                               "(one global multi-ring layout), or 'portal' (OVERVIEW canvas with ROOT + "
                               "each L1 branch embedded as a radial portal; each L1 laid out as a vertical "
                               "tree; requires the Advanced Canvas plugin). radial/portal persist layout to "
                               "data_registry.obsidian_layout, detect human moves/resizes in an existing "
                               "vault's canvases as sticky pins, and SAVE THE GRAPH FILE back so pins "
                               "survive re-export, merge, and new vaults")
    p_obs_exp.add_argument("--radial-ring-gap", type=int, default=900, metavar="PX",
                          help="Radial only: base pixel distance between depth rings (default 900)")
    p_obs_exp.add_argument("--radial-sweep", type=float, default=180.0, metavar="DEG",
                          help="Radial only: total fan-out arc in degrees (default 180; auto-expands toward 360 on spill)")
    p_obs_exp.add_argument("--nav-links", choices=["minimal", "full", "none"], default="minimal",
                          help="Navigation wiki-links in each node file: 'minimal' (default: only an UP link on L1 "
                               "branch nodes), 'full' (UP/DOWN/CONTAINS on every node), or 'none'")
    p_obs_exp.add_argument("--fit-height", action="store_true",
                          help="Size each node's canvas box to its estimated content height instead of the fixed "
                               "tall default: a per-field pixel estimate of the frontmatter, plus the measured "
                               "rendered height of any images embedded in the node body (e.g. a '## Samples' "
                               "section, sized with Pillow). Errs slightly tall so a box never clips.")
    p_obs_exp.add_argument("--no-install-plugins", action="store_true",
                          help="Do not install the Obsidian community plugins this layout needs into the "
                               "vault's .obsidian/ (portal needs Advanced Canvas to render its embeds; "
                               "without it portals show as static file cards that never expand). Obsidian has "
                               "no global plugin install, so each generated vault carries its own copy, read "
                               "from ~/.local/share/intentgraph/obsidian-plugins/ "
                               "($INTENTGRAPH_OBSIDIAN_PLUGIN_DIR to override).")

    # obsidian import
    p_obs_imp = obs_sub.add_parser(
        "import",
        help="Import Obsidian vault to IntentGraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  ig-tool obsidian import -i vault/ -o graph.json\n"
            "Notes:\n"
            "  - Round-trip with 'obsidian export' preserves node intent + treearcs.\n"
            "  - Use 'obsidian diff' to inspect changes before importing.\n"
        ),
    )
    p_obs_imp.add_argument("-i", "--vault-dir", required=True, metavar="VAULT_DIR", help="Input vault directory")
    p_obs_imp.add_argument("-o", "--output", required=True, help="Output graph file path (JSON or YAML)")

    # obsidian diff
    p_obs_diff = obs_sub.add_parser(
        "diff",
        help="Compare Obsidian vault against reference graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  ig-tool obsidian diff -g graph.json -i vault/ -o diff.yaml\n"
        ),
    )
    p_obs_diff.add_argument("-g", "--graph", required=True, help="Reference graph file (JSON or YAML)")
    p_obs_diff.add_argument("-i", "--vault-dir", required=True, metavar="VAULT_DIR", help="Vault directory to compare")
    p_obs_diff.add_argument("-o", "--output", help="Write diff report to this path")
    p_obs_diff.add_argument("--names-only", action="store_true",
                            help="Report only changed field NAMES per node (default: include old -> new values)")

    # obsidian merge
    p_obs_merge = obs_sub.add_parser(
        "merge",
        help="Merge Obsidian vault edits back into canonical graph (content-only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  ig-tool obsidian merge -g graph.json -i vault/\n"
            "  ig-tool obsidian merge -i vault/ -o merged.yaml\n"
            "Notes:\n"
            "  - Content-only merge: field updates applied, structural changes ignored.\n"
            "  - Conflict detection uses .ig-sync.yaml snapshot baseline.\n"
            "  - If canonical graph changed since export, merge fails unless --force.\n"
            "  - Use --dry-run to preview changes without applying.\n"
        ),
    )
    p_obs_merge.add_argument("-g", "--graph", help="Canonical graph file (JSON or YAML). If omitted, resolves from vault snapshot.")
    p_obs_merge.add_argument("-i", "--vault-dir", required=True, metavar="VAULT_DIR", help="Vault directory to merge from")
    p_obs_merge.add_argument("-o", "--output", help="Output graph path (default: in-place over input graph)")
    p_obs_merge.add_argument("--dry-run", action="store_true", help="Preview merge without applying changes")
    p_obs_merge.add_argument("--force", action="store_true", help="Proceed despite canonical graph changes since export")
    p_obs_merge.add_argument("--skip-malformed", action="store_true", help="Skip unparseable node files instead of halting")
    p_obs_merge.add_argument("-m", "--message", help="One-liner history note for this change (commit-style)")
    p_obs_merge.add_argument("--role", help="Agent role for provenance (history who = agent:<role>)")

    # obsidian export-canvas (was: canvas)
    p_obs_canvas = obs_sub.add_parser(
        "export-canvas",
        help="Export a working view (--nodes) to an Obsidian canvas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  ig-tool obsidian export-canvas -g graph.json --nodes E,T,L -o vault/viz/my.canvas\n"
            "Notes:\n"
            "  - Ancestors of the selected nodes are drawn as groups.\n"
        ),
    )
    p_obs_canvas.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_obs_canvas.add_argument("--nodes", metavar="UIDS",
                              help="Comma-separated node UIDs forming the view to draw")
    p_obs_canvas.add_argument("-o", "--output", required=True, help="Output .canvas file path")

    # obsidian export-tree (was: full-tree)
    p_obs_ft = obs_sub.add_parser(
        "export-tree",
        help="Export FT canvas (ROOT + L1; was: full-tree)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool obsidian export-tree -g graph.json -o vault/viz/__FT_ROOT.canvas\n"
            "  ig-tool obsidian export-tree -g graph.json --focus-l1 PARSER \\\n"
            "      -o vault/viz/_FT_PARSER.canvas\n"
            "Notes:\n"
            "  - Renamed from 'full-tree'.\n"
            "  - Output filename convention: __FT_ROOT.canvas (root) or _FT_<L1>.canvas (focus).\n"
            "  - --intentlinks: 'all' (default), 'siblings', or 'none'.\n"
        ),
    )
    p_obs_ft.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_obs_ft.add_argument("-o", "--output", required=True, help="Output .canvas file path")
    p_obs_ft.add_argument("--nodes-prefix", metavar="PREFIX", help="Vault-relative path prefix for node .md files (default: nodes)")
    p_obs_ft.add_argument("--width", type=int, metavar="PIXELS", help="Canvas width in pixels (default: 2400)")
    p_obs_ft.add_argument("--intentlinks", choices=["all", "siblings", "none"], default="all",
                          help="Which intentlinks to draw: all (default), siblings only, or none")
    p_obs_ft.add_argument("--focus-l1", metavar="UID", help="L1 UID to expand (default: none = full tree). Use -o viz/__FT_ROOT.canvas for root, viz/_FT_{L1}.canvas for L1 focus (leading _ sorts FT canvases to top).")

    # obsidian detect-pins
    p_obs_pins = obs_sub.add_parser(
        "detect-pins",
        help="Detect user-moved nodes in canvas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  ig-tool obsidian detect-pins -g graph.json --nodes E,T,L \\\n"
            "      --canvas vault/viz/my.canvas -o pins.yaml\n"
            "Notes:\n"
            "  - Compares canvas node positions against the auto-layout to find pinned nodes.\n"
            "  - --tolerance PIXELS (default 5) controls how much drift counts as 'unmoved'.\n"
        ),
    )
    p_obs_pins.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_obs_pins.add_argument("--nodes", metavar="UIDS",
                            help="Comma-separated node UIDs forming the view the canvas was generated from")
    p_obs_pins.add_argument("--canvas", required=True, metavar="FILE", help="Canvas file to analyze")
    p_obs_pins.add_argument("-o", "--output", help="Write pinned positions report to this path")
    p_obs_pins.add_argument("--tolerance", type=int, metavar="PIXELS", help="Pin detection tolerance (default: 5)")

    # obsidian export-lens-canvas (was: lens-canvas)
    p_obs_lc = obs_sub.add_parser(
        "export-lens-canvas",
        help="Export lens as Obsidian canvas with LOD-aware rendering (was: lens-canvas)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  ig-tool obsidian export-lens-canvas -l lens.yaml -o vault/viz/lens_view/ \\\n"
            "      --vault-root vault/\n"
            "Notes:\n"
            "  - Renamed from 'lens-canvas'.\n"
            "  - Output is a directory containing nodes/ + a .canvas file.\n"
        ),
    )

    p_obs_lc.add_argument("-l", "--lens", required=True, help="Path to lens YAML/JSON file")
    p_obs_lc.add_argument("-o", "--output", required=True, metavar="OUTPUT_DIR", help="Output directory (will contain nodes/ + .canvas)")
    p_obs_lc.add_argument("--vault-root", metavar="VAULT_ROOT", help="Obsidian vault root for file path resolution")
    p_obs_lc.add_argument("--intentlinks", choices=["all", "siblings", "none"], default="all",
                          help="Which intentlinks to draw: all (default), siblings only, or none")


def _warn(msg: str) -> None:
    print(f"ig-tool: warning: {msg}", file=sys.stderr)


def _warn_if_no_snapshot(vault_dir: Path) -> None:
    """Warn when a vault lacks the .ig-sync.yaml baseline (pre-snapshot export).

    Without a baseline there is no whole-node conflict detection, and link
    identity may be unreliable — links whose edges.yaml predates the uid fix
    can appear as spurious deletions in diff/merge.
    """
    if load_snapshot(vault_dir) is None:
        _warn(
            f"vault has no {SNAPSHOT_FILENAME} baseline (pre-snapshot export). "
            "No whole-node conflict detection; link changes may be false positives. "
            "Re-export to establish a baseline."
        )


# ================================================================== #
#  obsidian                                                            #
# ================================================================== #


def _obsidian_export(args: argparse.Namespace) -> None:
    """Export IntentGraph to Obsidian vault."""
    # 1. Load graph
    graph = _load_graph(args.graph)

    # 2. Validate output dir
    output_dir = Path(args.output)
    if output_dir.exists() and not args.force:
        _die(f"output directory exists: {args.output}. Use --force to overwrite.")

    # 3. Export
    layout_engine = getattr(args, "layout", "grid")
    radial_config = None
    if layout_engine == "radial":
        from intentgraph.obsidian import RadialConfig
        radial_config = RadialConfig(
            ring_gap=getattr(args, "radial_ring_gap", 900),
            total_sweep_deg=getattr(args, "radial_sweep", 180.0),
        )
    try:
        plugin_report = export_to_obsidian(
            graph,
            output_dir,
            vault_root=args.vault_root,
            include_intentlinks=args.intentlinks or "all",
            include_ft_canvases=not getattr(args, "no_ft_canvases", False),
            write_snapshot=True,
            graph_id=getattr(args, "graph_id", None),
            graph_file=args.graph,
            layout_engine=layout_engine,
            radial_config=radial_config,
            nav_links=getattr(args, "nav_links", "minimal"),
            fit_height=getattr(args, "fit_height", False),
            install_plugins=not getattr(args, "no_install_plugins", False),
        )
    except Exception as e:
        _die(f"export failed: {e}")

    # 3b. Layout-storing engines mutate the graph (obsidian_layout computed
    #     baselines + any pins detected from the existing vault's canvases).
    #     Save it back so the canonical IG carries the layout — pins must
    #     survive re-export, merge, and export into a brand-new vault.
    graph_updated = False
    if layout_engine in ("radial", "portal"):
        try:
            save_graph(graph, args.graph)
            graph_updated = True
        except Exception as e:
            _die(f"export succeeded but saving layout back to graph failed: {e}")

    # 4. Count created files
    node_count = len(list((output_dir / "nodes").glob("*.md")))
    canvas_count = len(list((output_dir / "viz").glob("*.canvas")))

    # 5. Generate report
    report = {
        "vault_dir": str(output_dir),
        "nodes_exported": node_count,
        "canvases_created": canvas_count,
        "edges_file": str(output_dir / "edges.yaml"),
    }
    if graph_updated:
        report["graph_updated"] = str(args.graph)
    if plugin_report.installed:
        report["plugins_installed"] = plugin_report.installed
    if plugin_report.already_current:
        report["plugins_already_current"] = plugin_report.already_current
    if plugin_report.missing_from_cache:
        report["plugins_missing"] = plugin_report.missing_from_cache
    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # 6. Write output & summary
    size = _write_output(content, None, emit=False)  # Don't write or print, just compute size

    # A missing plugin does not invalidate the vault (markdown/edges/canvases are
    # all correct) — it degrades portal RENDERING, silently, in Obsidian. Warn
    # loudly rather than failing, and say exactly how to fix it.
    hint = plugin_report.hint()
    if hint:
        _summary("warning", "obsidian export", str(output_dir), size,
                 nodes=node_count, canvases=canvas_count, note=hint)
    else:
        _summary("ok", "obsidian export", str(output_dir), size,
                 nodes=node_count, canvases=canvas_count)


def _obsidian_import(args: argparse.Namespace) -> None:
    """Import Obsidian vault to IntentGraph."""
    # 1. Validate vault dir exists
    vault_dir = Path(args.vault_dir)
    if not vault_dir.exists():
        _die(f"vault directory not found: {args.vault_dir}")

    # 2. Import
    try:
        graph = import_from_obsidian(vault_dir)
    except Exception as e:
        _die(f"import failed: {e}")

    # 3. Save to output
    if not args.output:
        _die("obsidian import requires -o OUTPUT_GRAPH")

    save_graph(graph, args.output)

    # 4. Generate report
    report = {
        "vault_dir": str(vault_dir),
        "nodes_imported": graph.node_count(),
        "links_imported": graph.link_count(),
        "saved_to": args.output,
    }
    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # 5. Write output & summary
    size = {"words": 0, "lines": 0, "chars": 0}  # Summary refers to the graph file
    _summary("ok", "obsidian import", args.output, size,
             nodes=graph.node_count(), links=graph.link_count())


def _obsidian_diff(args: argparse.Namespace) -> None:
    """Compare Obsidian vault against reference graph."""
    # 1. Load reference graph
    reference = _load_graph(args.graph)

    # 2. Validate vault dir
    vault_dir = Path(args.vault_dir)
    if not vault_dir.exists():
        _die(f"vault directory not found: {args.vault_dir}")
    _warn_if_no_snapshot(vault_dir)

    # 3. Run diff
    try:
        diff_result = diff_obsidian_vs_graph(vault_dir, reference)
    except Exception as e:
        _die(f"diff failed: {e}")

    # 4. Generate report
    report = {
        "vault_dir": str(vault_dir),
        "reference_graph": args.graph,
        "has_changes": diff_result.has_changes,
        "summary": diff_result.summary,
        "nodes_added": len(diff_result.nodes_added),
        "nodes_deleted": len(diff_result.nodes_deleted),
        "nodes_modified": len(diff_result.nodes_modified),
        "links_added": len(diff_result.links_added),
        "links_deleted": len(diff_result.links_deleted),
        "links_modified": len(diff_result.links_modified),
    }

    # Include details if changes detected. By default each changed field carries
    # its old -> new values (a diff without values is not a diff). --names-only
    # reduces the payload to bare field names.
    names_only = getattr(args, "names_only", False)

    def _field_entry(f):
        if names_only:
            return f.field
        return {"field": f.field, "old": f.old, "new": f.new}

    if diff_result.has_changes:
        report["details"] = {
            "nodes_added_uids": diff_result.nodes_added,
            "nodes_deleted_uids": diff_result.nodes_deleted,
            "nodes_modified_details": [
                {"uid": nd.uid, "changed_fields": [_field_entry(f) for f in nd.changed_fields]}
                for nd in diff_result.nodes_modified
            ],
            "links_added_details": [
                {"src": lc.src, "dst": lc.dst, "intent": lc.intent}
                for lc in diff_result.links_added
            ],
            "links_modified_details": [
                {"uid": lm.uid, "src": lm.src, "dst": lm.dst,
                 "changed_fields": [_field_entry(f) for f in lm.changed_fields]}
                for lm in diff_result.links_modified
            ],
            "links_deleted_details": [
                {"src": lc.src, "dst": lc.dst}
                for lc in diff_result.links_deleted
            ],
        }

    # 5. Serialize
    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # 6. Write output & summary
    size = _write_output(content, args.output)
    status = "ok" if not diff_result.has_changes else "warning"
    _summary(status, "obsidian diff", args.output, size,
             has_changes=diff_result.has_changes,
             total_changes=(report["nodes_added"] + report["nodes_deleted"] +
                           report["nodes_modified"] + report["links_added"] +
                           report["links_deleted"] + report["links_modified"]))


def _resolve_view(graph, nodes_arg: str | None, action: str) -> View:
    """Build the working View from a --nodes UID list (shared by canvas/pins)."""
    if not nodes_arg:
        _die(f"obsidian {action} requires --nodes UID,UID,...")
    node_uids = {u.strip() for u in nodes_arg.split(",") if u.strip()}
    try:
        return View.from_node_set(graph, "cli-view", node_uids)
    except Exception as e:
        _die(f"invalid --nodes selection: {e}")


def _obsidian_canvas(args: argparse.Namespace) -> None:
    """Export a working view to an Obsidian canvas."""
    # 1. Load graph
    graph = _load_graph(args.graph)

    # 2. Build the view from --nodes
    view = _resolve_view(graph, args.nodes, "export-canvas")

    # 3. Validate output path
    if not args.output:
        _die("obsidian export-canvas requires -o OUTPUT_CANVAS_FILE")

    output_path = Path(args.output)
    if not output_path.suffix == ".canvas":
        _die("output path must end with .canvas extension")

    # 4. Export canvas
    try:
        export_view_canvas(view, output_path)
    except Exception as e:
        _die(f"canvas export failed: {e}")

    # 5. Write output & summary
    size = {"words": 0, "lines": 0, "chars": 0}
    _summary("ok", "obsidian export-canvas", str(output_path), size,
             view_nodes=len(view.node_uids))


def _obsidian_detect_pins(args: argparse.Namespace) -> None:
    """Detect user-moved nodes in canvas."""
    # 1. Load graph
    graph = _load_graph(args.graph)

    # 2. Build the view from --nodes
    view = _resolve_view(graph, args.nodes, "detect-pins")

    # 3. Validate canvas input
    if not args.canvas:
        _die("obsidian detect-pins requires --canvas CANVAS_FILE")

    canvas_path = Path(args.canvas)
    if not canvas_path.exists():
        _die(f"canvas file not found: {args.canvas}")

    # 4. Detect pinned positions
    try:
        tolerance = args.tolerance or 5
        pinned = detect_pinned_positions(view, canvas_path, tolerance=tolerance)
    except Exception as e:
        _die(f"detect-pins failed: {e}")

    # 5. Generate report
    report = {
        "view_nodes": sorted(view.node_uids),
        "canvas_file": str(canvas_path),
        "tolerance": tolerance,
        "pinned_nodes": len(pinned),
        "pinned_uids": list(pinned.keys()),
    }

    # Include pinned positions if any
    if pinned:
        report["positions"] = {
            uid: {"x": nl.x, "y": nl.y, "width": nl.width, "height": nl.height}
            for uid, nl in pinned.items()
        }

    # 6. Serialize
    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # 7. Write output & summary
    size = _write_output(content, args.output)
    _summary("ok", "obsidian detect-pins", args.output, size,
             pinned_nodes=len(pinned))


def _obsidian_full_tree(args: argparse.Namespace) -> None:
    """Export FT canvas: ROOT + all L1; optional focus L1 expands only that subtree."""
    graph = _load_graph(args.graph)

    output_path = Path(args.output)
    if not output_path.suffix == ".canvas":
        output_path = output_path.with_suffix(".canvas")

    canvas_json = generate_full_tree_canvas(
        graph,
        nodes_prefix=args.nodes_prefix or "nodes",
        canvas_width=args.width or 2400,
        include_intentlinks=args.intentlinks or "all",
        focus_l1_uid=args.focus_l1,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(canvas_json, encoding="utf-8")

    node_count = sum(1 for _ in graph.iter_nodes())
    size = {"words": 0, "lines": 0, "chars": len(canvas_json)}
    _summary("ok", "obsidian export-tree", str(output_path), size,
             nodes=node_count)


def _obsidian_lens_canvas(args: argparse.Namespace) -> None:
    """Export lens as Obsidian canvas with LOD-aware rendering."""
    from intentgraph.serial.lens_file import load_lens

    lens_path = Path(args.lens)
    if not lens_path.exists():
        _die(f"lens file not found: {args.lens}")
    try:
        lens = load_lens(lens_path)
    except Exception as e:
        _die(f"failed to load lens: {e}")

    output_dir = Path(args.output)
    try:
        export_lens_canvas(
            lens,
            output_dir,
            vault_root=args.vault_root,
            include_intentlinks=args.intentlinks or "all",
        )
    except Exception as e:
        _die(f"lens canvas export failed: {e}")

    node_count = len(lens.nodes)
    canvas_path = output_dir / f"LENS_{lens.meta.name}.canvas"
    size = {"words": 0, "lines": 0, "chars": 0}
    _summary("ok", "obsidian lens-canvas", str(canvas_path), size,
             nodes=node_count, lens_name=lens.meta.name)


def _obsidian_merge(args: argparse.Namespace) -> None:
    """Merge Obsidian vault edits back into canonical IntentGraph."""
    # 1. Validate vault dir exists
    vault_dir = Path(args.vault_dir)
    if not vault_dir.exists():
        _die(f"vault directory not found: {args.vault_dir}")
    _warn_if_no_snapshot(vault_dir)

    # 2. Load or resolve canonical graph
    if args.graph:
        # Explicit graph provided
        graph = _load_graph(args.graph)
        graph_path = args.graph
    else:
        # Try to resolve from vault snapshot
        snapshot = load_snapshot(vault_dir)
        if snapshot and snapshot.get("graph_file"):
            graph_path = snapshot["graph_file"]
            try:
                graph = _load_graph(graph_path)
            except Exception as e:
                _die(f"could not load graph from snapshot: {graph_path}: {e}")
        else:
            _die("no graph provided (-g) and vault snapshot missing or has no graph_file. "
                 "Please pass -g/--graph to specify the canonical graph.")

    # 3. Load snapshot if available
    snapshot = load_snapshot(vault_dir)

    # 4. Check graph hash against snapshot (unless --force or --dry-run)
    if snapshot and not args.force and not args.dry_run:
        expected_hash = snapshot.get("graph_hash")
        actual_hash = graph_hash(graph)
        if expected_hash and actual_hash != expected_hash:
            _die(
                f"canonical graph has changed since export "
                f"(snapshot: {expected_hash[:12]}..., current: {actual_hash[:12]}...). "
                f"Re-export first or pass --force to override conflict detection."
            )

    # 5. Run merge
    try:
        merge_report = merge_obsidian_into_graph(
            vault_dir,
            graph,
            snapshot=snapshot,
            on_malformed="skip" if args.skip_malformed else "fail",
        )
    except Exception as e:
        _die(f"merge failed: {e}")

    # 6. Handle errors
    if merge_report.errors:
        error_summary = "\n  ".join(merge_report.errors[:5])
        if len(merge_report.errors) > 5:
            error_summary += f"\n  ... and {len(merge_report.errors) - 5} more"
        _die(f"merge encountered errors:\n  {error_summary}")

    # 7. Dry-run: print report and exit
    if args.dry_run:
        report = {
            "vault_dir": str(vault_dir),
            "dry_run": True,
            "summary": merge_report.summary,
            "applied_nodes": len(merge_report.applied_nodes),
            "applied_links": len(merge_report.applied_links),
            "conflicts": len(merge_report.conflicts),
            "ignored_added": len(merge_report.ignored_added),
            "ignored_deleted": len(merge_report.ignored_deleted),
        }
        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(content)
        return

    # 8. Save merged graph
    output_path = args.output or graph_path
    try:
        _save_graph(graph, output_path, args, channel="obsidian")
    except Exception as e:
        _die(f"failed to save merged graph: {e}")

    # 9. Generate report
    report = {
        "vault_dir": str(vault_dir),
        "saved_to": output_path,
        "summary": merge_report.summary,
        "applied_nodes": len(merge_report.applied_nodes),
        "applied_links": len(merge_report.applied_links),
        "conflicts": len(merge_report.conflicts),
        "ignored_added": len(merge_report.ignored_added),
        "ignored_deleted": len(merge_report.ignored_deleted),
    }
    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # 10. Write output & summary
    size = {"words": 0, "lines": 0, "chars": 0}
    _summary("ok", "obsidian merge", output_path, size,
             applied=len(merge_report.applied_nodes),
             conflicts=len(merge_report.conflicts))


def cmd_obsidian(args: argparse.Namespace) -> None:
    """Handle obsidian subcommand with 8 actions."""
    if args.action == "export":
        _obsidian_export(args)
    elif args.action == "import":
        _obsidian_import(args)
    elif args.action == "diff":
        _obsidian_diff(args)
    elif args.action == "merge":
        _obsidian_merge(args)
    elif args.action == "export-canvas":
        _obsidian_canvas(args)
    elif args.action == "export-tree":
        _obsidian_full_tree(args)
    elif args.action == "detect-pins":
        _obsidian_detect_pins(args)
    elif args.action == "export-lens-canvas":
        _obsidian_lens_canvas(args)
    else:
        _die(f"unknown obsidian action: {args.action}")
