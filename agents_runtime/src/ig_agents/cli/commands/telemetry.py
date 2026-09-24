"""ig-tool ``telemetry`` command: inspect local CLI usage log.

Moved verbatim from ``cli_impl.py`` (Phase 2: command extraction). Pure move:
no behavior change.
"""

from __future__ import annotations

import argparse
from typing import Any

from ig_agents import telemetry

from ig_agents.cli.common import _die


# ================================================================== #
#  telemetry                                                          #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``telemetry`` subcommand on *sub*."""
    p_tel = sub.add_parser(
        "telemetry",
        help="Inspect local CLI usage log (~/.cache/ig-tool/usage.jsonl)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool telemetry show              # summary table (top commands, failures)\n"
            "  ig-tool telemetry tail -n 50        # last 50 records as JSONL\n"
            "  ig-tool telemetry path              # print log file path\n"
            "Notes:\n"
            "  - Default-on. Disable with --no-telemetry or env IG_TOOL_NO_TELEMETRY=1.\n"
            "  - Local file only; no network calls.\n"
        ),
    )
    p_tel.add_argument(
        "action",
        choices=["show", "tail", "path"],
        help="show: summary; tail: last N records as JSONL; path: print log file path",
    )
    p_tel.add_argument(
        "-n", "--limit",
        type=int,
        default=20,
        help="Number of records (for 'tail'); default: 20",
    )


def cmd_telemetry(args: argparse.Namespace) -> None:
    if args.action == "path":
        telemetry.cmd_telemetry_path()
    elif args.action == "tail":
        telemetry.cmd_telemetry_tail(args.limit)
    elif args.action == "show":
        telemetry.cmd_telemetry_show()
    else:
        _die(f"unknown telemetry action: {args.action}")
