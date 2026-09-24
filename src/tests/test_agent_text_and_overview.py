"""Tests for WP-2.0.1 additions — history/impl_pointers in agent text,
tree overview, edge overview, view size estimation, and auto history injection.
"""

import yaml
import pytest

from intentgraph.models.view import View
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.agent_text import (
    NodeCreate,
    NodeUpdate,
    apply_edits,
    text_to_edits,
    view_to_text,
)
from intentgraph.serial.graph_overview import (
    graph_to_edge_overview,
    graph_to_tree_overview,
    view_text_size,
)


# ================================================================== #
#  history in agent text format                                        #
# ================================================================== #


class TestHistoryInAgentText:

    def test_history_serialized_when_present(self, medium_graph: IntentGraph):
        """Nodes with history entries should include them in the serialized text."""
        medium_graph.update_node("E", history=[
            {"who": "remi", "date": "2026-01-15", "note": "Initial design"},
            {"who": "agent:extractor", "date": "2026-01-16", "note": "Refined scope"},
        ])
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        e_node = next(n for n in doc["nodes"] if n["uid"] == "E")
        assert "history" in e_node
        assert len(e_node["history"]) == 2
        assert e_node["history"][0]["who"] == "remi"
        assert e_node["history"][1]["who"] == "agent:extractor"

    def test_history_not_serialized_when_empty(self, medium_graph: IntentGraph):
        """Nodes without history should not have a history key in output."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        e_node = next(n for n in doc["nodes"] if n["uid"] == "E")
        assert "history" not in e_node

    def test_history_round_trip_no_drift(self, medium_graph: IntentGraph):
        """Serialize with history, parse back, no spurious edits."""
        medium_graph.update_node("T", history=[
            {"who": "agent:critic", "date": "2026-02-01", "note": "Flagged vagueness"},
        ])
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        edits = text_to_edits(text, medium_graph)
        assert edits == [], f"Expected no edits, got: {edits}"

    def test_history_modification_detected(self, medium_graph: IntentGraph):
        """Adding a history entry via text should produce a NodeUpdate."""
        medium_graph.update_node("E", history=[
            {"who": "remi", "date": "2026-01-15", "note": "Initial"},
        ])
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)

        doc = yaml.safe_load(text)
        for n in doc["nodes"]:
            if n["uid"] == "E":
                n["history"].append(
                    {"who": "agent:elicitor", "date": "2026-02-10", "note": "Refined"}
                )
                break

        modified_text = yaml.dump(doc, default_flow_style=False, sort_keys=False)
        edits = text_to_edits(modified_text, medium_graph)

        updates = [e for e in edits if isinstance(e, NodeUpdate)]
        assert len(updates) == 1
        assert updates[0].uid == "E"
        assert "history" in updates[0].fields
        assert len(updates[0].fields["history"]) == 2


# ================================================================== #
#  impl_pointers in agent text format                                  #
# ================================================================== #


class TestImplPointersInAgentText:

    def test_impl_pointers_serialized_when_present(self, medium_graph: IntentGraph):
        medium_graph.update_node("E", impl_pointers=["src/extract/main.py (lines 10-50)", "src/extract/csv.py"])
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        e_node = next(n for n in doc["nodes"] if n["uid"] == "E")
        assert e_node["impl_pointers"] == ["src/extract/main.py (lines 10-50)", "src/extract/csv.py"]

    def test_impl_pointers_not_serialized_when_none(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        e_node = next(n for n in doc["nodes"] if n["uid"] == "E")
        assert "impl_pointers" not in e_node

    def test_impl_pointers_round_trip(self, medium_graph: IntentGraph):
        medium_graph.update_node("T", impl_pointers=["src/transform/pipeline.py"])
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        edits = text_to_edits(text, medium_graph)
        assert edits == []

    def test_impl_pointers_update_detected(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)

        doc = yaml.safe_load(text)
        for n in doc["nodes"]:
            if n["uid"] == "L":
                n["impl_pointers"] = "src/load/loader.py:1-100"
                break

        modified_text = yaml.dump(doc, default_flow_style=False, sort_keys=False)
        edits = text_to_edits(modified_text, medium_graph)

        updates = [e for e in edits if isinstance(e, NodeUpdate)]
        assert len(updates) == 1
        assert updates[0].uid == "L"
        assert updates[0].fields["impl_pointers"] == "src/load/loader.py:1-100"


# ================================================================== #
#  Auto history injection via agent_role                               #
# ================================================================== #


class TestAutoHistoryInjection:

    def test_agent_role_injects_history_on_create(self, tiny_graph: IntentGraph):
        edits = [NodeCreate(uid="C", name="Module C", intent="Does C things")]
        apply_edits(tiny_graph, edits, agent_role="extractor")

        node = tiny_graph.get_node("C")
        assert len(node.history) == 1
        assert node.history[0].who == "agent:extractor"
        assert "Created" in node.history[0].note

    def test_agent_role_injects_history_on_update(self, tiny_graph: IntentGraph):
        edits = [NodeUpdate(uid="A", fields={"intent": "Updated intent"})]
        apply_edits(tiny_graph, edits, agent_role="elicitor")

        node = tiny_graph.get_node("A")
        assert len(node.history) == 1
        assert node.history[0].who == "agent:elicitor"
        assert "intent" in node.history[0].note

    def test_no_history_when_role_not_provided(self, tiny_graph: IntentGraph):
        edits = [NodeCreate(uid="C", name="Module C", intent="Does C things")]
        apply_edits(tiny_graph, edits)

        node = tiny_graph.get_node("C")
        assert len(node.history) == 0

    def test_agent_role_does_not_affect_delete(self, tiny_graph: IntentGraph):
        """Deletes should work fine with agent_role (no history on deleted nodes)."""
        from intentgraph.serial.agent_text import NodeDelete
        edits = [NodeDelete(uid="B")]
        log = apply_edits(tiny_graph, edits, agent_role="extractor")
        assert "Deleted" in log[0]
        assert tiny_graph.get_node_or_none("B") is None


# ================================================================== #
#  Tree overview                                                       #
# ================================================================== #


class TestTreeOverview:

    def test_tree_overview_is_valid_yaml(self, medium_graph: IntentGraph):
        text = graph_to_tree_overview(medium_graph)
        doc = yaml.safe_load(text)
        assert "meta" in doc
        assert "tree" in doc

    def test_tree_overview_meta_counts(self, medium_graph: IntentGraph):
        text = graph_to_tree_overview(medium_graph)
        doc = yaml.safe_load(text)
        assert doc["meta"]["node_count"] == medium_graph.node_count()
        assert doc["meta"]["link_count"] == medium_graph.link_count()
        assert doc["meta"]["max_depth"] >= 2  # ROOT -> E -> E.1

    def test_tree_overview_contains_all_nodes(self, medium_graph: IntentGraph):
        """Every node UID should appear somewhere in the tree overview."""
        text = graph_to_tree_overview(medium_graph)
        for uid in medium_graph.nodes:
            assert uid in text, f"Node '{uid}' missing from tree overview"

    def test_tree_overview_compact(self, medium_graph: IntentGraph):
        """Tree overview should be much smaller than full view text."""
        from intentgraph.serial.agent_text import view_to_text

        overview = graph_to_tree_overview(medium_graph)
        # Full view at max depth for comparison
        f = View.from_depth(medium_graph, "deep", depth=3)
        full = view_to_text(f)

        assert len(overview) < len(full)

    def test_tree_overview_empty_graph(self, empty_graph: IntentGraph):
        text = graph_to_tree_overview(empty_graph)
        doc = yaml.safe_load(text)
        assert doc["tree"] == {}

    def test_tree_overview_includes_epistemic_state(self, medium_graph: IntentGraph):
        medium_graph.update_node("E", epistemic_state="risky")
        text = graph_to_tree_overview(medium_graph)
        assert "epistemic:risky" in text


# ================================================================== #
#  Edge overview                                                       #
# ================================================================== #


class TestEdgeOverview:

    def test_edge_overview_is_valid_yaml(self, medium_graph: IntentGraph):
        text = graph_to_edge_overview(medium_graph)
        doc = yaml.safe_load(text)
        assert "link_count" in doc
        assert "intentlinks" in doc

    def test_edge_overview_count_matches(self, medium_graph: IntentGraph):
        text = graph_to_edge_overview(medium_graph)
        doc = yaml.safe_load(text)
        assert doc["link_count"] == medium_graph.link_count()
        assert len(doc["intentlinks"]) == medium_graph.link_count()

    def test_edge_overview_contains_all_links(self, medium_graph: IntentGraph):
        text = graph_to_edge_overview(medium_graph)
        for link in medium_graph.iter_links():
            assert link.src in text
            assert link.dst in text


# ================================================================== #
#  View size estimation                                                #
# ================================================================== #


class TestViewTextSize:

    def test_basic_size_estimation(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        size = view_text_size(text)

        assert size["chars"] == len(text)
        assert size["words"] > 0
        assert size["lines"] > 0

    def test_larger_view_has_more_words(self, medium_graph: IntentGraph):
        small = View.from_node_set(medium_graph, "small", {"E", "T", "L"})
        large = View.from_depth(medium_graph, "large", depth=2)

        small_size = view_text_size(view_to_text(small))
        large_size = view_text_size(view_to_text(large))

        assert large_size["words"] > small_size["words"]

    def test_empty_text_returns_zeros(self):
        size = view_text_size("")
        assert size["chars"] == 0
        assert size["words"] == 0
