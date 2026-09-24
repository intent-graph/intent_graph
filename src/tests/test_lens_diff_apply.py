"""Tests for lens diff and apply — compute_diff, apply_diff, discard_changes."""

import pytest

from intentgraph.errors import IntentGraphError
from intentgraph.models.graph import IntentGraph
from intentgraph.models.link import IntentLink
from intentgraph.ops.lens_ops import (
    build_lens,
    compute_diff,
    apply_diff,
    discard_changes,
)


# ================================================================== #
#  compute_diff — no changes                                         #
# ================================================================== #


class TestComputeDiffNoChanges:
    """Test compute_diff when lens is unmodified."""

    def test_no_changes_empty_diff(self, tiny_graph: IntentGraph):
        """Unmodified lens produces empty diff."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        diff = compute_diff(lens)

        assert diff["nodes_created"] == []
        assert diff["nodes_modified"] == []
        assert diff["nodes_deleted"] == []
        assert diff["links_created"] == []
        assert diff["links_modified"] == []
        assert diff["links_deleted"] == []
        assert diff["treearcs_modified"] == []

    def test_no_base_state_treats_all_as_created(self, tiny_graph: IntentGraph):
        """Lens without base_state treats all as created."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Clear base state
        lens.base_state = None

        diff = compute_diff(lens)

        # All nodes should be in nodes_created
        assert len(diff["nodes_created"]) == lens.node_count()
        assert any(n["uid"] == "A" for n in diff["nodes_created"])


# ================================================================== #
#  compute_diff — node modifications                                 #
# ================================================================== #


class TestComputeDiffNodeModifications:
    """Test compute_diff detects node changes."""

    def test_node_intent_modified(self, tiny_graph: IntentGraph):
        """Modifying node.intent is detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        lens.nodes["A"].intent = "New intent for A"

        diff = compute_diff(lens)

        modifications = [m for m in diff["nodes_modified"] if m["uid"] == "A"]
        assert len(modifications) > 0
        intent_mod = next((m for m in modifications if m["field"] == "intent"), None)
        assert intent_mod is not None
        assert intent_mod["new_value"] == "New intent for A"

    def test_node_name_modified(self, tiny_graph: IntentGraph):
        """Modifying node.name is detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        lens.nodes["A"].name = "Renamed Module A"

        diff = compute_diff(lens)

        modifications = [m for m in diff["nodes_modified"] if m["uid"] == "A" and m["field"] == "name"]
        assert len(modifications) == 1
        assert modifications[0]["new_value"] == "Renamed Module A"

    def test_node_constraints_modified(self, tiny_graph: IntentGraph):
        """Modifying node.constraints is detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        lens.nodes["A"].constraints = ["Must be idempotent"]

        diff = compute_diff(lens)

        modifications = [m for m in diff["nodes_modified"] if m["uid"] == "A" and m["field"] == "constraints"]
        assert len(modifications) == 1
        assert modifications[0]["new_value"] == ["Must be idempotent"]

    def test_multiple_fields_modified(self, tiny_graph: IntentGraph):
        """Multiple field changes on same node are all detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        lens.nodes["A"].intent = "Changed intent"
        lens.nodes["A"].name = "Changed name"
        lens.nodes["A"].design_notes = "New design notes"

        diff = compute_diff(lens)

        a_mods = [m for m in diff["nodes_modified"] if m["uid"] == "A"]
        fields_modified = {m["field"] for m in a_mods}

        assert "intent" in fields_modified
        assert "name" in fields_modified
        assert "design_notes" in fields_modified


# ================================================================== #
#  compute_diff — node create/delete                                 #
# ================================================================== #


class TestComputeDiffNodeCreateDelete:
    """Test compute_diff detects node additions and removals."""

    def test_node_deletion_detected(self, tiny_graph: IntentGraph):
        """Removing a node from lens is detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Remove node B from lens
        del lens.nodes["B"]

        diff = compute_diff(lens)

        deletions = [d for d in diff["nodes_deleted"] if d["uid"] == "B"]
        assert len(deletions) == 1

    def test_node_creation_detected(self, tiny_graph: IntentGraph):
        """Adding a new node to lens is detected."""
        from intentgraph.models.node import IntentNode

        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Add a new node
        new_node = IntentNode(uid="C", name="Module C", intent="Does C")
        new_node.parent_uid = "ROOT"
        lens.nodes["C"] = new_node

        diff = compute_diff(lens)

        creations = [c for c in diff["nodes_created"] if c["uid"] == "C"]
        assert len(creations) == 1
        assert creations[0]["name"] == "Module C"
        assert creations[0]["parent"] == "ROOT"


# ================================================================== #
#  compute_diff — link modifications                                 #
# ================================================================== #


class TestComputeDiffLinkModifications:
    """Test compute_diff detects intentlink changes."""

    def test_link_intent_modified(self, tiny_graph: IntentGraph):
        """Modifying link.intent is detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Tiny graph has A_B link
        link_uid = "A_B"
        if link_uid in lens.intentlinks:
            lens.intentlinks[link_uid].intent = "Modified link intent"

            diff = compute_diff(lens)

            modifications = [m for m in diff["links_modified"] if m["uid"] == link_uid]
            intent_mod = next((m for m in modifications if m["field"] == "intent"), None)
            assert intent_mod is not None
            assert intent_mod["new_value"] == "Modified link intent"

    def test_link_shape_modified(self, tiny_graph: IntentGraph):
        """Modifying link.shape is detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        link_uid = "A_B"
        if link_uid in lens.intentlinks:
            lens.intentlinks[link_uid].shape = {"type": "depends_on", "strength": "strong"}

            diff = compute_diff(lens)

            modifications = [m for m in diff["links_modified"] if m["uid"] == link_uid and m["field"] == "shape"]
            assert len(modifications) == 1
            assert modifications[0]["new_value"] == {"type": "depends_on", "strength": "strong"}


# ================================================================== #
#  compute_diff — link create/delete                                 #
# ================================================================== #


class TestComputeDiffLinkCreateDelete:
    """Test compute_diff detects link additions and removals."""

    def test_link_deletion_detected(self, tiny_graph: IntentGraph):
        """Removing a link from lens is detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        link_uid = "A_B"
        if link_uid in lens.intentlinks:
            del lens.intentlinks[link_uid]

            diff = compute_diff(lens)

            deletions = [d for d in diff["links_deleted"] if d["uid"] == link_uid]
            assert len(deletions) == 1

    def test_link_creation_detected(self, tiny_graph: IntentGraph):
        """Adding a new link to lens is detected."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Add a new link
        new_link = IntentLink(uid="B_A", src="B", dst="A", intent="Reverse link")
        lens.intentlinks["B_A"] = new_link

        diff = compute_diff(lens)

        creations = [c for c in diff["links_created"] if c["uid"] == "B_A"]
        assert len(creations) == 1
        assert creations[0]["src"] == "B"
        assert creations[0]["dst"] == "A"


# ================================================================== #
#  compute_diff — reparenting (treearc changes)                      #
# ================================================================== #


class TestComputeDiffReparenting:
    """Test compute_diff detects treearc modifications (reparenting)."""

    def test_reparenting_detected(self, medium_graph: IntentGraph):
        """Changing a node's parent is detected."""
        lens = build_lens(medium_graph, target_uid="ROOT", budget=100, name="test")

        # Move E.1 from E to T (reparenting)
        e1_node = lens.nodes["E.1"]
        e_node = lens.nodes["E"]

        # Remove from E's children
        e_node.children_uids = [c for c in e_node.children_uids if c != "E.1"]

        # Set new parent
        e1_node.parent_uid = "T"
        lens.nodes["T"].children_uids.append("E.1")

        # Update treearcs
        lens.treearcs = [(p, c) for p, c in lens.treearcs if not (p == "E" and c == "E.1")]
        lens.treearcs.append(("T", "E.1"))

        diff = compute_diff(lens)

        reparentings = [r for r in diff["treearcs_modified"] if r["child_uid"] == "E.1"]
        assert len(reparentings) == 1
        assert reparentings[0]["old_parent"] == "E"
        assert reparentings[0]["new_parent"] == "T"


# ================================================================== #
#  apply_diff to graph                                               #
# ================================================================== #


class TestApplyDiff:
    """Test apply_diff writes changes back to source graph."""

    def test_apply_node_modification(self, tiny_graph: IntentGraph):
        """apply_diff updates node in graph."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        lens.nodes["A"].intent = "Modified intent"

        log = apply_diff(lens, tiny_graph)

        # Check that graph was updated
        assert tiny_graph.get_node("A").intent == "Modified intent"
        assert any("Modified node 'A'" in msg for msg in log)

    def test_apply_node_creation(self, tiny_graph: IntentGraph):
        """apply_diff adds new node to graph."""
        from intentgraph.models.node import IntentNode

        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        new_node = IntentNode(uid="C", name="Module C", intent="Does C")
        new_node.parent_uid = "ROOT"
        lens.nodes["C"] = new_node

        log = apply_diff(lens, tiny_graph)

        # Check that node was added to graph
        assert "C" in tiny_graph.nodes
        assert tiny_graph.get_node("C").name == "Module C"
        assert any("Created node 'C'" in msg for msg in log)

    def test_apply_node_deletion(self, tiny_graph: IntentGraph):
        """apply_diff removes node from graph."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        del lens.nodes["B"]

        log = apply_diff(lens, tiny_graph)

        # Check that node was removed from graph
        assert "B" not in tiny_graph.nodes
        assert any("Deleted node 'B'" in msg for msg in log)

    def test_apply_link_modification(self, tiny_graph: IntentGraph):
        """apply_diff updates link in graph."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        link_uid = "A_B"
        if link_uid in lens.intentlinks:
            lens.intentlinks[link_uid].intent = "Updated link intent"

            log = apply_diff(lens, tiny_graph)

            # Check that link was updated
            graph_link = tiny_graph.get_link(link_uid)
            assert graph_link.intent == "Updated link intent"
            assert any(f"Modified link '{link_uid}'" in msg for msg in log)

    def test_apply_link_creation(self, tiny_graph: IntentGraph):
        """apply_diff adds new link to graph."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        new_link = IntentLink(uid="B_A", src="B", dst="A", intent="Reverse link")
        lens.intentlinks["B_A"] = new_link

        log = apply_diff(lens, tiny_graph)

        # Check that link was added
        assert "B_A" in tiny_graph.links
        assert any("Created link 'B' → 'A'" in msg for msg in log)

    def test_apply_link_deletion(self, tiny_graph: IntentGraph):
        """apply_diff removes link from graph."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        link_uid = "A_B"
        if link_uid in lens.intentlinks:
            del lens.intentlinks[link_uid]

            log = apply_diff(lens, tiny_graph)

            # Check that link was removed
            assert link_uid not in tiny_graph.links
            assert any(f"Deleted link '{link_uid}'" in msg for msg in log)

    def test_apply_reparenting(self, medium_graph: IntentGraph):
        """apply_diff reparents node in graph."""
        lens = build_lens(medium_graph, target_uid="ROOT", budget=100, name="test")

        # Move E.1 from E to T
        e1_node = lens.nodes["E.1"]
        e_node = lens.nodes["E"]

        e_node.children_uids = [c for c in e_node.children_uids if c != "E.1"]
        e1_node.parent_uid = "T"
        lens.nodes["T"].children_uids.append("E.1")

        lens.treearcs = [(p, c) for p, c in lens.treearcs if not (p == "E" and c == "E.1")]
        lens.treearcs.append(("T", "E.1"))

        log = apply_diff(lens, medium_graph)

        # Check that reparenting happened
        assert medium_graph.get_node("E.1").parent_uid == "T"
        assert "E.1" in medium_graph.get_node("T").children_uids
        assert "E.1" not in medium_graph.get_node("E").children_uids
        assert any("Reparented 'E.1': E → T" in msg for msg in log)

    def test_apply_resets_base_state(self, tiny_graph: IntentGraph):
        """apply_diff resets lens base state and clears dirty flag."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        lens.nodes["A"].intent = "Modified"
        lens.mark_dirty()

        apply_diff(lens, tiny_graph)

        # Base state should be updated to current working state
        assert lens.dirty is False
        assert lens.base_state is not None

    def test_apply_multiple_changes(self, medium_graph: IntentGraph):
        """apply_diff handles multiple simultaneous changes."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # Multiple changes
        lens.nodes["E.1"].intent = "Modified E.1"
        lens.nodes["T.1"].name = "Renamed T.1"
        del lens.nodes["L.3.2"]

        log = apply_diff(lens, medium_graph)

        # All changes should be applied
        assert medium_graph.get_node("E.1").intent == "Modified E.1"
        assert medium_graph.get_node("T.1").name == "Renamed T.1"
        assert "L.3.2" not in medium_graph.nodes
        assert len(log) >= 3


# ================================================================== #
#  discard_changes                                                   #
# ================================================================== #


class TestDiscardChanges:
    """Test discard_changes reverts working state to base."""

    def test_discard_reverts_node_modifications(self, tiny_graph: IntentGraph):
        """discard_changes reverts node edits."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        original_intent = lens.nodes["A"].intent

        lens.nodes["A"].intent = "Modified intent"
        lens.mark_dirty()

        discard_changes(lens)

        # Should be reverted
        assert lens.nodes["A"].intent == original_intent
        assert lens.dirty is False

    def test_discard_reverts_node_deletions(self, tiny_graph: IntentGraph):
        """discard_changes restores deleted nodes."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        assert "B" in lens.nodes

        del lens.nodes["B"]
        lens.mark_dirty()

        discard_changes(lens)

        # B should be back
        assert "B" in lens.nodes
        assert lens.dirty is False

    def test_discard_reverts_link_modifications(self, tiny_graph: IntentGraph):
        """discard_changes reverts link edits."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        link_uid = "A_B"
        if link_uid in lens.intentlinks:
            original_intent = lens.intentlinks[link_uid].intent

            lens.intentlinks[link_uid].intent = "Modified link"
            lens.mark_dirty()

            discard_changes(lens)

            assert lens.intentlinks[link_uid].intent == original_intent
            assert lens.dirty is False

    def test_discard_without_base_state_raises(self):
        """discard_changes raises if no base state."""
        from intentgraph.models.lens import Lens, LensMeta

        meta = LensMeta(name="test", target_uid="A", source_graph="g.json")
        lens = Lens(meta=meta)

        with pytest.raises(IntentGraphError, match="No base state"):
            discard_changes(lens)

    def test_discard_clears_dirty_flag(self, tiny_graph: IntentGraph):
        """discard_changes sets dirty to False."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        lens.nodes["A"].intent = "Changed"
        lens.mark_dirty()

        discard_changes(lens)

        assert lens.dirty is False


# ================================================================== #
#  Round-trip: build → edit → diff → apply → verify                 #
# ================================================================== #


class TestRoundTrip:
    """Test full round-trip: build lens, edit, diff, apply, verify graph."""

    def test_round_trip_node_edit(self, tiny_graph: IntentGraph):
        """Full cycle: edit node in lens, apply to graph, verify."""
        # Build lens
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Edit
        lens.nodes["A"].intent = "Round-trip modified intent"
        lens.nodes["A"].design_notes = "Added during test"

        # Compute diff (implicit in apply_diff, but let's check)
        diff = compute_diff(lens)
        assert len(diff["nodes_modified"]) > 0

        # Apply to graph
        apply_diff(lens, tiny_graph)

        # Verify graph
        assert tiny_graph.get_node("A").intent == "Round-trip modified intent"
        assert tiny_graph.get_node("A").design_notes == "Added during test"

        # Lens should have clean base state
        assert lens.dirty is False

    def test_round_trip_node_create_delete(self, tiny_graph: IntentGraph):
        """Full cycle: create and delete nodes, apply, verify."""
        from intentgraph.models.node import IntentNode

        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Create new node
        new_node = IntentNode(uid="C", name="Module C", intent="New module")
        new_node.parent_uid = "ROOT"
        lens.nodes["C"] = new_node

        # Delete existing node
        del lens.nodes["B"]

        # Apply
        apply_diff(lens, tiny_graph)

        # Verify
        assert "C" in tiny_graph.nodes
        assert tiny_graph.get_node("C").name == "Module C"
        assert "B" not in tiny_graph.nodes

    def test_round_trip_link_operations(self, tiny_graph: IntentGraph):
        """Full cycle: modify, create, delete links, apply, verify."""
        lens = build_lens(tiny_graph, target_uid="A", budget=50, name="test")

        # Modify existing link
        if "A_B" in lens.intentlinks:
            lens.intentlinks["A_B"].intent = "Modified link intent"

        # Create new link
        new_link = IntentLink(uid="B_ROOT", src="B", dst="ROOT", intent="New link")
        lens.intentlinks["B_ROOT"] = new_link

        # Apply
        apply_diff(lens, tiny_graph)

        # Verify
        if "A_B" in tiny_graph.links:
            assert tiny_graph.get_link("A_B").intent == "Modified link intent"
        assert "B_ROOT" in tiny_graph.links
        assert tiny_graph.get_link("B_ROOT").src == "B"

    def test_round_trip_complex_scenario(self, medium_graph: IntentGraph):
        """Complex scenario: multiple edits across nodes, links, structure."""
        lens = build_lens(medium_graph, target_uid="E.1", budget=100, name="test")

        # Node modifications
        lens.nodes["E.1"].intent = "Complex test modified"
        lens.nodes["T.1"].design_notes = "New design"

        # Link modification - use a link we know exists and will be visible
        if "E_T" in lens.intentlinks:
            lens.intentlinks["E_T"].intent = "Updated E to T flow"

        # Node deletion
        if "L.3.2" in lens.nodes:
            del lens.nodes["L.3.2"]

        # Apply all changes
        log = apply_diff(lens, medium_graph)

        # Verify all changes in graph
        assert medium_graph.get_node("E.1").intent == "Complex test modified"
        assert medium_graph.get_node("T.1").design_notes == "New design"

        # Verify link modification if it was present
        if "E_T" in medium_graph.links:
            assert medium_graph.get_link("E_T").intent == "Updated E to T flow"

        assert "L.3.2" not in medium_graph.nodes

        # Log should contain all operations
        assert len(log) >= 3  # At least node modifications and deletion
