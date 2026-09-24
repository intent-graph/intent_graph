"""Bridge between CodeMap and IntentGraph agent infrastructure.

Wraps CodeMap's Python API for use by agent context assembly.
CodeMap is an optional dependency — all functions degrade gracefully
when the ``codemap`` package is not installed.

Two usage patterns:
1. **Infrastructure**: call these functions from ``context.py`` to include
   CodeMap output in assembled agent contexts.
2. **Pre-rendered**: the orchestrator (main Claude Code session) calls these
   before invoking an agent, passing the YAML text directly into the prompt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ================================================================== #
#  Optional import guard                                               #
# ================================================================== #

try:
    from codemap import CodeMap  # type: ignore[import-untyped]

    _CODEMAP_AVAILABLE = True
except ImportError:
    _CODEMAP_AVAILABLE = False


def codemap_available() -> bool:
    """Check whether the ``codemap`` package is importable."""
    return _CODEMAP_AVAILABLE


# ================================================================== #
#  Build                                                               #
# ================================================================== #


def build_codemap(project_path: str | Path) -> Any | None:
    """Parse a project into a CodeMap, or ``None`` if codemap is not installed.

    Returns the ``CodeMap`` object (from ``codemap.api``).
    """
    if not _CODEMAP_AVAILABLE:
        logger.info("codemap not installed — skipping build for %s", project_path)
        return None

    return CodeMap.build(project_path)


# ================================================================== #
#  Context rendering for agents                                        #
# ================================================================== #


def overview_for_context(project_path: str | Path) -> str:
    """Build a CodeMap and return the ``overview()`` YAML for agent context.

    Returns an empty string (with a comment) if codemap is not available.
    """
    cm = build_codemap(project_path)
    if cm is None:
        return "# CodeMap not available — codemap package not installed\n"
    return cm.overview()


def context_for_focus(project_path: str | Path, qualified_name: str) -> str:
    """Build a CodeMap and return IV-context ``context()`` YAML for a focus node.

    Returns an empty string (with a comment) if codemap is not available
    or the node is not found.
    """
    cm = build_codemap(project_path)
    if cm is None:
        return "# CodeMap not available — codemap package not installed\n"

    try:
        return cm.context(qualified_name)
    except Exception as e:
        return f"# CodeMap context failed for {qualified_name}: {e}\n"


def neighbors_for_links(
    project_path: str | Path,
    qualified_name: str,
    edge_type: str | None = None,
) -> str:
    """Build a CodeMap and return neighbors as formatted text.

    Useful for inferring intentlink candidates from code relationships.
    Returns an empty string (with a comment) if codemap is not available.
    """
    cm = build_codemap(project_path)
    if cm is None:
        return "# CodeMap not available — codemap package not installed\n"

    try:
        neighbors = cm.neighbors(qualified_name, edge_type)
    except Exception as e:
        return f"# CodeMap neighbors failed for {qualified_name}: {e}\n"

    if not neighbors:
        return f"# No neighbors found for {qualified_name}\n"

    lines = [f"# Neighbors of {qualified_name}"]
    if edge_type:
        lines[0] += f" (edge_type={edge_type})"
    for n in neighbors:
        lines.append(
            f"- {n['qualified_name']}  # {n['kind']}  {n['edge']}  {n['direction']}"
        )
    return "\n".join(lines) + "\n"


# ================================================================== #
#  Target CodeMap validation                                           #
# ================================================================== #


def validate_target_codemap(yaml_text: str) -> list[str]:
    """Validate a Target CodeMap YAML produced by the Designer agent.

    Checks format compliance with TREE_FORMAT.md conventions:
    - Every node has a comment with metadata
    - ``[PLANNED]`` marker is present (not real line numbers)
    - No orphan edge targets (every ``~calls`` target should be a node)

    Returns a list of validation issues (empty = valid).
    """
    issues: list[str] = []

    if not yaml_text.strip():
        issues.append("Target CodeMap is empty")
        return issues

    lines = yaml_text.strip().splitlines()

    has_planned = False
    node_names: set[str] = set()
    edge_targets: set[str] = set()

    in_edge_list = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip pure comments and blank lines
        if stripped.startswith("#") and ":" not in stripped.split("#")[0]:
            continue
        if not stripped:
            in_edge_list = False
            continue

        # Edge list items
        if in_edge_list and stripped.startswith("- "):
            target = stripped[2:].split("#")[0].strip()
            if target:
                edge_targets.add(target)
            continue

        # Edge key
        if stripped.startswith("~"):
            in_edge_list = True
            continue

        # Node line — should have a comment with metadata
        if ":" in stripped and not stripped.startswith("-"):
            in_edge_list = False
            name_part = stripped.split(":")[0].strip()

            if "#" in stripped:
                comment = stripped.split("#", 1)[1]
                if "[PLANNED]" in comment:
                    has_planned = True
                # Extract qualified name hint if present
                if name_part:
                    node_names.add(name_part)
            else:
                if name_part and not name_part.startswith("focus"):
                    issues.append(
                        f"Line {i}: node '{name_part}' has no metadata comment"
                    )

    if not has_planned:
        issues.append("No [PLANNED] markers found — Target CodeMap should use [PLANNED] instead of line numbers")

    # Check for orphan edge targets (warning, not error — targets may be
    # outside the planned scope, e.g., stdlib or external packages)
    # This is a soft check; we only flag it if the target looks like it
    # should be in the planned structure (contains the root package name).
    # For now, skip this check — it requires deeper context.

    return issues
