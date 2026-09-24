"""ig-tool ``init`` command: initialize a new IntentGraph.

Moved verbatim from ``cli_impl.py`` (Phase 2: command extraction). Pure move:
no behavior change.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import save_graph

from ig_agents.cli.common import _die, _save_graph, _summary


# ================================================================== #
#  init                                                                #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``init`` subcommand on *sub*."""
    p_init = sub.add_parser(
        "init",
        help="Initialize a new IntentGraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool init -o graph.json --root --root-name 'My System' --root-intent 'Top-level intent'\n"
            "  ig-tool init -o graph.yaml --template three-level --name 'project_x'\n"
            "Notes:\n"
            "  - Without --root or --template, creates an empty graph.\n"
            "  - Templates: 'minimal' (ROOT only), 'three-level' (ROOT + 3 modules).\n"
        ),
    )
    p_init.add_argument("-o", "--output", required=True, help="Output graph file path (JSON or YAML)")
    p_init.add_argument("--name", help="Graph name (stored in meta)")
    p_init.add_argument("--description", help="Graph description (stored in meta)")
    p_init.add_argument("--version", help="Graph version (stored in meta)")
    p_init.add_argument("--root", action="store_true", help="Add a ROOT node")
    p_init.add_argument("--root-name", metavar="NAME", help="Name for ROOT node (default: 'Root')")
    p_init.add_argument("--root-intent", metavar="INTENT", help="Intent for ROOT node (default: 'System root')")
    p_init.add_argument("--template", choices=["minimal", "three-level"],
                        help="Apply a template structure (minimal: ROOT only, three-level: ROOT + 3 modules)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing file")
    p_init.add_argument("-m", "--message", help="One-liner history note for this change (commit-style)")
    p_init.add_argument("--role", help="Agent role for provenance (history who = agent:<role>)")


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a new IntentGraph."""
    # 1. Validate output path
    if not args.output:
        _die("init requires -o OUTPUT_GRAPH")

    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        _die(f"output file exists: {args.output}. Use --force to overwrite.")

    # 2. Build metadata
    meta: dict[str, Any] = {}
    if args.name:
        meta["name"] = args.name
    if args.description:
        meta["description"] = args.description
    if args.version:
        meta["version"] = args.version

    # 3. Create graph
    graph = IntentGraph(meta=meta if meta else None)

    # 4. Add root node if requested (or if using a template)
    if args.root or args.template:
        root_name = args.root_name or "Root"
        root_intent = args.root_intent or "System root"
        graph.add_node("ROOT", root_name, root_intent)

    # 5. Apply template if specified
    if args.template:
        if args.template == "minimal":
            # Already done (just ROOT)
            pass
        elif args.template == "three-level":
            # Add sample 3-level structure
            graph.add_node_under("A", "Module A", "First major module", parent_uid="ROOT")
            graph.add_node_under("B", "Module B", "Second major module", parent_uid="ROOT")
            graph.add_node_under("C", "Module C", "Third major module", parent_uid="ROOT")
            graph.add_node_under("A.1", "Component A.1", "First component of A", parent_uid="A")
            graph.add_node_under("A.2", "Component A.2", "Second component of A", parent_uid="A")
            graph.add_link("A", "B", "A flows to B")
        else:
            _die(f"unknown template: {args.template}")

    # 6. Save graph
    _save_graph(graph, str(output_path), args)
    output_ext = output_path.suffix.lower()
    output_format = "yaml" if output_ext in (".yaml", ".yml") else "json"

    # 7. Generate report
    report = {
        "output": str(output_path),
        "format": output_format,
        "nodes": graph.node_count(),
        "links": graph.link_count(),
    }
    if meta:
        report["meta"] = meta
    if args.template:
        report["template"] = args.template

    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # 8. Write output & summary
    size = {"words": 0, "lines": 0, "chars": 0}
    _summary("ok", "init", str(output_path), size,
             nodes=graph.node_count(),
             links=graph.link_count(),
             format=output_format)
