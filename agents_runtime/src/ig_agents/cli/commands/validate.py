"""ig-tool ``validate`` command: graph structural integrity + lens checks.

Moved verbatim from ``cli_impl.py`` (Phase 2: command extraction). Pure move:
no behavior change.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from intentgraph.models.graph import IntentGraph

from ig_agents.cli.common import _die, _write_output, _summary, _load_graph


def add_parser(sub: Any) -> None:
    """Register the ``validate`` subcommand on *sub*."""
    p_val = sub.add_parser(
        "validate",
        help="Check graph integrity (T1-T5 + structural health)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool validate -g graph.json\n"
            "  ig-tool validate -g graph.yaml -o report.yaml\n"
            "  ig-tool validate -g graph.json -m intent_resources.yaml  # also check inter intentlinks\n"
            "Notes:\n"
            "  - Accepts both .json and .yaml graphs.\n"
            "  - Stdout: compact YAML summary. Use -o for full report.\n"
        ),
    )
    p_val.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_val.add_argument("-m", "--manifest", metavar="PATH", help="Path to intent_resources.yaml; when set, validate inter intentlink endpoints")
    p_val.add_argument("-o", "--output", help="Write full report to this path")


# ================================================================== #
#  validate                                                            #
# ================================================================== #


def _validate_graph(graph: IntentGraph) -> list[dict[str, str]]:
    """Structural integrity checks beyond constructor enforcement."""
    issues: list[dict[str, str]] = []
    roots = {n.uid for n in graph.roots()}

    for node in graph.iter_nodes():
        if node.parent_uid is None and node.uid not in roots:
            issues.append({"severity": "warning", "uid": node.uid,
                           "issue": "orphan node — no parent and not recognized as root"})
        if node.parent_uid is not None and node.parent_uid not in graph.nodes:
            issues.append({"severity": "error", "uid": node.uid,
                           "issue": f"broken parent_uid -> '{node.parent_uid}'"})
        for child_uid in node.children_uids:
            if child_uid not in graph.nodes:
                issues.append({"severity": "error", "uid": node.uid,
                               "issue": f"broken child ref -> '{child_uid}'"})
        if not node.intent.strip():
            issues.append({"severity": "warning", "uid": node.uid,
                           "issue": "empty intent field"})

    for link in graph.iter_links():
        if link.src not in graph.nodes:
            issues.append({"severity": "error", "uid": link.uid,
                           "issue": f"link src '{link.src}' does not exist"})
        if link.dst not in graph.nodes:
            issues.append({"severity": "error", "uid": link.uid,
                           "issue": f"link dst '{link.dst}' does not exist"})

    return issues


def cmd_validate(args: argparse.Namespace) -> None:
    graph = _load_graph(args.graph)
    issues = _validate_graph(graph)

    # Lens validation rules (Spec §7 V-L1 through V-L7, and §10 V-CG1–V-CG4)
    from pathlib import Path
    from intentgraph.validation import validate_lenses
    _ig_path = Path(args.graph).resolve() if getattr(args, "graph", None) else None
    lens_issues = validate_lenses(graph, ig_path=_ig_path)
    issues = issues + lens_issues

    # Optional: validate inter intentlink endpoints when manifest is provided
    if getattr(args, "manifest", None):
        from pathlib import Path
        from intentgraph.serial.intent_resources import resolve_graph_path
        from intentgraph.validation import validate_inter_intentlinks
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            _die(f"manifest file not found: {args.manifest}")
        def resolve_fn(gid: str):
            return resolve_graph_path(manifest_path, gid)
        inter_issues = validate_inter_intentlinks(graph, resolve_fn)
        issues = issues + inter_issues

    report: dict[str, Any] = {
        "graph": args.graph,
        "nodes": graph.node_count(),
        "links": graph.link_count(),
        "inter_links": graph.inter_link_count(),
        "issues": len(issues),
        "errors": sum(1 for i in issues if i["severity"] == "error"),
        "warnings": sum(1 for i in issues if i["severity"] == "warning"),
    }
    if issues:
        report["details"] = issues

    content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
    size = _write_output(content, args.output)

    errors = report["errors"]
    warnings = report["warnings"]
    status = "error" if errors else ("warning" if warnings else "ok")

    _summary(status, "validate",
             args.output, size,
             nodes=graph.node_count(), links=graph.link_count(),
             errors=errors, warnings=warnings)

    if errors:
        sys.exit(1)
