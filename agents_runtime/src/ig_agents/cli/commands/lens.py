"""``ig-tool lens`` — file-based agent-I/O lens operations (15 verbs).

Moved verbatim from ``cli_lens_commands.py`` (Phase 4: lens extraction).
This is the legacy/agent-I/O Lens: a standalone lens *file* (``-l``) built from
a graph (``-g``) and shaped by LOD per node. For graph-embedded named lenses
(persisted inside the graph file), see ``cli/commands/graph_lens.py``
(``ig-tool graph lens <verb>``).

Verbs: build, show, tree, info, focus, promote, demote, set-lod, prune,
expand, set-budget, list-pruned, diff, apply, discard.

Conservative move: ``cmd_lens`` keeps its original shape (one function,
dispatching on ``args.action`` via a chain of ``if``/``return``) rather than
being split into the params/run/format shape — the function is deeply
entangled with ``argparse.Namespace`` across 15 verbs, and a clean split was
judged higher-risk than value for a zero-behavior-change move. Noted as a
follow-up opportunity, not done here.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from intentgraph.models.lens import LOD
from intentgraph.serial.lens_file import load_lens, save_lens, lens_to_agent_text
from intentgraph.serial.json_yaml import save_graph
from intentgraph.ops.lens_ops import (
    build_lens,
    promote,
    demote,
    focus_on,
    prune_subtree,
    expand_subtree,
    set_budget,
    compute_diff,
    apply_diff,
    discard_changes,
)

from ig_agents.cli.common import _die, _load_graph, _save_graph, _write_output, _summary


def _load_lens_file(path: str) -> Any:
    """Load a lens file, dying on error."""
    p = Path(path)
    if not p.exists():
        _die(f"lens file not found: {path}")
    try:
        return load_lens(p)
    except Exception as e:
        _die(f"failed to load lens: {e}")


def cmd_lens(args: argparse.Namespace) -> None:
    """Handle lens subcommand with all actions."""

    # ---- build ----
    if args.action == "build":
        if not args.graph:
            _die("lens build requires -g GRAPH")
        if not args.target:
            _die("lens build requires -t TARGET_UID")
        if not args.output:
            _die("lens build requires -o OUTPUT_LENS")

        graph = _load_graph(args.graph)
        budget = args.budget or 30
        name = args.name or "working-lens"
        scope_root = args.scope_root

        try:
            lens = build_lens(
                graph,
                target_uid=args.target,
                budget=budget,
                source_graph_path=args.graph,
                name=name,
                scope_root=scope_root,
            )
        except Exception as e:
            _die(f"build failed: {e}")

        save_lens(lens, args.output)

        lod_stats = lens.lod_stats()
        _summary("ok", "lens build", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 nodes=lens.node_count(),
                 target=args.target,
                 budget=budget,
                 lod_stats=lod_stats,
                 pruned=len(lens.pruned_subtrees))
        return

    # ---- show (legacy agent-I/O mode only) ----
    # Internal-lens mode show has moved to: graph lens show
    if args.action == "show":
        if not args.lens_file:
            _die("lens show requires -l LENS_FILE (for internal lens show, use: graph lens show)")

        lens = _load_lens_file(args.lens_file)
        text = lens_to_agent_text(lens)
        size = _write_output(text, args.output)

        _summary("ok", "lens show", args.output, size,
                 nodes=lens.node_count(),
                 target=lens.meta.target_uid)
        return

    # ---- tree ----
    if args.action == "tree":
        if not args.lens_file:
            _die("lens tree requires -l LENS_FILE")

        lens = _load_lens_file(args.lens_file)
        lines = []

        # Build tree representation with LOD indicators
        def _render_tree(uid: str, prefix: str = "", is_last: bool = True) -> None:
            node = lens.nodes[uid]
            lod = lens.get_lod(uid)
            lod_indicator = {
                LOD.full: "[FULL]",
                LOD.lean: "[lean]",
                LOD.skeleton: "[skel]",
            }[lod]

            marker = "└─ " if is_last else "├─ "
            pruned_note = f" (pruned: {lens.node_metadata[uid].pruned_children})" \
                if lens.node_metadata[uid].pruned_children > 0 else ""

            lines.append(f"{prefix}{marker}{lod_indicator} {uid}: {node.name}{pruned_note}")

            # Children
            children = [c for c in node.children_uids if c in lens.nodes]
            extension = "   " if is_last else "│  "
            for i, child_uid in enumerate(children):
                _render_tree(child_uid, prefix + extension, i == len(children) - 1)

        # Render from root(s)
        roots = [uid for uid, node in lens.nodes.items() if node.parent_uid is None]
        for root_uid in roots:
            _render_tree(root_uid)

        content = "\n".join(lines)
        size = _write_output(content, args.output)

        _summary("ok", "lens tree", args.output, size,
                 nodes=lens.node_count())
        return

    # ---- info ----
    if args.action == "info":
        if not args.lens_file:
            _die("lens info requires -l LENS_FILE")

        lens = _load_lens_file(args.lens_file)
        lod_stats = lens.lod_stats()

        report = {
            "name": lens.meta.name,
            "target": lens.meta.target_uid,
            "budget": lens.meta.budget,
            "source_graph": lens.meta.source_graph,
            "scope_root": lens.meta.scope_root,
            "node_count": lens.node_count(),
            "lod_stats": lod_stats,
            "visible_links": lens.visible_link_count(),
            "pruned_subtrees": len(lens.pruned_subtrees),
            "dirty": lens.dirty,
        }

        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, args.output)

        _summary("ok", "lens info", args.output, size,
                 nodes=lens.node_count(),
                 target=lens.meta.target_uid,
                 dirty=lens.dirty)
        return

    # ---- focus ----
    if args.action == "focus":
        if not args.lens_file:
            _die("lens focus requires -l LENS_FILE")
        if not args.graph:
            _die("lens focus requires -g GRAPH")
        if not args.uid:
            _die("lens focus requires --uid TARGET_UID")
        if not args.output:
            _die("lens focus requires -o OUTPUT_LENS")

        lens = _load_lens_file(args.lens_file)
        graph = _load_graph(args.graph)

        try:
            focus_on(lens, graph, args.uid)
        except Exception as e:
            _die(f"focus failed: {e}")

        save_lens(lens, args.output)

        _summary("ok", "lens focus", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 new_target=args.uid,
                 nodes=lens.node_count())
        return

    # ---- promote ----
    if args.action == "promote":
        if not args.lens_file:
            _die("lens promote requires -l LENS_FILE")
        if not args.uid:
            _die("lens promote requires --uid NODE_UID")
        if not args.output:
            _die("lens promote requires -o OUTPUT_LENS")

        lens = _load_lens_file(args.lens_file)

        old_lod = lens.get_lod(args.uid)
        try:
            promote(lens, args.uid)
        except Exception as e:
            _die(f"promote failed: {e}")

        new_lod = lens.get_lod(args.uid)
        save_lens(lens, args.output)

        _summary("ok", "lens promote", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 uid=args.uid,
                 old_lod=old_lod.value,
                 new_lod=new_lod.value)
        return

    # ---- demote ----
    if args.action == "demote":
        if not args.lens_file:
            _die("lens demote requires -l LENS_FILE")
        if not args.uid:
            _die("lens demote requires --uid NODE_UID")
        if not args.output:
            _die("lens demote requires -o OUTPUT_LENS")

        lens = _load_lens_file(args.lens_file)

        old_lod = lens.get_lod(args.uid)
        try:
            demote(lens, args.uid)
        except Exception as e:
            _die(f"demote failed: {e}")

        new_lod = lens.get_lod(args.uid)
        save_lens(lens, args.output)

        _summary("ok", "lens demote", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 uid=args.uid,
                 old_lod=old_lod.value,
                 new_lod=new_lod.value)
        return

    # ---- set-lod ----
    # ---- set-lod (legacy agent-I/O mode only) ----
    # Internal-lens mode set-lod has moved to: graph lens set-lod
    if args.action == "set-lod":
        if not args.lens_file:
            _die("lens set-lod requires -l LENS_FILE (for internal lens set-lod, use: graph lens set-lod)")
        if not args.uid:
            _die("lens set-lod requires --uid NODE_UID")
        if not args.lod:
            _die("lens set-lod requires --lod (skeleton|lean|full)")
        if not args.output:
            _die("lens set-lod requires -o OUTPUT_LENS")

        lens = _load_lens_file(args.lens_file)

        old_lod = lens.get_lod(args.uid)
        try:
            new_lod = LOD(args.lod)
            lens.set_lod(args.uid, new_lod)
        except Exception as e:
            _die(f"set-lod failed: {e}")

        save_lens(lens, args.output)

        _summary("ok", "lens set-lod", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 uid=args.uid,
                 old_lod=old_lod.value,
                 new_lod=args.lod)
        return

    # ---- prune ----
    if args.action == "prune":
        if not args.lens_file:
            _die("lens prune requires -l LENS_FILE")
        if not args.uid:
            _die("lens prune requires --uid SUBTREE_ROOT_UID")
        if not args.output:
            _die("lens prune requires -o OUTPUT_LENS")

        lens = _load_lens_file(args.lens_file)
        old_count = lens.node_count()

        try:
            prune_subtree(lens, args.uid)
        except Exception as e:
            _die(f"prune failed: {e}")

        new_count = lens.node_count()
        save_lens(lens, args.output)

        _summary("ok", "lens prune", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 pruned_uid=args.uid,
                 nodes_removed=old_count - new_count,
                 nodes_remaining=new_count)
        return

    # ---- expand ----
    if args.action == "expand":
        if not args.lens_file:
            _die("lens expand requires -l LENS_FILE")
        if not args.graph:
            _die("lens expand requires -g GRAPH")
        if not args.uid:
            _die("lens expand requires --uid SUBTREE_ROOT_UID")
        if not args.output:
            _die("lens expand requires -o OUTPUT_LENS")

        lens = _load_lens_file(args.lens_file)
        graph = _load_graph(args.graph)
        old_count = lens.node_count()

        depth = args.depth if hasattr(args, 'depth') else None

        try:
            expand_subtree(lens, graph, args.uid, depth=depth)
        except Exception as e:
            _die(f"expand failed: {e}")

        new_count = lens.node_count()
        save_lens(lens, args.output)

        _summary("ok", "lens expand", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 expanded_uid=args.uid,
                 nodes_added=new_count - old_count,
                 nodes_total=new_count)
        return

    # ---- set-budget ----
    if args.action == "set-budget":
        if not args.lens_file:
            _die("lens set-budget requires -l LENS_FILE")
        if not args.graph:
            _die("lens set-budget requires -g GRAPH")
        if not args.budget:
            _die("lens set-budget requires -b BUDGET")
        if not args.output:
            _die("lens set-budget requires -o OUTPUT_LENS")

        lens = _load_lens_file(args.lens_file)
        graph = _load_graph(args.graph)
        old_budget = lens.meta.budget
        old_count = lens.node_count()

        try:
            set_budget(lens, graph, args.budget)
        except Exception as e:
            _die(f"set-budget failed: {e}")

        new_count = lens.node_count()
        save_lens(lens, args.output)

        _summary("ok", "lens set-budget", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 old_budget=old_budget,
                 new_budget=args.budget,
                 old_count=old_count,
                 new_count=new_count)
        return

    # ---- list-pruned ----
    if args.action == "list-pruned":
        if not args.lens_file:
            _die("lens list-pruned requires -l LENS_FILE")

        lens = _load_lens_file(args.lens_file)

        report = {
            "pruned_subtrees": lens.pruned_subtrees,
            "count": len(lens.pruned_subtrees),
        }

        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, args.output)

        _summary("ok", "lens list-pruned", args.output, size,
                 pruned_count=len(lens.pruned_subtrees))
        return

    # ---- diff ----
    if args.action == "diff":
        if not args.lens_file:
            _die("lens diff requires -l LENS_FILE")

        lens = _load_lens_file(args.lens_file)

        try:
            diff = compute_diff(lens)
        except Exception as e:
            _die(f"diff failed: {e}")

        # Count total changes
        total_changes = sum(len(v) for v in diff.values())

        report = {
            "has_changes": total_changes > 0,
            "summary": {
                "nodes_created": len(diff["nodes_created"]),
                "nodes_modified": len(diff["nodes_modified"]),
                "nodes_deleted": len(diff["nodes_deleted"]),
                "links_created": len(diff["links_created"]),
                "links_modified": len(diff["links_modified"]),
                "links_deleted": len(diff["links_deleted"]),
                "treearcs_modified": len(diff["treearcs_modified"]),
            },
            "details": diff,
        }

        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, args.output)

        status = "ok" if total_changes == 0 else "warning"
        _summary(status, "lens diff", args.output, size,
                 has_changes=total_changes > 0,
                 total_changes=total_changes)
        return

    # ---- apply ----
    if args.action == "apply":
        if not args.lens_file:
            _die("lens apply requires -l LENS_FILE")
        if not args.graph:
            _die("lens apply requires -g GRAPH")
        if not args.output:
            _die("lens apply requires -o UPDATED_GRAPH")

        lens = _load_lens_file(args.lens_file)
        graph = _load_graph(args.graph)

        try:
            log = apply_diff(lens, graph)
        except Exception as e:
            _die(f"apply failed: {e}")

        _save_graph(graph, args.output, args)

        report = {
            "applied": len(log),
            "log": log,
            "saved_to": args.output,
        }
        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # Write apply report
        report_path = str(Path(args.output).with_suffix(".apply_report.yaml"))
        _write_output(content, report_path)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "lens apply", args.output, size,
                 changes_applied=len(log),
                 report=report_path)
        return

    # ---- discard ----
    if args.action == "discard":
        if not args.lens_file:
            _die("lens discard requires -l LENS_FILE")
        if not args.output:
            _die("lens discard requires -o OUTPUT_LENS")

        lens = _load_lens_file(args.lens_file)

        try:
            discard_changes(lens)
        except Exception as e:
            _die(f"discard failed: {e}")

        save_lens(lens, args.output)

        _summary("ok", "lens discard", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 nodes=lens.node_count())
        return

    _die(f"unknown lens action: {args.action}")


def add_parser(sub: Any) -> None:
    """Register the ``lens`` subcommand (file-based agent-I/O lens, 15 verbs)."""
    p_lens = sub.add_parser(
        "lens",
        help=(
            "Agent I/O lens operations (file-based, -l): "
            "build, show, tree, info, focus, promote, demote, "
            "set-lod, prune, expand, set-budget, list-pruned, diff, apply, discard. "
            "For internal graph-embedded lens management, use: graph lens <verb>"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Lifecycle: build → show/tree → [focus/promote/demote/prune/expand] → diff → apply.\n"
            "Examples:\n"
            "  ig-tool lens build  -g graph.json -t TARGET -b 30 -o lens.yaml\n"
            "  ig-tool lens show   -l lens.yaml -o agent_view.yaml\n"
            "  ig-tool lens tree   -l lens.yaml\n"
            "  ig-tool lens focus  -l lens.yaml -g graph.json --uid NEW_TARGET -o lens.yaml\n"
            "  ig-tool lens expand -l lens.yaml -g graph.json --uid X --depth 1 -o lens.yaml\n"
            "  ig-tool lens diff   -l lens.yaml -o diff.yaml\n"
            "  ig-tool lens apply  -l lens.yaml -g graph.json -o updated.json\n"
            "Notes:\n"
            "  - This is FILE-based (legacy) lens. For graph-embedded named lenses, use: graph lens.\n"
            "  - -l is required for all actions except 'build'. -g is also needed for build/focus/expand/set-budget/apply.\n"
            "  - Budget -b is in thousands (default 30 = ~30k tokens).\n"
        ),
    )
    p_lens.add_argument("action", choices=[
        # Legacy agent-I/O commands (15 verbs)
        "build", "show", "tree", "info", "focus", "promote", "demote",
        "set-lod", "prune", "expand", "set-budget", "list-pruned", "diff", "apply", "discard",
    ])
    p_lens.add_argument("-g", "--graph", help="Path to IG file (JSON or YAML)")
    # -l: legacy agent-I/O Lens file path
    p_lens.add_argument("-l", dest="lens_file",
                        help="Path to agent-I/O Lens YAML file")
    p_lens.add_argument("-t", "--target", help="Target UID (for build, focus)")
    p_lens.add_argument("-b", "--budget", type=int, help="Budget (default: 30)")
    p_lens.add_argument("--name", help="Lens name (for build)")
    p_lens.add_argument("--scope-root", help="Scope root UID (for build)")
    p_lens.add_argument("--uid", help="Node UID")
    p_lens.add_argument("--lod", choices=["skeleton", "lean", "full"], help="LOD level")
    p_lens.add_argument("--depth", type=int, help="Depth (for expand)")
    p_lens.add_argument("-o", "--output", help="Output path")
    p_lens.add_argument("-m", "--message", help="One-liner history note for this change (commit-style)")
    p_lens.add_argument("--role", help="Agent role for provenance (history who = agent:<role>)")
