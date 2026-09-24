#!/usr/bin/env python3
"""ig-tool — unified CLI for IntentGraph hard tools.

Installed system-wide via ``uv tool install -e .`` from the intent_graph root.
Agents and the orchestrator invoke it as ``ig-tool <command> [args]``.

Design contract:

  OUTPUT:  Full results → file (-o path). Stdout → compact summary only.
  INPUT:   -g graph, -i additional input, -o output, -t target, -m mode.
  ERRORS:  Non-zero exit code. Messages to stderr. Never raw tracebacks.
  SUMMARY: Always stdout, always ≤5 lines, always machine-parseable YAML.

Thin entry point (parser-wiring decomposition complete): every ``cmd_*`` and
its ``add_parser`` now live in ``cli/commands/<name>.py``; ``cli/registry.py``
assembles ``build_parser()`` and ``DISPATCH`` from each module's
``add_parser``/``cmd_*``. This module only re-exports them plus ``main()`` and
the rename-hint table.
"""

from __future__ import annotations

import sys
import time

from ig_agents import telemetry

from ig_agents.cli.registry import build_parser, DISPATCH  # noqa: F401

# Re-exported for backward-compatible direct imports (tests, any external
# caller that did ``from ig_agents.cli import cmd_apply`` etc. before this
# module existed as a package boundary).
from ig_agents.cli.commands.validate import cmd_validate  # noqa: F401
from ig_agents.cli.commands.query import cmd_query  # noqa: F401
from ig_agents.cli.commands.parse_apply import cmd_parse, cmd_apply  # noqa: F401
from ig_agents.cli.commands.context import cmd_context  # noqa: F401
from ig_agents.cli.commands.workflow import cmd_workflow, cmd_step, cmd_trace  # noqa: F401
from ig_agents.cli.commands.obsidian import cmd_obsidian  # noqa: F401
from ig_agents.cli.commands.convert import cmd_convert  # noqa: F401
from ig_agents.cli.commands.tree import cmd_tree  # noqa: F401
from ig_agents.cli.commands.init import cmd_init  # noqa: F401
from ig_agents.cli.commands.telemetry import cmd_telemetry  # noqa: F401
from ig_agents.cli.commands.lens import cmd_lens  # noqa: F401
from ig_agents.cli.commands.graph_lens import cmd_graph  # noqa: F401
from ig_agents.cli.commands.graph_mutate import cmd_node, cmd_link  # noqa: F401

from ig_agents.cli.common import _die, _load_graph, _write_output, _summary  # noqa: F401


# Rename hints: shown when an old command name is used and argparse rejects it.
_RENAMED = {
    "edit":    "Use 'parse' (was: edit parse) or 'apply' (was: edit apply)",
    "batch":   "Use 'apply --batch <file>' (was: batch -g G -i F)",
    "step":    "Use 'workflow step ...' (was: step ...)",
    "trace":   "Use 'workflow trace ...' (was: trace ...)",
}


def main() -> None:
    parser = build_parser()
    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 2 and len(sys.argv) > 1:
            first_token = sys.argv[1]
            hint = _RENAMED.get(first_token)
            if hint:
                print(f"ig-tool: hint: {hint}", file=sys.stderr)
        raise

    handler = DISPATCH.get(args.command)
    if handler is None:
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Telemetry is on by default; disabled via --no-telemetry, env var,
    # or for the telemetry subcommand itself (don't log inspections).
    log_enabled = (
        not getattr(args, "no_telemetry", False)
        and not telemetry.disabled_via_env()
        and args.command != "telemetry"
    )

    exit_code = 0
    t0 = time.monotonic()
    try:
        handler(args)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
        raise
    except Exception as e:
        exit_code = 1
        _die(f"unexpected error: {e}")
    finally:
        if log_enabled:
            duration_ms = int((time.monotonic() - t0) * 1000)
            telemetry.write_record(
                command=getattr(args, "command", None),
                action=getattr(args, "action", None),
                exit_code=exit_code,
                duration_ms=duration_ms,
                argv=sys.argv[1:],
            )


if __name__ == "__main__":
    main()
