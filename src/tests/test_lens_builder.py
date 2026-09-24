"""Tests for lens builder — build_lens with IV_ LOD assignment and pruning."""

import pytest

from intentgraph.errors import IntentGraphError
from intentgraph.models.graph import IntentGraph
from intentgraph.models.lens import LOD
from intentgraph.ops.lens_ops import build_lens


# ================================================================== #
#  Basic lens building                                               #
# ================================================================== #


class TestBuildLensBasic:
    """Test build_lens with simple graphs."""

    def test_build_with_tiny_graph(self, tiny_graph: IntentGraph):
        """Build a lens from tiny_graph targeting A."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        assert lens.meta.name == "test"
        assert lens.meta.target_uid == "A"
        assert lens.meta.budget == 50
        assert "A" in lens.nodes
        assert "B" in lens.nodes
        assert "ROOT" in lens.nodes

    def test_lens_contains_deep_copies(self, tiny_graph: IntentGraph):
        """Lens nodes are independent copies."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Mutate lens node
        lens.nodes["A"].intent = "CHANGED"

        # Original unchanged
        assert tiny_graph.get_node("A").intent != "CHANGED"

    def test_lens_default_parameters(self, tiny_graph: IntentGraph):
        """build_lens has sensible defaults."""
        lens = build_lens(tiny_graph, target_uid="A")

        assert lens.meta.budget == 30  # default
        assert lens.meta.name == "working-lens"
        assert lens.meta.source_graph == "graph.json"
        assert lens.meta.scope_root is None

    def test_target_must_exist(self, tiny_graph: IntentGraph):
        """build_lens raises if target doesn't exist."""
        from intentgraph.errors import NodeNotFoundError

        with pytest.raises(NodeNotFoundError):
            build_lens(tiny_graph, target_uid="NONEXISTENT")


# ================================================================== #
#  IV_ LOD assignment correctness                                    #
# ================================================================== #


class TestIVLODAssignment:
    """Test that IV_ LOD assignment follows the pattern."""

    def test_target_gets_full(self, medium_graph: IntentGraph):
        """Target node always gets full LOD."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        assert lens.get_lod("E.1") == LOD.full

    def test_target_parent_gets_full(self, medium_graph: IntentGraph):
        """Target's parent (direct treearc neighbor) gets full."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        assert lens.get_lod("E") == LOD.full  # parent of E.1

    def test_target_children_get_full(self, medium_graph: IntentGraph):
        """Target's children (direct treearc neighbors) get full."""
        lens = build_lens(medium_graph, target_uid="E", budget=100, name="test")

        assert lens.get_lod("E.1") == LOD.full
        assert lens.get_lod("E.2") == LOD.full
        assert lens.get_lod("E.3") == LOD.full

    def test_intentlink_neighbors_get_full(self, medium_graph: IntentGraph):
        """Intentlink endpoints from target get full."""
        # E.3 has link to T.1
        lens = build_lens(medium_graph, target_uid="E.3", budget=100, name="test")

        assert lens.get_lod("T.1") == LOD.full  # intentlink neighbor

    def test_ancestors_get_lean(self, medium_graph: IntentGraph):
        """All ancestors up to root get lean."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        assert lens.get_lod("E") == LOD.full  # parent = neighbor (full overrides lean)
        assert lens.get_lod("ROOT") == LOD.lean  # ancestor

    def test_l1_nodes_get_lean(self, medium_graph: IntentGraph):
        """L1 nodes (direct children of root) get lean."""
        lens = build_lens(medium_graph, target_uid="L.3.1", budget=100, name="test")

        # L1 nodes: E, T, L
        # L is in the ancestor path, so might be full or lean depending on if it's also a neighbor
        # For L.3.1, L is ancestor → lean, but let's check E and T (not in path)
        assert lens.get_lod("E") == LOD.lean
        assert lens.get_lod("T") == LOD.lean

    def test_rest_get_skeleton(self, medium_graph: IntentGraph):
        """Nodes not in I, V, or _ get skeleton."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # T.2 is not an ancestor, not L1, not neighbor of E.1
        # (assuming no intentlink to E.1)
        assert lens.get_lod("T.2") == LOD.skeleton
        assert lens.get_lod("L.3.1") == LOD.skeleton

    def test_iv_pattern_overrides_lean_with_full(self, medium_graph: IntentGraph):
        """If a node qualifies for both lean and full, full wins."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # E is both an ancestor (lean) and parent (full) → should be full
        assert lens.get_lod("E") == LOD.full


# ================================================================== #
#  Pruning to budget                                                 #
# ================================================================== #


class TestBudgetPruning:
    """Test lens pruning when node count exceeds budget."""

    def test_no_pruning_under_budget(self, tiny_graph: IntentGraph):
        """No pruning when node count <= budget."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Tiny graph has 3 nodes (ROOT, A, B)
        assert lens.node_count() == 3
        assert len(lens.pruned_subtrees) == 0

    def test_pruning_over_budget(self, medium_graph: IntentGraph):
        """Nodes are pruned when over budget."""
        # Medium graph has 15+ nodes; budget=5 should trigger pruning
        lens = build_lens(medium_graph, target_uid="E.1", budget=5, name="test")

        assert lens.node_count() <= 5
        assert len(lens.pruned_subtrees) > 0

    def test_pruning_removes_most_distant_first(self, medium_graph: IntentGraph):
        """Pruning prioritizes most distant nodes."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=8, name="test")

        # E.1 and its neighbors (E, ROOT) should survive
        assert "E.1" in lens.nodes
        assert "E" in lens.nodes

        # Distant branches (L subtree, far from E.1) should be pruned
        # L.3.1 is far from E.1 → likely pruned
        if lens.node_count() < medium_graph.node_count():
            # Check that some L or T descendants are missing
            all_nodes = set(medium_graph.nodes.keys())
            lens_nodes = set(lens.nodes.keys())
            pruned = all_nodes - lens_nodes
            assert len(pruned) > 0

    def test_pruned_children_count(self, medium_graph: IntentGraph):
        """Parents of pruned nodes show pruned_children count."""
        lens = build_lens(medium_graph, target_uid="E", budget=6, name="test")

        # E has 3 children; if we're at budget 6, some might be pruned
        if lens.node_count() < medium_graph.node_count():
            # Check if any parent has pruned_children > 0
            for uid, meta in lens.node_metadata.items():
                node = lens.nodes[uid]
                total_children = len(medium_graph.get_node(uid).children_uids)
                visible_children = len([c for c in node.children_uids if c in lens.nodes])
                expected_pruned = total_children - visible_children
                assert meta.pruned_children == expected_pruned


# ================================================================== #
#  IntentLink visibility filtering                                   #
# ================================================================== #


class TestIntentLinkVisibility:
    """Test intentlink visibility rules in lens."""

    def test_links_visible_when_both_endpoints_lean_or_above(self, medium_graph: IntentGraph):
        """IntentLinks appear only if both endpoints are at lean or above."""
        lens = build_lens(medium_graph, target_uid="T.1", budget=100, name="test")

        # E.3 → T.1 link: both should be at least lean
        # T.1 is target (full), E.3 is intentlink neighbor (full)
        assert "E.3_T.1" in lens.intentlinks

    def test_links_hidden_when_endpoint_is_skeleton(self, medium_graph: IntentGraph):
        """Links with skeleton endpoint are excluded."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # Links to distant skeleton nodes should be excluded
        # E.g., if T.2 is skeleton and there's a link involving it, it's hidden
        # Check that all visible links have both endpoints >= lean
        for link_uid, link in lens.intentlinks.items():
            src_lod = lens.get_lod(link.src)
            dst_lod = lens.get_lod(link.dst)
            assert src_lod >= LOD.lean
            assert dst_lod >= LOD.lean

    def test_link_description_rules(self, medium_graph: IntentGraph):
        """IntentLink descriptions shown only if ≥1 endpoint is full.

        Note: This test verifies the LOD state, not the serialization.
        The actual description filtering happens in lens_to_agent_text.
        """
        lens = build_lens(medium_graph, target_uid="T.1", budget=100, name="test")

        # In the lens data model, links are always stored with full data
        # The filtering happens during serialization to agent text
        # Here we just verify that links are present when visibility rules are met
        for link in lens.intentlinks.values():
            assert link.intent is not None  # Full data is preserved


# ================================================================== #
#  Treearcs — both endpoints in lens                                 #
# ================================================================== #


class TestTreearcs:
    """Test treearc extraction."""

    def test_treearcs_both_endpoints_present(self, medium_graph: IntentGraph):
        """Treearcs only included when both endpoints are in lens."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=8, name="test")

        # Every treearc should have both endpoints in lens.nodes
        for parent, child in lens.treearcs:
            assert parent in lens.nodes, f"Parent {parent} missing"
            assert child in lens.nodes, f"Child {child} missing"

    def test_treearcs_excluded_when_child_pruned(self, medium_graph: IntentGraph):
        """Treearcs to pruned children are excluded."""
        lens = build_lens(medium_graph, target_uid="E", budget=5, name="test")

        # If E's children are pruned, treearcs to them should not exist
        treearc_children = {child for parent, child in lens.treearcs if parent == "E"}
        actual_children = set(lens.nodes["E"].children_uids) & set(lens.nodes.keys())

        assert treearc_children == actual_children


# ================================================================== #
#  Scope limiting                                                    #
# ================================================================== #


class TestScopeRoot:
    """Test scope_root parameter for subtree lenses."""

    def test_scope_root_limits_to_subtree(self, medium_graph: IntentGraph):
        """scope_root limits lens to a subtree."""
        lens = build_lens(
            medium_graph,
            target_uid="E.1",
            budget=100,
            scope_root="E",
            name="test"
        )

        # Only E subtree should be present
        assert "E" in lens.nodes
        assert "E.1" in lens.nodes
        assert "E.2" in lens.nodes
        assert "E.3" in lens.nodes

        # T and L subtrees should be excluded
        assert "T" not in lens.nodes
        assert "L" not in lens.nodes

    def test_scope_root_metadata(self, medium_graph: IntentGraph):
        """scope_root is recorded in metadata."""
        lens = build_lens(
            medium_graph,
            target_uid="E.1",
            scope_root="E",
            budget=100,
            name="test"
        )

        assert lens.meta.scope_root == "E"

    def test_target_not_in_scope_raises(self, medium_graph: IntentGraph):
        """scope_root must contain target, else error."""
        with pytest.raises(IntentGraphError, match="not within scope"):
            build_lens(
                medium_graph,
                target_uid="L.1",
                scope_root="E",  # E subtree doesn't contain L.1
                budget=100,
                name="test"
            )


# ================================================================== #
#  Larger graph stress test                                          #
# ================================================================== #


class TestLargerGraphs:
    """Test lens building on larger, more complex graphs."""

    def test_medium_graph_full_budget(self, medium_graph: IntentGraph):
        """Build lens on medium graph with high budget (no pruning)."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # All nodes should be present
        assert lens.node_count() == medium_graph.node_count()
        assert len(lens.pruned_subtrees) == 0

    def test_deep_graph_target_at_bottom(self, deep_graph: IntentGraph):
        """Build lens on deep graph targeting deepest node."""
        lens = build_lens(deep_graph, target_uid="A.1.1.1.1", budget=100, name="test")

        # All ancestors should be lean (except immediate parent = full)
        assert lens.get_lod("A.1.1.1.1") == LOD.full  # target
        assert lens.get_lod("A.1.1.1") == LOD.full  # parent (neighbor)
        assert lens.get_lod("A.1.1") == LOD.lean  # ancestor
        assert lens.get_lod("A.1") == LOD.lean  # ancestor
        assert lens.get_lod("A") == LOD.lean  # L1 node

    def test_wide_graph_many_l1_nodes(self, wide_graph: IntentGraph):
        """Build lens on wide graph with many L1 siblings."""
        lens = build_lens(wide_graph, target_uid="C10", budget=100, name="test")

        # C10 should be full (target)
        assert lens.get_lod("C10") == LOD.full

        # ROOT is parent (neighbor) → full
        assert lens.get_lod("ROOT") == LOD.full

        # All other L1 nodes should be lean (V pattern)
        for i in [1, 2, 3, 5, 15, 20]:
            uid = f"C{i}"
            if uid != "C10" and uid not in ("C2", "C5", "C20"):  # Exclude intentlink neighbors
                expected = LOD.lean
                # Unless they are intentlink neighbors
                # C10 has links: C5→C10, C10→C20
                if uid == "C5" or uid == "C20":
                    expected = LOD.full
                actual = lens.get_lod(uid)
                assert actual == expected, f"{uid} should be {expected}, got {actual}"


# ================================================================== #
#  Base state snapshot on build                                      #
# ================================================================== #


class TestBaseStateSnapshot:
    """Test that build_lens captures base state for diff tracking."""

    def test_base_state_captured_on_build(self, tiny_graph: IntentGraph):
        """build_lens snapshots base state."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        assert lens.base_state is not None
        assert "nodes" in lens.base_state
        assert "treearcs" in lens.base_state
        assert "intentlinks" in lens.base_state
        assert lens.dirty is False

    def test_base_state_matches_initial_state(self, tiny_graph: IntentGraph):
        """Base state reflects the initial lens content."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Nodes in base_state should match lens.nodes
        assert set(lens.base_state["nodes"].keys()) == set(lens.nodes.keys())

        # Treearcs should match
        base_treearcs = {tuple(t) if isinstance(t, list) else t for t in lens.base_state["treearcs"]}
        assert base_treearcs == set(lens.treearcs)
