"""ig-tool command registry: assembles ``build_parser()`` and ``DISPATCH``.

Parser-wiring decomposition: every command module owns its own
``add_parser(subparsers)`` and ``cmd_<name>`` handler. This module is the
single place that knows the full command list — it iterates each module's
``add_parser`` to build the parser, and assembles ``DISPATCH`` from each
module's ``cmd_<name>``. Adding a command means adding one module + one entry
in ``_COMMANDS`` below, not editing a central ``build_parser()`` function.
"""

from __future__ import annotations

import argparse

from ig_agents.cli.commands import (
    context,
    convert,
    graph_lens,
    graph_mutate,
    init,
    lens,
    obsidian,
    parse_apply,
    query,
    telemetry,
    tree,
    validate,
    workflow,
)

# Each entry: (add_parser callable, {dispatch_key: handler}).
# lens/graph/node/link register multiple dispatch keys from one module;
# workflow and obsidian register one key each but own nested sub-subparsers.
_COMMANDS: list[tuple] = [
    (validate.add_parser, {"validate": validate.cmd_validate}),
    (query.add_parser, {"query": query.cmd_query}),
    (parse_apply.add_parser, {"parse": parse_apply.cmd_parse, "apply": parse_apply.cmd_apply}),
    (context.add_parser, {"context": context.cmd_context}),
    (workflow.add_parser, {"workflow": workflow.cmd_workflow}),
    (obsidian.add_parser, {"obsidian": obsidian.cmd_obsidian}),
    (convert.add_parser, {"convert": convert.cmd_convert}),
    (tree.add_parser, {"tree": tree.cmd_tree}),
    (init.add_parser, {"init": init.cmd_init}),
    (telemetry.add_parser, {"telemetry": telemetry.cmd_telemetry}),
    (lens.add_parser, {"lens": lens.cmd_lens}),
    (graph_lens.add_parser, {"graph": graph_lens.cmd_graph}),
    (graph_mutate.add_parser, {"node": graph_mutate.cmd_node, "link": graph_mutate.cmd_link}),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ig-tool",
        description="IntentGraph hard tools — graph queries, lens ops, edit pipeline, context assembly.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""subcommands:
  validate   Check graph integrity
  query      Graph navigation (--node, --children, --ancestors, --links, --neighbors, --overview, --structure)
  parse      Parse agent edits file (was: edit parse)
  apply      Apply agent edits (-i) or batch YAML (--batch) (was: edit apply / batch)
  context    Assemble full context payload
  workflow   Workflow management: workflow step (create, summary) / workflow trace (show, record)
  obsidian   Obsidian vault operations (export, import, diff, export-canvas, export-tree, detect-pins, export-lens-canvas)
  convert    Convert graph between JSON and YAML formats
  tree       Render ASCII tree visualization of the IntentGraph
  init       Initialize a new IntentGraph
  lens       Agent I/O lens ops (build, show, tree, info, focus, promote, demote, set-lod, prune, expand, set-budget, list-pruned, diff, apply, discard)
  graph      Graph-embedded ops: graph lens (list, show, create, delete, add-node, remove-node, set-lod, add-link, remove-link, set-default, unset-default, project, reintegrate, validate, set-position, clear-position)
  node       Node manipulation (create, set, reparent, reorder, remove, show)
  link       IntentLink manipulation (create, set, remove)

output contract:
  Full results are written to -o <path>.
  Stdout always contains a compact YAML summary (status, metrics, output path).
  Agents: read the -o file only if you need the detail.""",
    )
    parser.add_argument(
        "--no-telemetry",
        action="store_true",
        help="Disable local usage logging to ~/.cache/ig-tool/usage.jsonl",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for add_parser_fn, _handlers in _COMMANDS:
        add_parser_fn(sub)

    return parser


def build_dispatch() -> dict:
    dispatch: dict = {}
    for _add_parser_fn, handlers in _COMMANDS:
        dispatch.update(handlers)
    return dispatch


DISPATCH = build_dispatch()
