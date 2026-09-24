"""Tests for IntentNode and HistoryEntry models."""

import pytest
from pydantic import ValidationError

from intentgraph.models.node import HistoryEntry, IntentNode


class TestHistoryEntry:

    def test_create_valid(self):
        h = HistoryEntry(who="remi", date="2026-02-12", note="Initial creation")
        assert h.who == "remi"
        assert h.date == "2026-02-12"

    def test_agent_convention(self):
        h = HistoryEntry(who="agent:extractor", date="2026-01", note="Extracted from code")
        assert h.who.startswith("agent:")


class TestIntentNode:

    def test_create_minimal(self):
        node = IntentNode(uid="ROOT", name="Root", intent="Top-level system goal")
        assert node.uid == "ROOT"
        assert node.name == "Root"
        assert node.intent == "Top-level system goal"
        assert node.epistemic_state is None
        assert node.constraints == []
        assert node.examples == []
        assert node.design_notes is None
        assert node.effort is None
        assert node.history == []
        assert node.data_registry is None
        assert node.parent_uid is None
        assert node.children_uids == []

    def test_create_full(self):
        node = IntentNode(
            uid="E.1.3",
            name="Validate credentials",
            intent="Parse and validate auth credentials from request",
            epistemic_state="risky -- JWT library has known CVEs",
            constraints=["Must support OAuth2", "Must support API key"],
            examples=["Bearer token in header", "API key in query param"],
            design_notes="Chose jose library over pyjwt for ECDSA support",
            effort="high correctness critical",
            history=[
                HistoryEntry(who="agent:extractor", date="2026-01-15", note="Extracted"),
                HistoryEntry(who="remi", date="2026-01-22", note="Reviewed and refined"),
            ],
        )
        assert node.uid == "E.1.3"
        assert len(node.constraints) == 2
        assert len(node.history) == 2
        assert node.history[0].who == "agent:extractor"

    def test_uid_empty_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            IntentNode(uid="", name="X", intent="Y")

    def test_uid_whitespace_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            IntentNode(uid="   ", name="X", intent="Y")

    def test_name_empty_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            IntentNode(uid="A", name="", intent="Y")

    def test_intent_empty_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            IntentNode(uid="A", name="X", intent="")

    def test_is_leaf_and_is_root(self):
        node = IntentNode(uid="A", name="X", intent="Y")
        assert node.is_leaf is True
        assert node.is_root is True

        node.parent_uid = "ROOT"
        assert node.is_root is False

        node.children_uids = ["A.1"]
        assert node.is_leaf is False

    def test_to_serial_dict_excludes_structural(self):
        node = IntentNode(uid="A", name="X", intent="Y", parent_uid="ROOT")
        node.children_uids = ["A.1"]
        d = node.to_serial_dict()
        assert "parent_uid" not in d
        assert "children_uids" not in d
        assert d["uid"] == "A"

    def test_to_serial_dict_omits_none_optionals(self):
        node = IntentNode(uid="A", name="X", intent="Y")
        d = node.to_serial_dict()
        assert "epistemic_state" not in d
        assert "design_notes" not in d
        assert "effort" not in d
        assert "constraints" not in d  # empty list omitted
        assert "history" not in d  # empty list omitted
        assert "data_registry" not in d  # None omitted

    def test_data_registry_round_trip(self):
        node = IntentNode(
            uid="A",
            name="X",
            intent="Y",
            constraints=["Node positions defined in /positions"],
            data_registry={
                "positions": {"ROOT.1": {"x": 100, "y": 300, "width": 250, "height": 150}},
                "spacing": {"horizontal": 150, "vertical": 100},
            },
        )
        assert node.data_registry["spacing"]["horizontal"] == 150
        d = node.to_serial_dict()
        assert "data_registry" in d
        assert d["data_registry"]["positions"]["ROOT.1"]["x"] == 100
        node2 = IntentNode.from_serial_dict(d)
        assert node2.data_registry == node.data_registry

    def test_data_registry_empty_dict_omitted(self):
        node = IntentNode(uid="A", name="X", intent="Y", data_registry={})
        d = node.to_serial_dict()
        assert "data_registry" not in d

    def test_data_registry_epistemic_key_preserved(self):
        node = IntentNode(
            uid="A",
            name="X",
            intent="Y",
            data_registry={
                "positions": {"ROOT.1": None},
                "_epistemic": {"positions/ROOT.1": "undecided"},
            },
        )
        d = node.to_serial_dict()
        assert d["data_registry"]["_epistemic"]["positions/ROOT.1"] == "undecided"

    def test_serial_round_trip(self):
        node = IntentNode(
            uid="E.1",
            name="Extract",
            intent="Extract data",
            epistemic_state="known",
            constraints=["Must be idempotent"],
            history=[HistoryEntry(who="remi", date="2026-02", note="Created")],
        )
        d = node.to_serial_dict()
        node2 = IntentNode.from_serial_dict(d)
        assert node2.uid == node.uid
        assert node2.epistemic_state == node.epistemic_state
        assert node2.constraints == node.constraints
        assert len(node2.history) == 1
        assert node2.history[0].who == "remi"
