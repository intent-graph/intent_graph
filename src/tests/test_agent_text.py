"""Tests for agent text format — serializer, parser, round-trip, error handling."""

import pytest
import yaml

from intentgraph.errors import ParseError
from intentgraph.models.view import View
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.agent_text import (
    LinkCreate,
    LinkDelete,
    LinkUpdate,
    NodeCreate,
    NodeDelete,
    NodeUpdate,
    apply_edits,
    diff_to_edits,
    parse_agent_output,
    text_to_edits,
    view_to_text,
)


# ================================================================== #
#  Serializer: view -> text                                           #
# ================================================================== #


class TestViewToText:

    def test_basic_structure(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "level1", {"E", "T", "L"})
        text = view_to_text(f)

        # Must be valid YAML
        doc = yaml.safe_load(text)
        assert "view" in doc
        assert "nodes" in doc
        assert "intentlinks" in doc

    def test_view_header(self, medium_graph: IntentGraph):
        f = View.from_node_set(
            medium_graph, "my_view", {"E", "T", "L"}, scope="ETL overview"
        )
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        assert doc["view"]["name"] == "my_view"
        assert doc["view"]["scope"] == "ETL overview"

    def test_nodes_have_required_fields(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        for node in doc["nodes"]:
            assert "uid" in node
            assert "name" in node
            assert "intent" in node

    def test_collapsed_children_shown(self, medium_graph: IntentGraph):
        """Non-leaf view nodes should list their collapsed children."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        e_node = next(n for n in doc["nodes"] if n["uid"] == "E")
        assert "collapsed_children" in e_node
        assert set(e_node["collapsed_children"]) == {"E.1", "E.2", "E.3"}

    def test_optional_fields_included_when_set(self, medium_graph: IntentGraph):
        medium_graph.update_node(
            "E",
            epistemic_state="known",
            constraints=["Must be idempotent"],
            design_notes="Chose streaming for memory efficiency",
        )
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        e_node = next(n for n in doc["nodes"] if n["uid"] == "E")
        assert e_node["epistemic_state"] == "known"
        assert e_node["constraints"] == ["Must be idempotent"]
        assert e_node["design_notes"] == "Chose streaming for memory efficiency"

    def test_lean_nodes_emit_only_core_fields(self, medium_graph: IntentGraph):
        medium_graph.update_node(
            "E",
            epistemic_state="known",
            constraints=["Must be idempotent"],
            design_notes="Chose streaming for memory efficiency",
            impl_pointers="src/extract/main.py",
        )
        medium_graph.update_node(
            "T",
            epistemic_state="known",
            constraints=["Normalize into canonical schema"],
        )
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f, lean_node_uids={"E"})
        doc = yaml.safe_load(text)

        e_node = next(n for n in doc["nodes"] if n["uid"] == "E")
        assert set(e_node.keys()) <= {"uid", "name", "intent", "epistemic_state"}
        assert "constraints" not in e_node
        assert "design_notes" not in e_node
        assert "impl_pointers" not in e_node
        assert "collapsed_children" not in e_node

        t_node = next(n for n in doc["nodes"] if n["uid"] == "T")
        assert "constraints" in t_node

    def test_intentlinks_projected(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        links = doc["intentlinks"]
        assert len(links) > 0
        # E->T and T->L should be present (direct or lifted)
        pairs = {(l["src"], l["dst"]) for l in links}
        assert ("E", "T") in pairs
        assert ("T", "L") in pairs

    def test_lifted_links_marked(self, medium_graph: IntentGraph):
        """Links projected from below the view should have lifted=True."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        lifted = [l for l in doc["intentlinks"] if l.get("lifted")]
        # E.3->T.1 projects to E->T, which should be lifted
        assert len(lifted) > 0
        for l in lifted:
            assert "original_src" in l
            assert "original_dst" in l

    def test_nodes_sorted_by_uid(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)

        uids = [n["uid"] for n in doc["nodes"]]
        assert uids == sorted(uids)


# ================================================================== #
#  Parser: text -> edits                                              #
# ================================================================== #


class TestTextToEdits:

    def test_no_changes_produces_no_edits(self, medium_graph: IntentGraph):
        """Parsing the graph's own serialized view should produce no edits."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        edits = text_to_edits(text, medium_graph)
        assert edits == []

    def test_node_update_detected(self, medium_graph: IntentGraph):
        """Changing a field in the text should produce a NodeUpdate."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)

        doc = yaml.safe_load(text)
        # Modify E's intent
        for n in doc["nodes"]:
            if n["uid"] == "E":
                n["intent"] = "CHANGED: Extract all data sources"
                n["epistemic_state"] = "risky"
                break

        modified_text = yaml.dump(doc, default_flow_style=False, sort_keys=False)
        edits = text_to_edits(modified_text, medium_graph)

        updates = [e for e in edits if isinstance(e, NodeUpdate)]
        assert len(updates) == 1
        assert updates[0].uid == "E"
        assert updates[0].fields["intent"] == "CHANGED: Extract all data sources"
        assert updates[0].fields["epistemic_state"] == "risky"

    def test_node_create_detected(self, medium_graph: IntentGraph):
        """A new node in the text should produce a NodeCreate."""
        text = yaml.dump({
            "view": {"name": "test"},
            "nodes": [
                {"uid": "NEW.1", "name": "New Node", "intent": "Brand new intent"},
            ],
            "intentlinks": [],
        }, sort_keys=False)

        edits = text_to_edits(text, medium_graph)
        creates = [e for e in edits if isinstance(e, NodeCreate)]
        assert len(creates) == 1
        assert creates[0].uid == "NEW.1"
        assert creates[0].name == "New Node"

    def test_node_delete_detected(self, medium_graph: IntentGraph):
        """A node marked _delete: true should produce a NodeDelete."""
        text = yaml.dump({
            "view": {"name": "test"},
            "nodes": [
                {"uid": "E", "_delete": True},
            ],
            "intentlinks": [],
        }, sort_keys=False)

        edits = text_to_edits(text, medium_graph)
        deletes = [e for e in edits if isinstance(e, NodeDelete)]
        assert len(deletes) == 1
        assert deletes[0].uid == "E"

    def test_link_create_detected(self, medium_graph: IntentGraph):
        """A new link in the text should produce a LinkCreate."""
        text = yaml.dump({
            "view": {"name": "test"},
            "nodes": [],
            "intentlinks": [
                {"src": "L", "dst": "E", "intent": "Feedback loop"},
            ],
        }, sort_keys=False)

        edits = text_to_edits(text, medium_graph)
        creates = [e for e in edits if isinstance(e, LinkCreate)]
        assert len(creates) == 1
        assert creates[0].src == "L"
        assert creates[0].dst == "E"

    def test_link_update_detected(self, medium_graph: IntentGraph):
        """Changing an existing link's intent in a full-view text should
        produce a LinkUpdate — not be silently dropped (Bug 2)."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)

        doc = yaml.safe_load(text)
        link = next(l for l in doc["intentlinks"] if l["uid"] == "E_T")
        link["intent"] = "CHANGED: extracted data now streams to transform"

        modified_text = yaml.dump(doc, default_flow_style=False, sort_keys=False)
        edits = text_to_edits(modified_text, medium_graph)

        updates = [e for e in edits if isinstance(e, LinkUpdate)]
        assert len(updates) == 1
        assert updates[0].uid == "E_T"
        assert updates[0].fields == {
            "intent": "CHANGED: extracted data now streams to transform"
        }
        # No spurious LinkCreate/LinkDelete for the same entity.
        assert not [e for e in edits if isinstance(e, LinkCreate) and e.src == "E" and e.dst == "T"]

        log = apply_edits(medium_graph, edits)
        assert medium_graph.get_link("E_T").intent == (
            "CHANGED: extracted data now streams to transform"
        )
        assert any("E_T" in entry for entry in log)

    def test_link_unchanged_produces_no_edit(self, medium_graph: IntentGraph):
        """An existing link whose fields are identical to the graph should
        round-trip with no edit (not a create, not an update)."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)

        edits = text_to_edits(text, medium_graph)
        link_edits = [
            e for e in edits
            if isinstance(e, (LinkCreate, LinkUpdate, LinkDelete))
        ]
        assert link_edits == []

    def test_link_delete_detected(self, medium_graph: IntentGraph):
        text = yaml.dump({
            "view": {"name": "test"},
            "nodes": [],
            "intentlinks": [
                {"uid": "E_T", "_delete": True},
            ],
        }, sort_keys=False)

        edits = text_to_edits(text, medium_graph)
        deletes = [e for e in edits if isinstance(e, LinkDelete)]
        assert len(deletes) == 1
        assert deletes[0].uid == "E_T"

    def test_lifted_links_skipped(self, medium_graph: IntentGraph):
        """Lifted links should be ignored by the parser (they are projections)."""
        text = yaml.dump({
            "view": {"name": "test"},
            "nodes": [],
            "intentlinks": [
                {
                    "uid": "E.3_T.1",
                    "src": "E",
                    "dst": "T",
                    "intent": "Projected link",
                    "lifted": True,
                    "original_src": "E.3",
                    "original_dst": "T.1",
                },
            ],
        }, sort_keys=False)

        edits = text_to_edits(text, medium_graph)
        assert edits == []


# ================================================================== #
#  Apply edits                                                        #
# ================================================================== #


class TestApplyEdits:

    def test_apply_node_create(self, tiny_graph: IntentGraph):
        edits = [NodeCreate(uid="C", name="Module C", intent="Does C things")]
        log = apply_edits(tiny_graph, edits)
        assert tiny_graph.get_node_or_none("C") is not None
        assert len(log) == 1

    def test_apply_node_update(self, tiny_graph: IntentGraph):
        edits = [NodeUpdate(uid="A", fields={"intent": "Updated A intent"})]
        apply_edits(tiny_graph, edits)
        assert tiny_graph.get_node("A").intent == "Updated A intent"

    def test_apply_node_delete(self, tiny_graph: IntentGraph):
        edits = [NodeDelete(uid="B")]
        apply_edits(tiny_graph, edits)
        assert tiny_graph.get_node_or_none("B") is None

    def test_apply_link_create(self, tiny_graph: IntentGraph):
        edits = [LinkCreate(src="B", dst="A", intent="B responds to A")]
        apply_edits(tiny_graph, edits)
        assert tiny_graph.link_count() == 2

    def test_apply_link_delete(self, tiny_graph: IntentGraph):
        edits = [LinkDelete(uid="A_B")]
        apply_edits(tiny_graph, edits)
        assert tiny_graph.link_count() == 0


# ================================================================== #
#  Error handling                                                     #
# ================================================================== #


class TestParseErrors:

    def test_invalid_yaml(self, medium_graph: IntentGraph):
        with pytest.raises(ParseError, match="Invalid YAML"):
            text_to_edits("{{{{not yaml", medium_graph)

    def test_not_a_mapping(self, medium_graph: IntentGraph):
        with pytest.raises(ParseError, match="mapping"):
            text_to_edits("- just a list", medium_graph)

    def test_nodes_not_a_list(self, medium_graph: IntentGraph):
        with pytest.raises(ParseError, match="'nodes' must be a list"):
            text_to_edits(
                yaml.dump({"nodes": "not a list", "intentlinks": []}),
                medium_graph,
            )

    def test_node_missing_uid(self, medium_graph: IntentGraph):
        with pytest.raises(ParseError, match="uid"):
            text_to_edits(
                yaml.dump({
                    "nodes": [{"name": "X", "intent": "Y"}],
                    "intentlinks": [],
                }),
                medium_graph,
            )

    def test_new_node_missing_intent(self, medium_graph: IntentGraph):
        with pytest.raises(ParseError, match="require 'name' and 'intent'"):
            text_to_edits(
                yaml.dump({
                    "nodes": [{"uid": "NEW.1", "name": "X"}],
                    "intentlinks": [],
                }),
                medium_graph,
            )

    def test_link_missing_fields(self, medium_graph: IntentGraph):
        with pytest.raises(ParseError, match="'src', 'dst', and 'intent' are required"):
            text_to_edits(
                yaml.dump({
                    "nodes": [],
                    "intentlinks": [{"src": "E"}],
                }),
                medium_graph,
            )


# ================================================================== #
#  Round-trip: serialize -> parse -> apply -> re-serialize            #
# ================================================================== #


class TestRoundTrip:

    def test_serialize_parse_no_drift(self, medium_graph: IntentGraph):
        """Serializing and parsing the same view should produce zero edits."""
        f = View.from_depth(medium_graph, "d2", depth=2)
        text = view_to_text(f)
        edits = text_to_edits(text, medium_graph)
        assert edits == [], f"Expected no edits, got: {edits}"

    def test_modify_and_apply_round_trip(self, medium_graph: IntentGraph):
        """Modify a view text, apply edits, re-serialize, and verify no further drift."""
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)

        # Agent modifies a node
        doc = yaml.safe_load(text)
        for n in doc["nodes"]:
            if n["uid"] == "T":
                n["intent"] = "Transform data with validation"
                n["epistemic_state"] = "constrained"
                break
        modified_text = yaml.dump(doc, default_flow_style=False, sort_keys=False)

        # Parse and apply
        edits = text_to_edits(modified_text, medium_graph)
        assert len(edits) == 1
        apply_edits(medium_graph, edits)

        # Verify the change stuck
        assert medium_graph.get_node("T").intent == "Transform data with validation"
        assert medium_graph.get_node("T").epistemic_state == "constrained"

        # Re-serialize and re-parse: should produce zero edits now
        text2 = view_to_text(f)
        edits2 = text_to_edits(text2, medium_graph)
        assert edits2 == []


# ================================================================== #
#  LinkUpdate + graph.update_link                                     #
# ================================================================== #


class TestLinkUpdate:

    def test_update_link_intent(self, tiny_graph: IntentGraph):
        edits = [LinkUpdate(uid="A_B", fields={"intent": "A sends filtered data to B"})]
        log = apply_edits(tiny_graph, edits)
        assert tiny_graph.get_link("A_B").intent == "A sends filtered data to B"
        assert len(log) == 1

    def test_update_link_shape(self, tiny_graph: IntentGraph):
        edits = [LinkUpdate(uid="A_B", fields={"shape": {"type": "stream", "format": "json"}})]
        apply_edits(tiny_graph, edits)
        assert tiny_graph.get_link("A_B").shape == {"type": "stream", "format": "json"}

    def test_update_link_structural_fields_rejected(self, tiny_graph: IntentGraph):
        from intentgraph.errors import IntentGraphError
        with pytest.raises(IntentGraphError, match="structural"):
            tiny_graph.update_link("A_B", src="X")

    def test_update_link_not_found(self, tiny_graph: IntentGraph):
        from intentgraph.errors import LinkNotFoundError
        with pytest.raises(LinkNotFoundError):
            tiny_graph.update_link("NONEXISTENT", intent="nope")


# ================================================================== #
#  Diff format: diff_to_edits                                         #
# ================================================================== #


class TestDiffToEdits:

    def _make_diff(self, nodes=None, intentlinks=None, **meta_overrides):
        meta = {"base": "graph.json", "author": "agent:test"}
        meta.update(meta_overrides)
        doc = {"diff_meta": meta}
        if nodes is not None:
            doc["nodes"] = nodes
        if intentlinks is not None:
            doc["intentlinks"] = intentlinks
        return yaml.dump(doc, default_flow_style=False, sort_keys=False)

    def test_empty_diff_produces_no_edits(self, medium_graph: IntentGraph):
        text = self._make_diff(nodes=[], links=[])
        edits = diff_to_edits(text, medium_graph)
        assert edits == []

    def test_node_create(self, medium_graph: IntentGraph):
        text = self._make_diff(nodes=[
            {"uid": "NEW.1", "name": "New Node", "intent": "Brand new", "_new": True, "parent": "E"},
        ])
        edits = diff_to_edits(text, medium_graph)
        creates = [e for e in edits if isinstance(e, NodeCreate)]
        assert len(creates) == 1
        assert creates[0].uid == "NEW.1"
        assert creates[0].name == "New Node"

    def test_node_update(self, medium_graph: IntentGraph):
        text = self._make_diff(nodes=[
            {"uid": "E", "intent": "Updated extraction intent"},
        ])
        edits = diff_to_edits(text, medium_graph)
        updates = [e for e in edits if isinstance(e, NodeUpdate)]
        assert len(updates) == 1
        assert updates[0].uid == "E"
        assert updates[0].fields == {"intent": "Updated extraction intent"}

    def test_node_update_with_prev_ignored(self, medium_graph: IntentGraph):
        """_prev is for review only — the parser ignores it."""
        text = self._make_diff(nodes=[
            {
                "uid": "E",
                "intent": "Updated extraction intent",
                "_prev": {"intent": "Data extraction"},
            },
        ])
        edits = diff_to_edits(text, medium_graph)
        updates = [e for e in edits if isinstance(e, NodeUpdate)]
        assert len(updates) == 1
        assert "_prev" not in updates[0].fields

    def test_node_delete(self, medium_graph: IntentGraph):
        text = self._make_diff(nodes=[
            {"uid": "E.1", "_delete": True},
        ])
        edits = diff_to_edits(text, medium_graph)
        deletes = [e for e in edits if isinstance(e, NodeDelete)]
        assert len(deletes) == 1
        assert deletes[0].uid == "E.1"

    def test_link_create(self, medium_graph: IntentGraph):
        text = self._make_diff(intentlinks=[
            {"uid": "L_E", "src": "L", "dst": "E", "intent": "Feedback loop", "_new": True},
        ])
        edits = diff_to_edits(text, medium_graph)
        creates = [e for e in edits if isinstance(e, LinkCreate)]
        assert len(creates) == 1
        assert creates[0].src == "L"
        assert creates[0].dst == "E"

    def test_link_update(self, medium_graph: IntentGraph):
        text = self._make_diff(intentlinks=[
            {"uid": "E_T", "intent": "Refined: Extracted data flows to transformation step"},
        ])
        edits = diff_to_edits(text, medium_graph)
        updates = [e for e in edits if isinstance(e, LinkUpdate)]
        assert len(updates) == 1
        assert updates[0].uid == "E_T"
        assert updates[0].fields["intent"] == "Refined: Extracted data flows to transformation step"

    def test_link_delete(self, medium_graph: IntentGraph):
        text = self._make_diff(intentlinks=[
            {"uid": "E_T", "_delete": True},
        ])
        edits = diff_to_edits(text, medium_graph)
        deletes = [e for e in edits if isinstance(e, LinkDelete)]
        assert len(deletes) == 1
        assert deletes[0].uid == "E_T"

    def test_lifted_links_skipped(self, medium_graph: IntentGraph):
        text = self._make_diff(intentlinks=[
            {"uid": "E.3_T.1", "src": "E", "dst": "T", "intent": "Projected",
             "lifted": True, "original_src": "E.3", "original_dst": "T.1"},
        ])
        edits = diff_to_edits(text, medium_graph)
        assert edits == []

    def test_mixed_operations(self, medium_graph: IntentGraph):
        """A diff with creates, updates, and deletes all at once."""
        text = self._make_diff(
            nodes=[
                {"uid": "NEW.X", "name": "X", "intent": "New X", "_new": True},
                {"uid": "E", "epistemic_state": "risky"},
                {"uid": "E.2", "_delete": True},
            ],
            intentlinks=[
                {"uid": "E_T", "intent": "Reworded flow"},
                {"uid": "T_L", "_delete": True},
                {"uid": "L_E", "src": "L", "dst": "E", "intent": "Loop", "_new": True},
            ],
        )
        edits = diff_to_edits(text, medium_graph)
        assert len(edits) == 6

        types = [type(e).__name__ for e in edits]
        assert "NodeCreate" in types
        assert "NodeUpdate" in types
        assert "NodeDelete" in types
        assert "LinkUpdate" in types
        assert "LinkDelete" in types
        assert "LinkCreate" in types

    def test_missing_diff_meta_raises(self, medium_graph: IntentGraph):
        text = yaml.dump({"nodes": [], "intentlinks": []})
        with pytest.raises(ParseError, match="diff_meta"):
            diff_to_edits(text, medium_graph)

    def test_new_node_missing_intent_raises(self, medium_graph: IntentGraph):
        text = self._make_diff(nodes=[
            {"uid": "BAD", "name": "No intent", "_new": True},
        ])
        with pytest.raises(ParseError, match="require 'name' and 'intent'"):
            diff_to_edits(text, medium_graph)

    def test_new_link_missing_fields_raises(self, medium_graph: IntentGraph):
        text = self._make_diff(intentlinks=[
            {"src": "E", "_new": True},
        ])
        with pytest.raises(ParseError, match="new links require"):
            diff_to_edits(text, medium_graph)

    def test_link_update_missing_uid_raises(self, medium_graph: IntentGraph):
        text = self._make_diff(intentlinks=[
            {"intent": "No uid provided"},
        ])
        with pytest.raises(ParseError, match="link updates require 'uid'"):
            diff_to_edits(text, medium_graph)


# ================================================================== #
#  Auto-detection: parse_agent_output                                 #
# ================================================================== #


class TestParseAgentOutput:

    def test_routes_to_text_to_edits_for_view_format(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        edits = parse_agent_output(text, medium_graph)
        assert edits == []

    def test_routes_to_diff_to_edits_for_diff_format(self, medium_graph: IntentGraph):
        doc = {
            "diff_meta": {"base": "graph.json", "author": "agent:test"},
            "nodes": [{"uid": "E", "intent": "Changed intent"}],
            "intentlinks": [],
        }
        text = yaml.dump(doc, default_flow_style=False, sort_keys=False)
        edits = parse_agent_output(text, medium_graph)
        assert len(edits) == 1
        assert isinstance(edits[0], NodeUpdate)

    def test_invalid_yaml_raises(self, medium_graph: IntentGraph):
        with pytest.raises(ParseError):
            parse_agent_output("{{{{bad yaml", medium_graph)


# ================================================================== #
#  Diff round-trip: diff -> edits -> apply -> verify                  #
# ================================================================== #


class TestDiffRoundTrip:

    def test_apply_diff_and_verify(self, medium_graph: IntentGraph):
        """Apply a diff, then verify changes took effect."""
        doc = {
            "diff_meta": {"base": "graph.json", "author": "agent:extractor"},
            "nodes": [
                {"uid": "T", "intent": "Transform with strict validation", "epistemic_state": "constrained"},
                {"uid": "E.2", "_delete": True},
            ],
            "intentlinks": [
                {"uid": "E_T", "intent": "Validated data flows to strict transformation"},
            ],
        }
        text = yaml.dump(doc, default_flow_style=False, sort_keys=False)
        edits = diff_to_edits(text, medium_graph)
        apply_edits(medium_graph, edits, agent_role="extractor")

        assert medium_graph.get_node("T").intent == "Transform with strict validation"
        assert medium_graph.get_node("T").epistemic_state == "constrained"
        assert medium_graph.get_node_or_none("E.2") is None
        assert medium_graph.get_link("E_T").intent == "Validated data flows to strict transformation"

        # History appended for updates
        t_history = medium_graph.get_node("T").history
        assert any("extractor" in h.who for h in t_history)


# ================================================================== #
#  Legacy header compatibility                                        #
# ================================================================== #


class TestLegacyFrontierHeader:
    """The legacy `frontier:` header key is still accepted on read."""

    def test_legacy_frontier_header_parses(self, medium_graph: IntentGraph):
        text = yaml.dump({
            "frontier": {"name": "legacy"},
            "nodes": [
                {"uid": "NEW.9", "name": "New Node", "intent": "Created via legacy header"},
            ],
            "intentlinks": [],
        }, sort_keys=False)

        edits = text_to_edits(text, medium_graph)
        creates = [e for e in edits if isinstance(e, NodeCreate)]
        assert len(creates) == 1
        assert creates[0].uid == "NEW.9"

    def test_legacy_frontier_header_auto_detected(self, medium_graph: IntentGraph):
        text = yaml.dump({
            "frontier": {"name": "legacy"},
            "nodes": [{"uid": "E", "name": "Extract", "intent": "Changed via legacy header"}],
            "intentlinks": [],
        }, sort_keys=False)

        edits = parse_agent_output(text, medium_graph)
        assert len(edits) == 1
        assert isinstance(edits[0], NodeUpdate)

    def test_emitter_writes_view_header(self, medium_graph: IntentGraph):
        f = View.from_node_set(medium_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        doc = yaml.safe_load(text)
        assert "view" in doc
        assert "frontier" not in doc
