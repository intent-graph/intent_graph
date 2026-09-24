"""ig-tool ``context`` command: assemble full context payload for agent invocation.

The working view is selected on the command line — either an explicit node
set (``--nodes``) or a uniform depth cut (``--depth``).
"""

from __future__ import annotations

import argparse
from typing import Any

from intentgraph.ops.iv_context import IV_CONTEXT_MODE_FULL

from ig_agents.cli.common import _die, _write_output, _summary, _load_graph


# ================================================================== #
#  context                                                             #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``context`` subcommand on *sub*."""
    p_c = sub.add_parser(
        "context",
        help="Assemble full context payload for agent invocation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool context -g graph.json --nodes E,T,L -t E -m lean -o ctx.yaml\n"
            "  ig-tool context -g graph.json --depth 1 --overview --style style.md -o ctx.yaml\n"
            "Notes:\n"
            "  - Select the working view with --nodes UID,UID,... or --depth N (exactly one).\n"
            "  - For new work, prefer 'lens build' which produces a richer agent-I/O artifact.\n"
            "  - Mode 'lean' = target+neighbors full, others lean. Mode 'full' = all nodes full.\n"
        ),
    )
    p_c.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_c.add_argument("--nodes", metavar="UIDS",
                     help="Comma-separated node UIDs forming the working view")
    p_c.add_argument("--depth", type=int, metavar="N",
                     help="Build the working view as a uniform depth cut (0 = root)")
    p_c.add_argument("--name", default="working-view", metavar="NAME",
                     help="Name for the working view (default: working-view)")
    p_c.add_argument("-t", "--target", metavar="UID", help="Target UID for IV-context")
    p_c.add_argument("-m", "--mode", choices=["full", "lean"], help="IV-context mode")
    p_c.add_argument("-b", "--budget", type=int, help="Word budget (default: 4000)")
    p_c.add_argument("-o", "--output", help="Write context payload to this path")
    p_c.add_argument("--overview", action="store_true", help="Include tree/edge overview")
    p_c.add_argument("--style", metavar="PATH", help="Path to style directives markdown")


def cmd_context(args: argparse.Namespace) -> None:
    from ig_agents.context import assemble_agent_context, build_working_view

    graph = _load_graph(args.graph)

    node_uids = None
    if args.nodes:
        node_uids = {u.strip() for u in args.nodes.split(",") if u.strip()}

    try:
        view = build_working_view(
            graph,
            node_uids=node_uids,
            depth=args.depth,
            name=args.name,
        )
    except Exception as e:
        _die(f"cannot build working view: {e}. Pass --nodes UID,UID,... or --depth N.")

    ctx = assemble_agent_context(
        graph, view,
        target_uid=args.target,
        iv_context_mode=args.mode or IV_CONTEXT_MODE_FULL,
        include_overview=args.overview,
        style_path=args.style,
        word_budget=args.budget or 4000,
    )

    parts = [ctx["view_text"]]
    if args.overview and "tree_overview" in ctx:
        parts.append("---\n")
        parts.append(ctx["tree_overview"])
        parts.append("---\n")
        parts.append(ctx["edge_overview"])

    content = "\n".join(parts)
    size = _write_output(content, args.output)

    budget = ctx["budget_check"]
    _summary("ok", "context", args.output, size,
             words=budget["size"]["words"],
             budget=budget["budget"],
             within_budget=budget["within_budget"])
