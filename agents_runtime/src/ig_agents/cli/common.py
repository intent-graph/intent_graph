"""Shared helpers for ig-tool CLI command modules.

The ONE canonical copy of ``_die``/``_load_graph``/``_write_output``/``_summary``.
These were previously duplicated verbatim in both ``cli.py`` and
``cli_lens_commands.py``; both now import from here instead of defining their
own copies. Ported verbatim (behavior-identical) from ``cli.py``'s version,
which was picked as the source of truth over ``cli_lens_commands.py``'s copy
(the two had drifted only in docstring wording and a missing ``-> NoReturn``
type annotation on ``_die`` in the latter — no behavioral difference).
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.ops.provenance import content_snapshot, stamp_provenance
from intentgraph.serial.json_yaml import load_graph, save_graph


def _die(msg: str, code: int = 1) -> NoReturn:
    print(f"ig-tool: error: {msg}", file=sys.stderr)
    sys.exit(code)


def _load_graph(path: str) -> IntentGraph:
    p = Path(path)
    if not p.exists():
        _die(f"graph file not found: {path}")
    try:
        graph = load_graph(p)
    except Exception as e:
        _die(f"failed to load graph: {e}")
    # Provenance baseline: diffed against at save time (write-boundary stamping).
    graph._provenance_baseline = content_snapshot(graph)
    return graph


def resolve_actor(role: str | None = None) -> str:
    """Resolve the history `who` per the channel (formalism §4, Provenance capture).

    Agents pass --role → `agent:<role>`. Humans resolve from IG_ACTOR, then
    git user.name, then the OS user.
    """
    if role:
        return f"agent:{role}"
    actor = os.environ.get("IG_ACTOR")
    if actor:
        return actor
    try:
        git_name = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        if git_name:
            return git_name
    except Exception:
        pass
    return getpass.getuser()


def _save_graph(
    graph: IntentGraph, path: str, args: Any = None, *, channel: str | None = None
) -> list[str]:
    """Save with write-boundary provenance stamping.

    Diffs the graph against the baseline captured by ``_load_graph`` (empty
    baseline for freshly built graphs → every node stamps as created) and
    appends a commit-style HistoryEntry to each changed node. Actor comes from
    ``args.role``; the one-liner note from ``args.message`` (-m), else an
    auto-generated diff summary. ``channel`` appends a ``via:<channel>``
    qualifier for human actors (e.g. obsidian merge). Returns the stamped uids.
    """
    baseline = getattr(graph, "_provenance_baseline", {})
    role = getattr(args, "role", None)
    who = resolve_actor(role)
    if channel and not role:
        who = f"{who} via:{channel}"
    note = getattr(args, "message", None)
    stamped = stamp_provenance(graph, baseline, who=who, note=note)
    save_graph(graph, path)
    return stamped


def _write_output(content: str, output_path: str | None, emit: bool = True) -> dict[str, Any]:
    """Write content to the -o path, or emit it to stdout when no path is given.

    With `output_path`, content goes to that file. Without it, and when `emit`
    is True (the default), content is printed to stdout — like tree/convert —
    so the body is never silently dropped; the _summary header still follows.
    Pass `emit=False` for callers that only want the size metrics (the content
    has already been written elsewhere).
    """
    words = len(content.split())
    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    size = {"words": words, "lines": lines, "chars": len(content)}

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    elif emit and content:
        print(content)

    return size


def _summary(status: str, command: str, output_path: str | None, size: dict[str, Any],
             **extra: Any) -> None:
    """Print compact YAML summary to stdout. Always ≤5 lines."""
    d: dict[str, Any] = {"status": status, "command": command}
    d.update(extra)
    if output_path:
        d["output"] = output_path
        d["output_size"] = {k: size[k] for k in ("words", "lines")}
    yaml.dump(d, sys.stdout, default_flow_style=False, allow_unicode=True, sort_keys=False)

