"""Tests for IntentGraph invariant enforcement (T1, T3) and mutation methods."""

import pytest

from intentgraph.errors import (
    DuplicateLinkError,
    DuplicateNodeError,
    IntentGraphError,
    LinkInvariantViolation,
    LinkNotFoundError,
    NodeNotFoundError,
    TreeInvariantViolation,
)
from intentgraph.models.graph import IntentGraph


# ================================================================== #
#  T1 — Tree property                                                 #
# ================================================================== #


class TestT1TreeProperty:
    """Treearcs must form a directed rooted tree."""

    def test_single_root(self, tiny_graph: IntentGraph):
        roots = tiny_graph.roots()
        assert len(roots) == 1
        assert roots[0].uid == "ROOT"

    def test_every_non_root_has_one_parent(self, medium_graph: IntentGraph):
        for node in medium_graph.iter_nodes():
            if node.uid == "ROOT":
                assert node.parent_uid is None
            else:
                assert node.parent_uid is not None
                parent = medium_graph.parent(node.uid)
                assert parent is not None

    def test_attach_creates_treearc(self, empty_graph: IntentGraph):
        g = empty_graph
        g.add_node("ROOT", "Root", "Root node")
        g.add_node("C", "Child", "Child node")
        g.attach("ROOT", "C")

        assert g.parent("C").uid == "ROOT"
        assert "C" in [c.uid for c in g.children("ROOT")]

    def test_attach_duplicate_parent_raises(self, empty_graph: IntentGraph):
        g = empty_graph
        g.add_node("ROOT", "Root", "Root")
        g.add_node("P2", "Alt parent", "Alt")
        g.add_node("C", "Child", "Child")
        g.attach("ROOT", "C")

        with pytest.raises(TreeInvariantViolation, match="already has parent"):
            # Try to reparent C from ROOT to P2 (using skip_uid_validation since C's UID doesn't match P2. prefix)
            g.attach("P2", "C", skip_uid_validation=True)

    def test_attach_cycle_raises(self, empty_graph: IntentGraph):
        """Attaching a node under its own descendant must raise."""
        g = empty_graph
        g.add_node("ROOT", "Root", "Root")
        g.add_node("A", "A", "A")
        g.add_node("B", "B", "B")
        g.attach("ROOT", "A")
        # Attach B to A with skip_uid_validation since B doesn't start with A.
        g.attach("A", "B", skip_uid_validation=True)

        with pytest.raises(TreeInvariantViolation, match="cycle"):
            # Try to attach ROOT under B (its descendant) — this creates a cycle
            # Use skip_uid_validation since ROOT doesn't match B. prefix
            g.attach("B", "ROOT", skip_uid_validation=True)

    def test_attach_self_cycle_raises(self, empty_graph: IntentGraph):
        """A node cannot be its own parent."""
        g = empty_graph
        g.add_node("ROOT", "Root", "Root")
        # is_above(ROOT, ROOT) is True, so this should raise
        # Use skip_uid_validation since ROOT doesn't match ROOT. prefix (trivially)
        with pytest.raises(TreeInvariantViolation, match="cycle"):
            g.attach("ROOT", "ROOT", skip_uid_validation=True)

    def test_detach_removes_treearc(self, tiny_graph: IntentGraph):
        g = tiny_graph
        g.detach("ROOT", "A")
        assert g.parent("A") is None
        assert "A" not in [c.uid for c in g.children("ROOT")]

    def test_detach_wrong_parent_raises(self, tiny_graph: IntentGraph):
        with pytest.raises(TreeInvariantViolation, match="not a child"):
            tiny_graph.detach("A", "B")  # B is child of ROOT, not A

    def test_remove_leaf_succeeds(self, tiny_graph: IntentGraph):
        tiny_graph.remove_node("B")
        assert tiny_graph.get_node_or_none("B") is None
        assert "B" not in [c.uid for c in tiny_graph.children("ROOT")]

    def test_remove_non_leaf_without_cascade_raises(self, medium_graph: IntentGraph):
        with pytest.raises(TreeInvariantViolation, match="has children"):
            medium_graph.remove_node("E")

    def test_remove_cascade_deletes_subtree(self, medium_graph: IntentGraph):
        medium_graph.remove_node("L", cascade=True)
        for uid in ["L", "L.1", "L.2", "L.3", "L.3.1", "L.3.2"]:
            assert medium_graph.get_node_or_none(uid) is None
        # ROOT still has E and T
        assert len(medium_graph.children("ROOT")) == 2


# ================================================================== #
#  T3 — Intentlink well-formedness                                    #
# ================================================================== #


class TestT3LinkWellFormedness:

    def test_add_link_valid(self, tiny_graph: IntentGraph):
        link = tiny_graph.add_link("B", "A", "B responds to A")
        assert link.uid == "B_A"
        assert tiny_graph.link_count() == 2

    def test_add_link_nonexistent_src_raises(self, tiny_graph: IntentGraph):
        with pytest.raises(LinkInvariantViolation, match="Source node 'X'"):
            tiny_graph.add_link("X", "A", "bad link")

    def test_add_link_nonexistent_dst_raises(self, tiny_graph: IntentGraph):
        with pytest.raises(LinkInvariantViolation, match="Destination node 'X'"):
            tiny_graph.add_link("A", "X", "bad link")

    def test_add_duplicate_link_raises(self, tiny_graph: IntentGraph):
        with pytest.raises(DuplicateLinkError):
            tiny_graph.add_link("A", "B", "duplicate")

    def test_add_link_with_tag_allows_parallel(self, tiny_graph: IntentGraph):
        link = tiny_graph.add_link("A", "B", "second link", tag="v2")
        assert link.uid == "A_B#v2"
        assert tiny_graph.link_count() == 2

    def test_remove_link(self, tiny_graph: IntentGraph):
        tiny_graph.remove_link("A_B")
        assert tiny_graph.link_count() == 0

    def test_remove_nonexistent_link_raises(self, tiny_graph: IntentGraph):
        with pytest.raises(LinkNotFoundError):
            tiny_graph.remove_link("NOPE")

    def test_remove_node_cascades_links(self, tiny_graph: IntentGraph):
        """Removing a node must also remove all its intentlinks (T3 preservation)."""
        tiny_graph.remove_node("A")
        assert tiny_graph.link_count() == 0

    def test_link_descendant_rule_valid(self, medium_graph: IntentGraph):
        """Child link endpoints must be descendants of parent link endpoints."""
        # Parent link: E -> T
        medium_graph.add_link(
            "E.3", "T.1", "Refined: validated to normalized",
            tag="refined",
            parent="E_T",
        )
        assert medium_graph.link_count() == 9

    def test_link_descendant_rule_violation(self, medium_graph: IntentGraph):
        """Child link src not a descendant of parent link src should raise."""
        with pytest.raises(LinkInvariantViolation, match="not a descendant"):
            medium_graph.add_link(
                "L.1", "T.1", "Bad refinement",
                tag="bad",
                parent="E_T",  # L.1 is not under E
            )


# ================================================================== #
#  Node mutation                                                      #
# ================================================================== #


class TestNodeMutation:

    def test_add_duplicate_node_raises(self, tiny_graph: IntentGraph):
        with pytest.raises(DuplicateNodeError):
            tiny_graph.add_node("ROOT", "Dup", "Duplicate root")

    def test_get_nonexistent_raises(self, empty_graph: IntentGraph):
        with pytest.raises(NodeNotFoundError):
            empty_graph.get_node("NOPE")

    def test_update_content_fields(self, tiny_graph: IntentGraph):
        tiny_graph.update_node(
            "A",
            intent="Updated intent for A",
            epistemic_state="known",
            constraints=["Must be fast"],
        )
        node = tiny_graph.get_node("A")
        assert node.intent == "Updated intent for A"
        assert node.epistemic_state == "known"
        assert node.constraints == ["Must be fast"]

    def test_update_structural_field_raises(self, tiny_graph: IntentGraph):
        with pytest.raises(IntentGraphError, match="structural fields"):
            tiny_graph.update_node("A", parent_uid="B")


# ================================================================== #
#  Query operators                                                    #
# ================================================================== #


class TestQueryOperators:

    def test_anc(self, deep_graph: IntentGraph):
        anc = deep_graph.anc("A.1.1.1.1")
        assert anc == {"A.1.1.1", "A.1.1", "A.1", "A", "ROOT"}

    def test_desc(self, medium_graph: IntentGraph):
        desc = medium_graph.desc("L")
        assert desc == {"L.1", "L.2", "L.3", "L.3.1", "L.3.2"}

    def test_is_above_true(self, deep_graph: IntentGraph):
        assert deep_graph.is_above("ROOT", "A.1.1.1.1") is True
        assert deep_graph.is_above("A", "A.1.1") is True

    def test_is_above_self(self, deep_graph: IntentGraph):
        assert deep_graph.is_above("A.1", "A.1") is True

    def test_is_above_false(self, deep_graph: IntentGraph):
        assert deep_graph.is_above("A.1.1.1.1", "ROOT") is False

    def test_siblings(self, medium_graph: IntentGraph):
        sibs = medium_graph.siblings("T")
        sib_uids = {s.uid for s in sibs}
        assert sib_uids == {"E", "L"}

    def test_is_leaf(self, medium_graph: IntentGraph):
        assert medium_graph.is_leaf("E.1") is True
        assert medium_graph.is_leaf("E") is False

    def test_roots(self, medium_graph: IntentGraph):
        roots = medium_graph.roots()
        assert len(roots) == 1
        assert roots[0].uid == "ROOT"
