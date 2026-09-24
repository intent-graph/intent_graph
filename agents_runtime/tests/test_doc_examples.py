"""Regression: every `ig-tool` invocation in agent-facing docs must parse cleanly.

Globs all markdown files under agent-facing directories, extracts every line
beginning with ``ig-tool `` from fenced code blocks, and verifies it parses
through ``build_parser().parse_known_args()``.

Skips invocations containing template placeholders (``<...>``, ``{...}``, or
all-caps tokens like ``UID``, ``NAME``, etc.) that cannot be filled by a test.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from ig_agents.cli import build_parser


# repo root: agents_runtime/tests/<this file> → parents[2]
REPO = Path(__file__).resolve().parents[2]
DOC_GLOBS = [
    ".claude/agents/*.md",
    ".claude/skills/*/SKILL.md",
    "agents/**/*.md",
    "agents_runtime/orchestrator*/**/*.md",
    "agents_runtime/*.md",
    "*.md",
]
SKIP_PATH_TOKENS = (".ARCHIVED", "_LEGACY", "__pycache__", ".venv")
ANGLE_PLACEHOLDER = re.compile(r"<[A-Za-z_]+>")
BRACE_PLACEHOLDER = re.compile(r"\{[A-Za-z_]+\}")
# All-caps placeholders frequently used in docs as "fill me in" markers.
ALL_CAPS_PLACEHOLDER = re.compile(
    r"\b("
    r"UID|UIDS|NODE_UID|LINK_UID|TARGET|TARGET_UID|"
    r"NAME|LENS_NAME|FRONTIER|FRONTIER_NAME|"
    r"GRAPH|GRAPH_PATH|FILE|PATH|DIR|"
    r"SRC|DST|SRC_UID|DST_UID|"
    r"INTENT|STATE|ROLE|"
    r"TOKENS|BUDGET|N|DEPTH|"
    r"AGENT|EXTRACTOR|STEWARD"
    r")\b"
)
FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)


def _has_placeholder(line: str) -> bool:
    if ANGLE_PLACEHOLDER.search(line):
        return True
    if BRACE_PLACEHOLDER.search(line):
        return True
    if ALL_CAPS_PLACEHOLDER.search(line):
        return True
    return False


def _extract_invocations() -> list[tuple[str, int, str]]:
    """Return (rel_path, line_number, invocation) for every ig-tool line.

    Joins backslash-continued lines into a single invocation. Strips inline
    comments. Skips invocations containing template placeholders.
    """
    out: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int, str]] = set()
    for pattern in DOC_GLOBS:
        for path in REPO.glob(pattern):
            spath = str(path)
            if any(tok in spath for tok in SKIP_PATH_TOKENS):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in FENCE_RE.finditer(text):
                block_start = text[: match.start()].count("\n") + 2
                lines = match.group(1).splitlines()
                i = 0
                while i < len(lines):
                    raw = lines[i].strip()
                    if raw.startswith("$ "):
                        raw = raw[2:]
                    if not raw.startswith("ig-tool "):
                        i += 1
                        continue
                    start_offset = i
                    # Glue backslash-continued lines
                    parts: list[str] = []
                    while i < len(lines):
                        cur = lines[i].strip()
                        if cur.startswith("$ "):
                            cur = cur[2:]
                        ends_in_continuation = cur.rstrip().endswith("\\")
                        if ends_in_continuation:
                            parts.append(cur.rstrip().rstrip("\\").rstrip())
                            i += 1
                            continue
                        parts.append(cur)
                        i += 1
                        break
                    line = " ".join(p for p in parts if p)
                    # Strip trailing inline shell comments (heuristic: "  # ")
                    if "  #" in line:
                        line = line.split("  #", 1)[0].strip()
                    if not line:
                        continue
                    if _has_placeholder(line):
                        continue
                    rel = str(path.relative_to(REPO))
                    key = (rel, block_start + start_offset, line)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(key)
    return out


INVOCATIONS = _extract_invocations()


def test_extracted_at_least_one_invocation():
    """Sanity: the extractor finds something. If this fails, the globs are wrong."""
    assert len(INVOCATIONS) > 0, "No ig-tool invocations extracted from docs"


@pytest.mark.parametrize(
    "file_path,line_no,invocation",
    INVOCATIONS,
    ids=[f"{rel}:{ln}" for rel, ln, _ in INVOCATIONS],
)
def test_doc_invocation_parses(file_path: str, line_no: int, invocation: str):
    """Every documented ig-tool invocation must parse against the live parser."""
    try:
        tokens = shlex.split(invocation)
    except ValueError as exc:
        pytest.fail(f"{file_path}:{line_no} — shlex error on `{invocation}`: {exc}")
    assert tokens[0] == "ig-tool", f"unexpected leading token: {tokens[0]}"
    parser = build_parser()
    try:
        parser.parse_known_args(tokens[1:])
    except SystemExit as exc:
        pytest.fail(
            f"{file_path}:{line_no} — `{invocation}` does not parse "
            f"(exit {exc.code})"
        )
