"""ig-tool ``convert`` command: convert graph between JSON and YAML formats.

Moved verbatim from ``cli_impl.py`` (Phase 2: command extraction). Pure move:
no behavior change.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from intentgraph.serial.json_yaml import (
    graph_to_json,
    graph_to_yaml,
    load_json,
    load_yaml,
)

from ig_agents.cli.common import _die, _summary


# ================================================================== #
#  convert                                                             #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``convert`` subcommand on *sub*."""
    p_conv = sub.add_parser(
        "convert",
        help="Convert graph between JSON and YAML formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool convert -i graph.yaml -o graph.json\n"
            "  ig-tool convert -i graph.json -o graph.yaml\n"
            "  ig-tool convert -i graph.json -f yaml          # to stdout\n"
            "Notes:\n"
            "  - Format inferred from output extension (.json or .yaml/.yml), or use -f.\n"
            "  - Most ig-tool commands accept both formats; conversion is rarely needed.\n"
        ),
    )
    p_conv.add_argument("-i", "--input", required=True, help="Input graph file (JSON or YAML)")
    p_conv.add_argument("-o", "--output", help="Output file path (format inferred from extension, or use --format)")
    p_conv.add_argument("-f", "--format", choices=["json", "yaml"], help="Output format (overrides extension)")


def cmd_convert(args: argparse.Namespace) -> None:
    """Convert graph between JSON and YAML formats."""
    # 1. Detect input format
    input_path = Path(args.input)
    if not input_path.exists():
        _die(f"input file not found: {args.input}")

    input_ext = input_path.suffix.lower()
    if input_ext == ".json":
        graph = load_json(input_path)
        input_format = "json"
    elif input_ext in (".yaml", ".yml"):
        graph = load_yaml(input_path)
        input_format = "yaml"
    else:
        _die(f"unsupported input format: {input_ext} (expected .json, .yaml, or .yml)")

    # 2. Determine output format
    if args.format:
        output_format = args.format
    elif args.output:
        output_ext = Path(args.output).suffix.lower()
        if output_ext == ".json":
            output_format = "json"
        elif output_ext in (".yaml", ".yml"):
            output_format = "yaml"
        else:
            _die(f"cannot infer output format from extension: {output_ext}")
    else:
        # Default: if input is JSON, output YAML; if input is YAML, output JSON
        output_format = "yaml" if input_format == "json" else "json"

    # 3. Convert
    if output_format == "json":
        content = graph_to_json(graph, indent=2)
    else:
        content = graph_to_yaml(graph)

    # 4. Write output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(content, encoding="utf-8")
        result_path = str(output_path)
    else:
        # Print to stdout if no -o specified
        print(content)
        result_path = "(stdout)"

    # 5. Generate summary
    size = {"words": len(content.split()), "lines": content.count("\n"), "chars": len(content)}
    _summary("ok", "convert", result_path if args.output else None, size,
             input_format=input_format,
             output_format=output_format,
             nodes=graph.node_count(),
             links=graph.link_count())
