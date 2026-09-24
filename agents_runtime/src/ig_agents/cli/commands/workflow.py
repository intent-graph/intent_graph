"""ig-tool ``workflow`` command: step folder management + trace recording.

Moved verbatim from ``cli_impl.py`` (Phase 5: workflow extraction).
``cmd_workflow`` dispatches to ``cmd_step`` (``workflow step {create,summary}``)
or ``cmd_trace`` (``workflow trace {show,record}``). Pure move: no behavior
change.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from ig_agents.cli.common import _die, _write_output, _summary


# ================================================================== #
#  Argument parser                                                     #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``workflow`` subcommand (step + trace sub-subcommands) on *sub*."""
    p_wf = sub.add_parser(
        "workflow",
        help="Workflow management: step folder ops and trace recording",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Sub-subcommands:\n"
            "  workflow step {create, summary}    Step folder lifecycle\n"
            "  workflow trace {show, record}      Workflow event trace JSONL\n"
            "Examples:\n"
            "  ig-tool workflow step create --dir steps/ --step DISTILL.SCOPE --target D --prev steps/004_X\n"
            "  ig-tool workflow trace record trace.jsonl --step S --target T --actor A --action ... --result ...\n"
            "Notes:\n"
            "  - Renamed from 'step' / 'trace' (Phase 3 hard cutover).\n"
        ),
    )
    wf_sub = p_wf.add_subparsers(dest="workflow_action", required=True)

    # workflow trace (was: trace)
    p_wt = wf_sub.add_parser(
        "trace",
        help="Workflow trace operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool workflow trace record trace.jsonl --step DISTILL.SCOPE --target D \\\n"
            "      --actor steward --action 'apply edits' --result 'ok'\n"
            "  ig-tool workflow trace show trace.jsonl --workflow distill\n"
        ),
    )
    p_wt.add_argument("action", choices=["show", "record"])
    p_wt.add_argument("trace_file", help="Path to trace JSONL file")
    p_wt.add_argument("-o", "--output", help="Write output to this path")
    p_wt.add_argument("--step", help="Step UID (record)")
    p_wt.add_argument("--target", help="Target UID (record)")
    p_wt.add_argument("--actor", help="Actor name (record)")
    p_wt.add_argument("--action", dest="act", help="Action description (record)")
    p_wt.add_argument("--result", help="Result description (record)")
    p_wt.add_argument("--workflow", help="Workflow name (show)")
    p_wt.add_argument("--graph-name", help="Graph name (show)")

    # workflow step (was: step)
    p_ws = wf_sub.add_parser(
        "step",
        help="Step folder management (create, summary)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool workflow step create --dir steps/ --step DISTILL.REFINE --target D \\\n"
            "      --prev steps/017_DISTILL.CHALLENGE \\\n"
            "      --copy output_issues.yaml:input_issues.yaml\n"
            "  ig-tool workflow step summary steps/017_DISTILL.CHALLENGE/output_issues.yaml\n"
            "Notes:\n"
            "  - --copy SRC:DST is repeatable; copies files from --prev into the new step folder.\n"
        ),
    )
    p_ws.add_argument("action", choices=["create", "summary"])
    p_ws.add_argument("file", nargs="?", help="File path (for summary)")
    p_ws.add_argument("--dir", help="Steps directory (for create)")
    p_ws.add_argument("--step", dest="step", help="Step UID (for create)")
    p_ws.add_argument("--target", help="Target UID (for create)")
    p_ws.add_argument("--prev", help="Previous step folder path (for create)")
    p_ws.add_argument("--copy", action="append", metavar="SRC:DST",
                      help="Copy file from prev step (src:dst or filename). Repeatable.")
    p_ws.add_argument("-o", "--output", help="Write output to this path (for summary)")


# ================================================================== #
#  workflow (dispatch)                                                 #
# ================================================================== #


def cmd_workflow(args: argparse.Namespace) -> None:
    """Dispatch workflow sub-subcommand (step or trace)."""
    if args.workflow_action == "step":
        cmd_step(args)
    elif args.workflow_action == "trace":
        cmd_trace(args)
    else:
        _die(f"unknown workflow action: {args.workflow_action}")


# ================================================================== #
#  trace                                                               #
# ================================================================== #


def cmd_trace(args: argparse.Namespace) -> None:
    from ig_agents.trace import WorkflowTrace

    trace = WorkflowTrace(args.trace_file)

    if args.action == "show":
        content = trace.render(
            workflow_name=args.workflow or "",
            graph_name=args.graph_name or "",
        )
        size = _write_output(content, args.output)
        entries = trace.read()
        _summary("ok", "trace show", args.output, size,
                 entries=len(entries))
        return

    if args.action == "record":
        if not all([args.step, args.target, args.actor, args.act, args.result]):
            _die("record requires: --step, --target, --actor, --action, --result")
        trace.record(
            step=args.step,
            target=args.target,
            actor=args.actor,
            action=args.act,
            result=args.result,
        )
        _summary("ok", "trace record", None, {"words": 0, "lines": 0, "chars": 0},
                 step=args.step, target=args.target, actor=args.actor)
        return

    _die(f"unknown trace action: {args.action}")


# ================================================================== #
#  step                                                                #
# ================================================================== #


def _next_step_number(steps_dir: Path) -> int:
    """Find the next sequential step number by scanning existing folders."""
    max_n = 0
    if steps_dir.exists():
        for child in steps_dir.iterdir():
            if child.is_dir() and child.name[:3].isdigit():
                try:
                    max_n = max(max_n, int(child.name[:3]))
                except ValueError:
                    pass
    return max_n + 1


def _parse_copy_spec(spec: str) -> tuple[str, str]:
    """Parse a copy spec 'src:dst' or 'filename' (same name for both)."""
    if ":" in spec:
        src, dst = spec.split(":", 1)
        return src.strip(), dst.strip()
    return spec.strip(), spec.strip()


def cmd_step(args: argparse.Namespace) -> None:
    if args.action == "create":
        steps_dir = Path(args.dir)
        steps_dir.mkdir(parents=True, exist_ok=True)

        seq = _next_step_number(steps_dir)
        folder_name = f"{seq:03d}_{args.step}"
        step_folder = steps_dir / folder_name
        step_folder.mkdir()

        copied: list[dict[str, str]] = []
        if args.prev and args.copy:
            prev_dir = Path(args.prev)
            if not prev_dir.is_dir():
                _die(f"previous step folder not found: {args.prev}")

            for spec in args.copy:
                src_name, dst_name = _parse_copy_spec(spec)
                src_path = prev_dir / src_name
                dst_path = step_folder / dst_name
                if not src_path.exists():
                    _die(f"source file not found: {src_path}")
                import shutil
                shutil.copy2(str(src_path), str(dst_path))
                copied.append({"src": src_name, "dst": dst_name})

        from datetime import datetime
        manifest: dict[str, Any] = {
            "step": args.step,
            "target": args.target or "",
            "created": datetime.now().isoformat(timespec="seconds"),
            "inputs": [
                {"file": c["dst"], "role": f"copied from prev step ({c['src']})", "required": True}
                for c in copied
            ],
            "expected_outputs": [],
            "notes": [],
        }
        if args.prev:
            manifest["prev_step"] = str(Path(args.prev).name)

        manifest_text = yaml.dump(manifest, default_flow_style=False,
                                  allow_unicode=True, sort_keys=False)
        (step_folder / "_manifest.yaml").write_text(manifest_text, encoding="utf-8")

        size = _write_output(manifest_text, None, emit=False)
        _summary("ok", "step create", str(step_folder), size,
                 folder=folder_name, files_copied=len(copied))
        return

    if args.action == "summary":
        if not args.file:
            _die("step summary requires a file path argument")

        target = Path(args.file)
        if not target.exists():
            _die(f"file not found: {args.file}")

        raw = target.read_text(encoding="utf-8")

        metrics: dict[str, Any] = {}
        try:
            data = yaml.safe_load(raw)
            if isinstance(data, dict):
                _SCALAR_KEYS = {"status", "major", "moderate", "minor",
                                "edit_count", "edits_applied", "applied",
                                "nodes_created", "nodes_updated", "nodes_deleted",
                                "product_issues", "pig_issues"}
                _LIST_KEYS = {"issues", "edits", "details", "log"}
                for key in _SCALAR_KEYS:
                    if key in data and isinstance(data[key], (int, float, str, bool)):
                        metrics[key] = data[key]
                for key in _LIST_KEYS:
                    if key in data and isinstance(data[key], list):
                        metrics[f"{key}_count"] = len(data[key])
                        severities: dict[str, int] = {}
                        for item in data[key]:
                            if isinstance(item, dict) and "severity" in item:
                                sev = item["severity"]
                                severities[sev] = severities.get(sev, 0) + 1
                        if severities:
                            metrics[f"{key}_by_severity"] = severities
                if not metrics:
                    metrics["top_keys"] = list(data.keys())[:10]
            elif isinstance(data, list):
                metrics["item_count"] = len(data)
        except yaml.YAMLError:
            pass

        words = len(raw.split())
        lines = raw.count("\n")
        metrics["words"] = words
        metrics["lines"] = lines

        summary_text = yaml.dump({"file": str(target.name), "metrics": metrics},
                                 default_flow_style=False, allow_unicode=True,
                                 sort_keys=False)
        size = _write_output(summary_text, args.output)
        _summary("ok", "step summary", args.output, size, **metrics)
        return

    _die(f"unknown step action: {args.action}")
