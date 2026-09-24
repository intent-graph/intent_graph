"""ig-tool ``tree`` command: ASCII tree visualization of the IntentGraph.

Moved verbatim from ``cli_impl.py`` (Phase 2: command extraction). Pure move:
no behavior change.
"""

from __future__ import annotations

import argparse
from typing import Any

from intentgraph.serial.ascii_tree import render_ascii_tree, render_ascii_tree_boxed

from ig_agents.cli.common import _write_output, _summary, _load_graph


# ================================================================== #
#  tree                                                                #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``tree`` subcommand on *sub*."""
    p_tree = sub.add_parser(
        "tree",
        help="Render ASCII tree visualization of the IntentGraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool tree -g graph.json\n"
            "  ig-tool tree -g graph.json --root PARSER --show-intent --style boxed\n"
            "  ig-tool tree -g graph.json --width 100 -o tree.txt\n"
            "Notes:\n"
            "  - --root defaults to auto-detected root (first node with no parent).\n"
            "  - --style boxed renders with Unicode box drawing; default is plain text.\n"
        ),
    )
    p_tree.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_tree.add_argument("-o", "--output", help="Write tree to this path (default: stdout)")
    p_tree.add_argument("--root", metavar="UID", help="UID of root node to start from (default: auto-detect)")
    p_tree.add_argument("--show-intent", action="store_true", help="Include intent descriptions below each node")
    p_tree.add_argument("--style", choices=["simple", "boxed"], default="simple",
                        help="Rendering style (simple: text tree, boxed: box-based)")
    p_tree.add_argument("--width", type=int, metavar="N", help="Max width for text wrapping (default: 80 for simple, 120 for boxed)")
    p_tree.add_argument("--indent", metavar="STR", help="Indentation string (default: '    ')")


def cmd_tree(args: argparse.Namespace) -> None:
    """Render ASCII tree visualization of the IntentGraph."""
    # 1. Load graph
    graph = _load_graph(args.graph)

    # 2. Render tree
    if args.style == "boxed":
        content = render_ascii_tree_boxed(
            graph,
            root_uid=args.root,
            max_width=args.width or 120
        )
    else:
        content = render_ascii_tree(
            graph,
            root_uid=args.root,
            show_intent=args.show_intent,
            max_width=args.width or 80,
            indent=args.indent or "    "
        )

    # 3. Write output
    size = _write_output(content, args.output)

    # 4. Generate summary
    _summary("ok", "tree", args.output, size,
             nodes=graph.node_count(),
             root=args.root or "(auto-detected)")
