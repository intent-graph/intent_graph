"""Tests for ilink projection — rep, project_links, dominance."""

import pytest

from intentgraph.models.view import View
from intentgraph.models.graph import IntentGraph
from intentgraph.ops.projection import (
    ProjectedLink,
    project_links,
    project_links_with_dominance,
    rep,
)


class TestRep:
    """Tests for rep(V, n) — the view representative of a node."""

    def test_node_in_view(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        assert rep(f, "E") == "E"
        assert rep(f, "T") == "T"

    def test_descendant_projects_up(self, medium_graph: IntentGraph):
        """E.1 should project to E when view is {E, T, L}."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        assert rep(f, "E.1") == "E"
        assert rep(f, "E.3") == "E"
        assert rep(f, "L.3.1") == "L"

    def test_root_not_in_view(self, medium_graph: IntentGraph):
        """ROOT is above the view; rep should be None for a node above the view."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        # ROOT's parent is None, and ROOT is not in the view
        assert rep(f, "ROOT") is None

    def test_partial_view(self, medium_graph: IntentGraph):
        """Node in an uncovered subtree returns None."""
        f = View.from_node_set(medium_graph, "partial", {"E"})
        assert rep(f, "E.1") == "E"
        assert rep(f, "T.1") is None  # T subtree not in view
        assert rep(f, "L") is None

    def test_nonexistent_node(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E"})
        assert rep(f, "NOPE") is None


class TestProjectLinks:

    def test_direct_links_at_level1(self, medium_graph: IntentGraph):
        """View {E, T, L}: links E->T and T->L are directly visible."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        projected = project_links(f)

        pairs = {(pl.display_src, pl.display_dst) for pl in projected}
        assert ("E", "T") in pairs
        assert ("T", "L") in pairs

    def test_lifted_links(self, medium_graph: IntentGraph):
        """Links like E.3->T.1 should project to E->T when view is {E, T, L}."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        projected = project_links(f)

        lifted = [pl for pl in projected if pl.is_lifted]
        assert len(lifted) > 0

        # All lifted links should have display endpoints in the view
        for pl in lifted:
            assert pl.display_src in f
            assert pl.display_dst in f

    def test_self_loops_filtered(self, medium_graph: IntentGraph):
        """Links within the same subtree should be filtered as self-loops.

        T.1->T.2 at view {E, T, L} projects to T->T (self-loop, hidden).
        """
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        projected = project_links(f)

        for pl in projected:
            assert pl.display_src != pl.display_dst, (
                f"Self-loop should be filtered: {pl.display_src} -> {pl.display_dst}"
            )

    def test_no_unrepresentable(self, medium_graph: IntentGraph):
        """All projected links should have both endpoints in the view."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        projected = project_links(f)

        for pl in projected:
            assert pl.display_src in f
            assert pl.display_dst in f

    def test_finer_view_shows_more_links(self, medium_graph: IntentGraph):
        """A deeper view should surface more links (fewer self-loop collapses)."""
        f_coarse = View.from_depth(medium_graph, "d1", depth=1)
        f_fine = View.from_depth(medium_graph, "d2", depth=2)

        p_coarse = project_links(f_coarse)
        p_fine = project_links(f_fine)

        # More detailed view should show at least as many distinct links
        assert len(p_fine) >= len(p_coarse)

    def test_empty_view(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "empty", set())
        assert project_links(f) == []

    def test_deep_graph_projection(self, deep_graph: IntentGraph):
        """Link ROOT->A.1.1.1.1 at view {A} projects to nothing (ROOT not in view)."""
        f = View.from_node_set(deep_graph, "test", {"A"})
        projected = project_links(f)
        # ROOT is not in the view, so rep(F, ROOT) is None
        # The only link ROOT->A.1.1.1.1 should be unrepresentable
        assert len(projected) == 0


class TestDominance:

    def test_refined_link_suppresses_parent(self, medium_graph: IntentGraph):
        """When a child link covers the same projected endpoints, parent is suppressed."""
        g = medium_graph

        # Add a refined child link under E_T
        g.add_link(
            "E.3", "T.1", "Refined: validated to normalized",
            tag="refined_child",
            parent="E_T",
        )

        # At level 1 view, both E_T and the child project to (E, T)
        f = View.from_node_set(g, "test", {"E", "T", "L"})

        basic = project_links(f)
        with_dom = project_links_with_dominance(f)

        # Basic projection includes both parent and child
        e_t_basic = [pl for pl in basic if pl.display_src == "E" and pl.display_dst == "T"]
        assert len(e_t_basic) >= 2  # parent + at least one child

        # With dominance, the parent E_T should be suppressed
        parent_in_dom = [
            pl for pl in with_dom if pl.original.uid == "E_T"
        ]
        assert len(parent_in_dom) == 0, "Parent link E_T should be suppressed by dominance"

    def test_no_children_no_suppression(self, medium_graph: IntentGraph):
        """Links without refined children should NOT be suppressed."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})

        basic = project_links(f)
        with_dom = project_links_with_dominance(f)

        # Without any refined child links, dominance should not change anything
        assert len(with_dom) == len(basic)
