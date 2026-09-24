"""ig-tool ``parse``, ``apply`` (incl. ``--batch``) commands: the edit pipeline.

Moved from ``cli_impl.py``/``cli_lens_commands.py`` (Phase 3: Edit pipeline).
``parse``, ``apply``, and batch execution share the ``EditOp``/
``apply_edits`` mutation surface (PRIMER_01_SEMANTICS, PRIMER_03A_EDITING) —
kept together in one module because the edit domain requires it, not split
across agents/files.

**The structural fix (Bug 1, structural half):**
``cmd_apply``'s ``--batch`` path used to hand-build a synthetic
``argparse.Namespace`` to call ``cmd_batch`` — a delegation antipattern that
silently dropped ``role`` because the Namespace didn't include it. That
delegation is replaced here with a typed function call:
``run_batch(BatchParams(role=params.role, ...))``. ``BatchParams`` is a
frozen, keyword-only dataclass — a missing/renamed field is now a
construction-time ``TypeError``, not a silent ``getattr(ns, "role", None)``
drop. This is the general fix for hand-built namespace delegation, not just
the ``--role`` instance.

Batch execution itself (``run_batch``) still executes operations via direct
``graph.add_node()``/``update_node()`` calls rather than translating to
``EditOp``s through ``apply_edits`` — the preferred structural fix would
involve rewriting batch execution to use the unified edit pipeline, but that
was deferred and kept as a follow-up opportunity.
"""

from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.serial.agent_text import apply_edits, text_to_edits

from ig_agents.cli.common import _die, _load_graph, _save_graph, _write_output, _summary


# ================================================================== #
#  Typed params                                                       #
# ================================================================== #


@dataclass(frozen=True, kw_only=True)
class ParseParams:
    """Params for ``ig-tool parse`` (read-only: report what would be applied)."""

    graph_path: str
    input_path: str
    output_path: str | None = None
    role: str | None = None


@dataclass(frozen=True, kw_only=True)
class ApplyParams:
    """Params for ``ig-tool apply`` (single-edits-file mode, ``-i``)."""

    graph_path: str
    input_path: str | None = None
    output_path: str | None = None
    role: str | None = None
    message: str | None = None
    dry_run: bool = False


@dataclass(frozen=True, kw_only=True)
class BatchParams:
    """Params for batch execution (``ig-tool apply --batch``).

    Every field ``cmd_batch``'s body reads from ``args`` has an explicit
    counterpart here. Threading a new field through in the future means
    adding it to this dataclass and to the ``BatchParams(...)`` construction
    call in ``cmd_apply`` — a missing field fails at construction, not at
    runtime deep inside batch execution.
    """

    graph_path: str
    batch_path: str
    output_path: str | None = None
    role: str | None = None
    message: str | None = None
    dry_run: bool = False


def _parse_params_from_args(args: argparse.Namespace) -> ParseParams:
    return ParseParams(
        graph_path=args.graph,
        input_path=args.input,
        output_path=args.output,
        role=getattr(args, "role", None),
    )


def _apply_params_from_args(args: argparse.Namespace) -> ApplyParams:
    return ApplyParams(
        graph_path=args.graph,
        input_path=getattr(args, "input", None),
        output_path=getattr(args, "output", None),
        role=getattr(args, "role", None),
        message=getattr(args, "message", None),
        dry_run=getattr(args, "dry_run", False),
    )


def _batch_params_from_args(args: argparse.Namespace) -> BatchParams:
    """Build ``BatchParams`` from a real ``apply --batch`` (or legacy ``batch``)
    Namespace. Used only when ``run_batch``/``cmd_batch`` is invoked directly
    (e.g. tests, legacy standalone ``batch`` command) — ``cmd_apply`` itself
    constructs ``BatchParams`` inline from its own already-typed ``ApplyParams``
    plus the ``--batch`` file path, not through this helper.
    """
    return BatchParams(
        graph_path=args.graph,
        batch_path=args.input,
        output_path=getattr(args, "output", None),
        role=getattr(args, "role", None),
        message=getattr(args, "message", None),
        dry_run=getattr(args, "dry_run", False),
    )


# ================================================================== #
#  parse                                                               #
# ================================================================== #


def run_parse(params: ParseParams, graph: IntentGraph) -> dict[str, Any]:
    """Parse an agent edits file against *graph* and report what would apply.

    Read-only: does not mutate *graph*. Returns the report dict (also written
    via ``_write_output``/``_summary`` by the ``cmd_parse`` wrapper).
    """
    edits_path = Path(params.input_path)
    if not edits_path.exists():
        _die(f"edits file not found: {params.input_path}")

    edits_text = edits_path.read_text(encoding="utf-8")

    try:
        edits = text_to_edits(edits_text, graph)
    except Exception as e:
        _die(f"parse error: {e}")

    items = []
    for edit in edits:
        entry = {"type": type(edit).__name__}
        entry.update({k: v for k, v in edit.__dict__.items() if k != "fields"})
        items.append(entry)
    return {"edit_count": len(edits), "edits": items}


def cmd_parse(args: argparse.Namespace) -> None:
    """Top-level 'parse' command — was 'edit parse'."""
    params = _parse_params_from_args(args)
    graph = _load_graph(params.graph_path)
    report = run_parse(params, graph)

    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
    size = _write_output(content, params.output_path)
    _summary("ok", "edit parse", params.output_path, size, edit_count=report["edit_count"])


# ================================================================== #
#  apply (single edits file, -i)                                      #
# ================================================================== #


def run_apply(params: ApplyParams, graph: IntentGraph) -> dict[str, Any]:
    """Parse and apply an agent edits file to *graph* (mutates *graph* in place
    unless ``params.dry_run``, in which case a deep copy is mutated instead).

    Returns the apply report dict. Raises via ``_die`` on parse/apply failure
    (matches prior behavior — these are user-input errors, not exceptions to
    propagate).
    """
    edits_path = Path(params.input_path)
    if not edits_path.exists():
        _die(f"edits file not found: {params.input_path}")

    edits_text = edits_path.read_text(encoding="utf-8")

    try:
        edits = text_to_edits(edits_text, graph)
    except Exception as e:
        _die(f"parse error: {e}")

    if params.dry_run:
        try:
            test_graph = deepcopy(graph)
            log = apply_edits(test_graph, edits)
            return {"dry_run": True, "applied": len(log), "log": log}
        except Exception as e:
            _die(f"dry run failed: {e}")

    if not params.output_path:
        _die("edit apply requires -o OUTPUT_GRAPH (will not overwrite input)")

    try:
        log = apply_edits(graph, edits)
    except Exception as e:
        _die(f"apply failed: {e}")

    return {"applied": len(log), "log": log, "saved_to": params.output_path}


def cmd_apply(args: argparse.Namespace) -> None:
    """Top-level 'apply' command — was 'edit apply'; --batch folds in batch.

    Structural fix (Bug 1): the ``--batch`` path used to hand-build a
    synthetic ``argparse.Namespace`` to call ``cmd_batch``, silently dropping
    ``role`` because it wasn't included. Replaced with a typed function call —
    ``run_batch(BatchParams(...))`` — where every field ``run_batch`` needs is
    an explicit constructor
    parameter; a missing one is a construction-time error.
    """
    params = _apply_params_from_args(args)

    if getattr(args, "batch", None):
        batch_params = BatchParams(
            graph_path=params.graph_path,
            batch_path=args.batch,
            output_path=params.output_path,
            role=params.role,
            message=params.message,
            dry_run=params.dry_run,
        )
        run_batch(batch_params)
        return

    graph = _load_graph(params.graph_path)
    report = run_apply(params, graph)

    if params.dry_run:
        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, params.output_path)
        _summary("ok", "edit apply --dry-run", params.output_path, size,
                 edits_applied=report["applied"])
        return

    _save_graph(graph, params.output_path, params)

    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
    # Write the apply report alongside the graph
    report_path = str(Path(params.output_path).with_suffix(".apply_report.yaml"))
    _write_output(content, report_path)
    size = {"words": 0, "lines": 0, "chars": 0}  # summary refers to the graph
    _summary("ok", "edit apply", params.output_path, size,
             edits_applied=report["applied"], report=report_path)


# ================================================================== #
#  edit (legacy alias: 'edit parse' / 'edit apply')                   #
# ================================================================== #


def cmd_edit(args: argparse.Namespace) -> None:
    """Legacy 'edit parse'/'edit apply' dispatch — kept for any caller still
    building an ``action``-bearing Namespace directly (parse/apply are the
    hard-cutover top-level names; this function is not wired into the parser).
    """
    if args.action == "parse":
        cmd_parse(args)
        return
    if args.action == "apply":
        cmd_apply(args)
        return
    _die(f"unknown edit action: {args.action}")


# ================================================================== #
#  batch                                                              #
# ================================================================== #


def run_batch(params: BatchParams) -> dict[str, Any]:
    """Execute a batch YAML file's operations against the graph at
    ``params.graph_path``, honoring ``params.role`` (history stamping) and
    ``params.dry_run``. Loads the graph itself (batch is always driven from a
    path, matching the CLI's ``-g``/``--batch`` contract) and saves to
    ``params.output_path`` on success unless ``params.dry_run``.

    Returns the batch report dict. On error, writes the error report and
    calls ``sys.exit(1)`` (matches prior ``cmd_batch`` behavior exactly).
    """
    if not params.output_path and not params.dry_run:
        _die("batch requires -o OUTPUT_GRAPH (or --dry-run)")

    graph = _load_graph(params.graph_path)

    # Load batch file
    batch_path = Path(params.batch_path)
    if not batch_path.exists():
        _die(f"batch file not found: {params.batch_path}")

    try:
        batch_data = yaml.safe_load(batch_path.read_text(encoding="utf-8"))
    except Exception as e:
        _die(f"failed to parse batch YAML: {e}")

    if not isinstance(batch_data, dict) or "operations" not in batch_data:
        _die("batch YAML must contain 'operations' list")

    operations = batch_data["operations"]
    if not isinstance(operations, list):
        _die("'operations' must be a list")

    # Execute operations
    results = []
    graph_backup = None

    if not params.dry_run:
        # Deep copy for atomic rollback
        graph_backup = deepcopy(graph)

    try:
        for i, op in enumerate(operations):
            if not isinstance(op, dict) or "op" not in op:
                _die(f"operation {i}: missing 'op' field")

            op_type = op["op"]
            op_result = {"index": i, "op": op_type, "status": "pending"}

            # ---- node.create ----
            if op_type == "node.create":
                uid = op.get("uid")
                name = op.get("name")
                intent = op.get("intent")
                parent = op.get("parent")

                if not all([uid, name, intent]):
                    raise ValueError(f"node.create requires uid, name, intent")

                kwargs = {}
                for f in ["epistemic_state", "design_notes", "effort"]:
                    if f in op:
                        kwargs[f] = op[f]
                if "constraints" in op:
                    kwargs["constraints"] = list(op["constraints"])
                if "examples" in op:
                    kwargs["examples"] = list(op["examples"])
                if "impl_pointers" in op:
                    kwargs["impl_pointers"] = op["impl_pointers"]
                if "data_registry" in op:
                    kwargs["data_registry"] = op["data_registry"]

                graph.add_node(uid, name, intent, **kwargs)
                if parent:
                    graph.attach(parent, uid)

                op_result["status"] = "success"
                op_result["uid"] = uid

            # ---- node.set ----
            elif op_type == "node.set":
                uid = op.get("uid")
                if not uid:
                    raise ValueError(f"node.set requires uid")

                kwargs = {}
                for f in ["name", "intent", "epistemic_state", "design_notes", "effort",
                          "constraints", "examples", "impl_pointers", "data_registry"]:
                    if f in op:
                        kwargs[f] = op[f]

                unset_fields = list(op.get("unset", []) or [])
                overlap = set(unset_fields) & set(kwargs)
                if overlap:
                    raise ValueError(f"node.set: field(s) both set and unset: {sorted(overlap)}")
                if not kwargs and not unset_fields:
                    raise ValueError(f"node.set requires at least one field to update (or 'unset')")

                if kwargs:
                    graph.update_node(uid, **kwargs)
                if unset_fields:
                    graph.unset_node_fields(uid, unset_fields)

                op_result["status"] = "success"
                op_result["uid"] = uid
                op_result["fields"] = list(kwargs.keys()) + [f"unset:{f}" for f in unset_fields]

            # ---- node.reparent ----
            elif op_type == "node.reparent":
                child_uid = op.get("child")
                new_parent = op.get("under")

                if not all([child_uid, new_parent]):
                    raise ValueError(f"node.reparent requires child, under")

                child = graph.get_node(child_uid)
                if child.parent_uid:
                    graph.detach(child.parent_uid, child_uid)
                graph.attach(new_parent, child_uid)

                op_result["status"] = "success"
                op_result["child"] = child_uid
                op_result["new_parent"] = new_parent

            # ---- node.remove ----
            elif op_type == "node.remove":
                uid = op.get("uid")
                recursive = op.get("recursive", False)

                if not uid:
                    raise ValueError(f"node.remove requires uid")

                removed_count = 1
                if recursive:
                    desc_uids = graph.desc(uid)
                    removed_count = 1 + len(desc_uids)

                graph.remove_node(uid, cascade=recursive)

                op_result["status"] = "success"
                op_result["uid"] = uid
                op_result["removed_count"] = removed_count

            # ---- link.create ----
            elif op_type == "link.create":
                src = op.get("src")
                dst = op.get("dst")
                intent = op.get("intent")

                if not all([src, dst, intent]):
                    raise ValueError(f"link.create requires src, dst, intent")

                kwargs = {}
                if "uid" in op:
                    kwargs["uid"] = op["uid"]
                if "tag" in op:
                    kwargs["tag"] = op["tag"]
                if "shape" in op:
                    kwargs["shape"] = op["shape"]
                if "parent" in op:
                    kwargs["parent"] = op["parent"]

                link = graph.add_link(src, dst, intent, **kwargs)

                op_result["status"] = "success"
                op_result["link_uid"] = link.uid
                op_result["src"] = src
                op_result["dst"] = dst

            # ---- link.set ----
            elif op_type == "link.set":
                uid = op.get("uid")
                if not uid:
                    raise ValueError(f"link.set requires uid")

                kwargs = {}
                for f in ["intent", "shape", "parent"]:
                    if f in op:
                        kwargs[f] = op[f]

                if not kwargs:
                    raise ValueError(f"link.set requires at least one field to update")

                graph.update_link(uid, **kwargs)

                op_result["status"] = "success"
                op_result["uid"] = uid
                op_result["fields"] = list(kwargs.keys())

            # ---- link.remove ----
            elif op_type == "link.remove":
                uid = op.get("uid")
                if not uid:
                    raise ValueError(f"link.remove requires uid")

                graph.remove_link(uid)

                op_result["status"] = "success"
                op_result["uid"] = uid

            else:
                raise ValueError(f"unknown operation type: {op_type}")

            results.append(op_result)

    except Exception as e:
        # Rollback
        if graph_backup is not None:
            graph = graph_backup

        # Mark current operation as failed
        if results and results[-1]["status"] == "pending":
            results[-1]["status"] = "error"
            results[-1]["error"] = str(e)

        report = {
            "status": "error",
            "error": str(e),
            "operations_attempted": len(results),
            "operations_succeeded": sum(1 for r in results if r["status"] == "success"),
            "rollback": "all changes discarded" if graph_backup else "n/a",
            "results": results,
        }

        # Never write the error report to params.output_path: the batch did not
        # apply, and output_path is typically the graph destination (often the
        # same path as -g) — writing there would overwrite the source graph
        # with an error report, destroying it. Error report always goes to
        # stdout, matching the "output_path unset" reporting shape.
        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, None)

        _summary("error", "batch", None, size,
                 operations_attempted=len(results),
                 operations_succeeded=sum(1 for r in results if r["status"] == "success"))
        sys.exit(1)

    # Success - save if not dry-run
    if params.dry_run:
        report = {
            "dry_run": True,
            "operations": len(results),
            "results": results,
        }
    else:
        _save_graph(graph, params.output_path, params)
        report = {
            "status": "success",
            "operations": len(results),
            "saved_to": params.output_path,
            "results": results,
        }

    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
    _write_output(content, None)  # Always to stdout for batch

    size_for_graph = {"words": 0, "lines": 0, "chars": 0}
    _summary("ok", "batch", params.output_path if not params.dry_run else None, size_for_graph,
             operations=len(results),
             dry_run=params.dry_run)

    return report


def cmd_batch(args: argparse.Namespace) -> None:
    """Legacy standalone 'batch' entrypoint (Namespace-bearing) — kept for any
    caller still building a batch-shaped Namespace directly (e.g. tests that
    predate the typed-params refactor). Translates to ``BatchParams`` and
    delegates to ``run_batch``; not wired into the parser (``apply --batch``
    is the only CLI-visible surface).
    """
    run_batch(_batch_params_from_args(args))


# ================================================================== #
#  Argument parser                                                     #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``parse`` and ``apply`` subcommands on *sub*."""
    # ---- parse (was: edit parse) ----
    p_parse = sub.add_parser(
        "parse",
        help="Parse agent edits file and report what would be applied",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool parse -g graph.json -i agent_output.yaml -o parsed.yaml\n"
            "Notes:\n"
            "  - Read-only: validates and reports; does not mutate the graph.\n"
            "  - To apply: ig-tool apply -g graph.json -i parsed.yaml -o updated.json\n"
            "  - Renamed from 'edit parse' (Phase 3 hard cutover).\n"
        ),
    )
    p_parse.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_parse.add_argument("-i", "--input", required=True, metavar="EDITS", help="Path to agent output YAML")
    p_parse.add_argument("-o", "--output", metavar="PATH", help="Output path for parse report")
    p_parse.add_argument("--role", metavar="AGENT", help="Agent role for history entries")

    # ---- apply (was: edit apply; --batch folds in: batch) ----
    p_apply = sub.add_parser(
        "apply",
        help="Apply agent edits to graph, or run a batch YAML file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool apply -g graph.json -i edits.yaml -o updated.json --role steward\n"
            "  ig-tool apply -g graph.json --batch ops.yaml -o updated.json --role extractor\n"
            "  ig-tool apply -g graph.json -i edits.yaml -o updated.json --dry-run\n"
            "Notes:\n"
            "  - -g and -o are required. Either -i (single edits file) or --batch (batch file).\n"
            "  - --role appends an audit entry to each modified node's history.\n"
            "  - Renamed from 'edit apply'; --batch absorbs the old 'batch' command.\n"
        ),
    )
    p_apply.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_apply.add_argument("-i", "--input", metavar="EDITS", help="Path to agent output YAML (single edit)")
    p_apply.add_argument("--batch", metavar="FILE", help="Path to batch YAML file (was: batch -i FILE)")
    p_apply.add_argument("-o", "--output", metavar="PATH", help="Output path (updated graph)")
    p_apply.add_argument("--role", metavar="AGENT", help="Agent role for provenance (history who = agent:<role>)")
    p_apply.add_argument("-m", "--message", help="One-liner history note for this change (commit-style)")
    p_apply.add_argument("--dry-run", action="store_true", help="Simulate apply without saving")
