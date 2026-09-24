"""Field-level contracts agreed 2026-07-15 (formalism §4/§4.2).

- impl_pointers is list[str] with legacy-string coercion
- effort is free text (str), assignment-validated
- update_node/update_link reject unknown fields (strict, no silent drops)
- unset_node_fields clears optional fields (lists → [], scalars → None)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from intentgraph.errors import IntentGraphError
from intentgraph.models.graph import IntentGraph
from intentgraph.models.node import IntentNode


def _graph() -> IntentGraph:
    g = IntentGraph()
    g.add_node("ROOT", "Root", "System root")
    g.add_node("A", "A", "Module A")
    g.attach("ROOT", "A")
    g.add_link("ROOT", "A", "root uses A")
    return g


class TestImplPointers:
    def test_list_of_strings_is_canonical(self):
        n = IntentNode(uid="X", name="x", intent="i",
                       impl_pointers=["src/a.py::Cls.m (lines 1-5)", "src/b.py"])
        assert n.impl_pointers == ["src/a.py::Cls.m (lines 1-5)", "src/b.py"]

    def test_legacy_string_coerces_to_single_entry(self):
        n = IntentNode(uid="X", name="x", intent="i", impl_pointers="src/a.py::Cls")
        assert n.impl_pointers == ["src/a.py::Cls"]

    def test_legacy_multiline_string_splits(self):
        n = IntentNode(uid="X", name="x", intent="i",
                       impl_pointers="src/a.py\nsrc/b.py\n")
        assert n.impl_pointers == ["src/a.py", "src/b.py"]

    def test_none_coerces_to_empty_list(self):
        n = IntentNode(uid="X", name="x", intent="i", impl_pointers=None)
        assert n.impl_pointers == []

    def test_empty_omitted_from_serialization(self):
        n = IntentNode(uid="X", name="x", intent="i")
        assert "impl_pointers" not in n.to_serial_dict()


class TestEffortIsFreeText:
    def test_string_accepted(self):
        n = IntentNode(uid="X", name="x", intent="i", effort="high correctness critical")
        assert n.effort == "high correctness critical"

    def test_int_assignment_rejected(self):
        n = IntentNode(uid="X", name="x", intent="i")
        with pytest.raises(ValidationError):
            n.effort = 3  # type: ignore[assignment]


class TestStrictUpdates:
    def test_unknown_node_field_raises(self):
        g = _graph()
        with pytest.raises(IntentGraphError, match="Unknown node field"):
            g.update_node("A", desing_notes="typo'd key")  # deliberate typo

    def test_unknown_link_field_raises(self):
        g = _graph()
        uid = next(iter(g.links))
        with pytest.raises(IntentGraphError, match="Unknown link field"):
            g.update_link(uid, shpae={"typo": True})  # deliberate typo

    def test_known_field_still_updates(self):
        g = _graph()
        g.update_node("A", design_notes="why this way")
        assert g.get_node("A").design_notes == "why this way"


class TestUnsetNodeFields:
    def test_scalar_resets_to_none(self):
        g = _graph()
        g.update_node("A", design_notes="temp", effort="best effort")
        g.unset_node_fields("A", ["design_notes", "effort"])
        node = g.get_node("A")
        assert node.design_notes is None
        assert node.effort is None

    def test_list_resets_to_empty(self):
        g = _graph()
        g.update_node("A", constraints=["c1"], impl_pointers=["src/a.py"])
        g.unset_node_fields("A", ["constraints", "impl_pointers"])
        node = g.get_node("A")
        assert node.constraints == []
        assert node.impl_pointers == []

    def test_required_field_cannot_be_unset(self):
        g = _graph()
        with pytest.raises(IntentGraphError, match="cannot be unset"):
            g.unset_node_fields("A", ["intent"])

    def test_history_cannot_be_unset(self):
        g = _graph()
        with pytest.raises(IntentGraphError, match="cannot be unset"):
            g.unset_node_fields("A", ["history"])


class TestLinkParentAtCreation:
    def test_add_link_accepts_parent(self):
        g = _graph()
        g.add_node("A.1", "A1", "sub")
        g.attach("A", "A.1")
        parent_uid = next(iter(g.links))  # ROOT_A
        child = g.add_link("ROOT", "A.1", "refined relation", parent=parent_uid)
        assert child.parent == parent_uid
