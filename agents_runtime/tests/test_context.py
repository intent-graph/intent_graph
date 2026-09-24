"""Tests for context assembly and budget management."""

import pytest
import yaml

from intentgraph.models.view import View
from intentgraph.models.graph import IntentGraph

from ig_agents.context import (
    IV_CONTEXT_MODE_FULL,
    IV_CONTEXT_MODE_LEAN,
    assemble_agent_context,
    build_iv_context_profile,
    check_view_budget,
)


class TestCheckViewBudget:

    def test_within_budget(self, sample_view: View):
        result = check_view_budget(sample_view, word_budget=10000)
        assert result["within_budget"] is True
        assert result["size"]["words"] > 0
        assert "recommendation" not in result

    def test_over_budget(self, sample_view: View):
        result = check_view_budget(sample_view, word_budget=1)
        assert result["within_budget"] is False
        assert "recommendation" in result
        assert "IV-context" in result["recommendation"]

    def test_lean_mode_requires_target(self, sample_view: View):
        with pytest.raises(ValueError, match="target_uid is required"):
            check_view_budget(
                sample_view,
                word_budget=1,
                iv_context_mode=IV_CONTEXT_MODE_LEAN,
            )


class TestBuildIvContextProfile:

    def test_full_mode_keeps_all_nodes_full(
        self,
        sample_graph: IntentGraph,
        sample_view: View,
    ):
        profile = build_iv_context_profile(
            sample_graph,
            sample_view,
            target_uid="E",
            iv_context_mode=IV_CONTEXT_MODE_FULL,
        )
        assert set(profile["full_detail_uids"]) == {"E", "T", "L"}
        assert profile["lean_detail_uids"] == []

    def test_lean_mode_only_target_and_direct_neighbors_are_full(
        self,
        sample_graph: IntentGraph,
        sample_view: View,
    ):
        profile = build_iv_context_profile(
            sample_graph,
            sample_view,
            target_uid="E",
            iv_context_mode=IV_CONTEXT_MODE_LEAN,
        )
        assert set(profile["direct_neighbor_uids"]) == {"T"}
        assert set(profile["full_detail_uids"]) == {"E", "T"}
        assert set(profile["lean_detail_uids"]) == {"L"}


class TestAssembleAgentContext:

    def test_basic_assembly(self, sample_graph: IntentGraph, sample_view: View):
        ctx = assemble_agent_context(sample_graph, sample_view)
        assert "view_text" in ctx
        assert "budget_check" in ctx
        assert ctx["budget_check"]["within_budget"] is True

    def test_with_overview(self, sample_graph: IntentGraph, sample_view: View):
        ctx = assemble_agent_context(sample_graph, sample_view, include_overview=True)
        assert "tree_overview" in ctx
        assert "edge_overview" in ctx
        assert "ROOT" in ctx["tree_overview"]
        assert "E" in ctx["edge_overview"]

    def test_without_overview(self, sample_graph: IntentGraph, sample_view: View):
        ctx = assemble_agent_context(sample_graph, sample_view, include_overview=False)
        assert "tree_overview" not in ctx
        assert "edge_overview" not in ctx

    def test_with_nonexistent_style(self, sample_graph: IntentGraph, sample_view: View):
        ctx = assemble_agent_context(
            sample_graph, sample_view,
            style_path="/nonexistent/style.md",
        )
        assert "style_text" not in ctx

    def test_with_lean_iv_context(self, sample_graph: IntentGraph, sample_view: View):
        sample_graph.update_node(
            "L",
            constraints=["Do not block writes"],
            design_notes="Non-neighbor context detail should be dropped in lean mode.",
        )
        sample_graph.update_node(
            "E",
            constraints=["Neighbor detail is retained in lean mode."],
        )

        ctx = assemble_agent_context(
            sample_graph,
            sample_view,
            target_uid="E",
            iv_context_mode=IV_CONTEXT_MODE_LEAN,
        )

        doc = yaml.safe_load(ctx["view_text"])
        nodes = {n["uid"]: n for n in doc["nodes"]}

        # target and direct neighbor stay full detail
        assert "constraints" in nodes["E"]
        assert "collapsed_children" in nodes["E"]
        assert "intent" in nodes["T"]

        # non-neighbor node is lean
        assert set(nodes["L"].keys()) <= {"uid", "name", "intent", "epistemic_state"}
        assert "constraints" not in nodes["L"]
        assert "design_notes" not in nodes["L"]
        assert "collapsed_children" not in nodes["L"]
