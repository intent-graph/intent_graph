"""Context assembly — prepare IntentGraph context for agent consumption.

Handles working-view serialization with budget management, tree/edge overview
generation, IV-shaped context modes, and CodeMap integration.

The core IV-context logic (target adjacency, detail-tier partitioning) lives
in ``intentgraph.ops.iv_context``; this module re-exports the constants and
adds the agent-layer concerns (budget, overview, CodeMap, CLI).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from intentgraph.models.graph import IntentGraph
from intentgraph.models.view import View
from intentgraph.ops.iv_context import (
    IV_CONTEXT_MODE_FULL,
    IV_CONTEXT_MODE_LEAN,
    _IV_CONTEXT_MODES,
    _validate_iv_context_mode,
    build_iv_context_profile,
    target_neighbor_uids,
)
from intentgraph.serial.agent_text import view_to_text
from intentgraph.serial.graph_overview import (
    graph_to_edge_overview,
    graph_to_tree_overview,
    view_text_size,
)
from intentgraph.serial.json_yaml import load_graph

from ig_agents.codemap_bridge import codemap_available, overview_for_context

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
direct_target_neighbor_uids = target_neighbor_uids


# ================================================================== #
#  Context budget                                                      #
# ================================================================== #

DEFAULT_WORD_BUDGET = 4000  # conservative default for agent context


def check_view_budget(
    view: View,
    word_budget: int = DEFAULT_WORD_BUDGET,
    *,
    target_uid: str | None = None,
    iv_context_mode: str = IV_CONTEXT_MODE_FULL,
) -> dict[str, Any]:
    """Check whether a working view fits within the word budget.

    Returns a dict with:
    - ``within_budget``: bool
    - ``size``: {chars, words, lines}
    - ``budget``: the word budget used
    - ``recommendation``: str (if over budget, suggests IV-shaped context)
    """
    _validate_iv_context_mode(iv_context_mode)

    lean_node_uids: set[str] | None = None
    if iv_context_mode == IV_CONTEXT_MODE_LEAN:
        if target_uid is None:
            raise ValueError(
                "target_uid is required when iv_context_mode='lean'"
            )
        profile = build_iv_context_profile(
            view.graph,
            view,
            target_uid=target_uid,
            iv_context_mode=iv_context_mode,
        )
        lean_node_uids = set(profile["lean_detail_uids"])

    text = view_to_text(view, lean_node_uids=lean_node_uids)
    size = view_text_size(text)

    within = size["words"] <= word_budget
    result: dict[str, Any] = {
        "within_budget": within,
        "size": size,
        "budget": word_budget,
    }

    if not within:
        mode_hint = (
            "lean IV-context"
            if iv_context_mode == IV_CONTEXT_MODE_LEAN
            else "full IV-context"
        )
        result["recommendation"] = (
            f"View has {size['words']} words (budget: {word_budget}). "
            f"Use {mode_hint}: keep target and direct neighbors at full detail, "
            f"and collapse other view nodes to lean fields "
            f"(uid/name/intent/epistemic_state). Consider using the Navigator agent."
        )

    return result


# ================================================================== #
#  Full context assembly                                               #
# ================================================================== #


def assemble_agent_context(
    graph: IntentGraph,
    view: View,
    *,
    target_uid: str | None = None,
    iv_context_mode: str = IV_CONTEXT_MODE_FULL,
    include_overview: bool = False,
    style_path: Path | str | None = None,
    codemap_project_path: Path | str | None = None,
    target_codemap_text: str | None = None,
    word_budget: int = DEFAULT_WORD_BUDGET,
) -> dict[str, Any]:
    """Assemble the full context payload for an agent invocation.

    Returns a dict with all the text pieces an agent needs:
    - ``view_text``: serialized working-view YAML (§2 agent text)
    - ``budget_check``: result of check_view_budget
    - ``iv_context``: computed detail tiers for IV-shaped context (if target provided)
    - ``tree_overview``: (optional) compact tree hierarchy
    - ``edge_overview``: (optional) compact intentlink list
    - ``style_text``: (optional) style directives content
    - ``codemap_overview``: (optional) CodeMap structural overview YAML
    - ``target_codemap``: (optional) Target CodeMap YAML from Designer
    """
    _validate_iv_context_mode(iv_context_mode)

    iv_context: dict[str, Any] | None = None
    lean_node_uids: set[str] | None = None
    if target_uid is not None:
        iv_context = build_iv_context_profile(
            graph,
            view,
            target_uid=target_uid,
            iv_context_mode=iv_context_mode,
        )
        lean_node_uids = set(iv_context["lean_detail_uids"])
    elif iv_context_mode == IV_CONTEXT_MODE_LEAN:
        raise ValueError("target_uid is required when iv_context_mode='lean'")

    view_text = view_to_text(view, lean_node_uids=lean_node_uids)
    budget = check_view_budget(
        view,
        word_budget,
        target_uid=target_uid,
        iv_context_mode=iv_context_mode,
    )

    result: dict[str, Any] = {
        "view_text": view_text,
        "budget_check": budget,
    }
    if iv_context is not None:
        result["iv_context"] = iv_context

    if include_overview:
        result["tree_overview"] = graph_to_tree_overview(graph)
        result["edge_overview"] = graph_to_edge_overview(graph)

    if style_path:
        p = Path(style_path)
        if p.exists():
            result["style_text"] = p.read_text(encoding="utf-8")

    if codemap_project_path:
        result["codemap_overview"] = overview_for_context(codemap_project_path)

    if target_codemap_text:
        result["target_codemap"] = target_codemap_text

    return result


def assemble_designer_context(
    graph: IntentGraph,
    view: View,
    *,
    target_uid: str | None = None,
    iv_context_mode: str = IV_CONTEXT_MODE_FULL,
    projection_ig_path: Path | str | None = None,
    codemap_project_path: Path | str | None = None,
    word_budget: int = DEFAULT_WORD_BUDGET,
) -> dict[str, Any]:
    """Assemble context specifically for the Designer agent.

    The Designer needs:
    - ``view_text``: product working-view YAML (what to build)
    - ``budget_check``: budget check result
    - ``iv_context``: computed detail tiers for IV-shaped context (if target provided)
    - ``projection_text``: (optional) ProjectionIG view YAML (rendering preferences)
    - ``codemap_overview``: (optional) existing codebase structural overview
    """
    _validate_iv_context_mode(iv_context_mode)

    iv_context: dict[str, Any] | None = None
    lean_node_uids: set[str] | None = None
    if target_uid is not None:
        iv_context = build_iv_context_profile(
            graph,
            view,
            target_uid=target_uid,
            iv_context_mode=iv_context_mode,
        )
        lean_node_uids = set(iv_context["lean_detail_uids"])
    elif iv_context_mode == IV_CONTEXT_MODE_LEAN:
        raise ValueError("target_uid is required when iv_context_mode='lean'")

    view_text = view_to_text(view, lean_node_uids=lean_node_uids)
    budget = check_view_budget(
        view,
        word_budget,
        target_uid=target_uid,
        iv_context_mode=iv_context_mode,
    )

    result: dict[str, Any] = {
        "view_text": view_text,
        "budget_check": budget,
    }
    if iv_context is not None:
        result["iv_context"] = iv_context

    if projection_ig_path:
        p = Path(projection_ig_path)
        if p.exists():
            result["projection_text"] = p.read_text(encoding="utf-8")
        else:
            logger.warning("ProjectionIG path does not exist: %s", p)

    if codemap_project_path:
        if codemap_available():
            result["codemap_overview"] = overview_for_context(codemap_project_path)
        else:
            logger.info("codemap not installed — no structural context for Designer")

    return result


# ================================================================== #
#  View selection (shared with the CLI)                                 #
# ================================================================== #


def build_working_view(
    graph: IntentGraph,
    *,
    node_uids: set[str] | frozenset[str] | None = None,
    depth: int | None = None,
    name: str = "working-view",
) -> View:
    """Build a working view from an explicit node set or a uniform depth cut.

    Exactly one of ``node_uids`` / ``depth`` must be provided.
    """
    if (node_uids is None) == (depth is None):
        raise ValueError("provide exactly one of node_uids or depth")
    if node_uids is not None:
        return View.from_node_set(graph, name, set(node_uids))
    return View.from_depth(graph, name, depth)


# ================================================================== #
#  CLI entry point                                                     #
# ================================================================== #


def main() -> None:
    """CLI: assemble full or lean IV-context from a working view."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Assemble agent context from IntentGraph")
    parser.add_argument("--graph", required=True, help="Path to graph file (JSON or YAML)")
    parser.add_argument("--nodes", default=None,
                        help="Comma-separated node UIDs forming the working view")
    parser.add_argument("--depth", type=int, default=None,
                        help="Build the working view as a uniform depth cut (0 = root)")
    parser.add_argument("--name", default="working-view", help="Name for the working view")
    parser.add_argument("--budget", type=int, default=DEFAULT_WORD_BUDGET, help="Word budget")
    parser.add_argument("--overview", action="store_true", help="Include tree/edge overview")
    parser.add_argument("--style", default=None, help="Path to style directives markdown")
    parser.add_argument("--target", default=None, help="Target UID used to compute IV-context tiers")
    parser.add_argument(
        "--iv-context-mode",
        default=IV_CONTEXT_MODE_FULL,
        choices=sorted(_IV_CONTEXT_MODES),
        help="IV-context mode: full (all full detail) or lean (non-neighbors lean)",
    )
    args = parser.parse_args()

    graph = load_graph(args.graph)

    try:
        view = build_working_view(
            graph,
            node_uids=(
                {u.strip() for u in args.nodes.split(",") if u.strip()}
                if args.nodes else None
            ),
            depth=args.depth,
            name=args.name,
        )
    except ValueError as e:
        print(f"error: {e} (pass --nodes UID,UID,... or --depth N)", file=sys.stderr)
        sys.exit(1)

    ctx = assemble_agent_context(
        graph, view,
        target_uid=args.target,
        iv_context_mode=args.iv_context_mode,
        include_overview=args.overview,
        style_path=args.style,
        word_budget=args.budget,
    )

    # Output view text to stdout, budget info to stderr
    print(ctx["view_text"])
    budget = ctx["budget_check"]
    print(f"\n--- Budget: {budget['size']['words']}/{budget['budget']} words "
          f"({'OK' if budget['within_budget'] else 'OVER'})", file=sys.stderr)

    if "recommendation" in budget:
        print(f"--- {budget['recommendation']}", file=sys.stderr)


if __name__ == "__main__":
    main()
