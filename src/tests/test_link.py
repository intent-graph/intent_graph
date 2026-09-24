"""Tests for IntentLink model."""

import pytest
from pydantic import ValidationError

from intentgraph.models.link import IntentLink


class TestIntentLink:

    def test_create_minimal(self):
        link = IntentLink(uid="A_B", src="A", dst="B", intent="A feeds B")
        assert link.uid == "A_B"
        assert link.src == "A"
        assert link.dst == "B"
        assert link.shape is None
        assert link.parent is None

    def test_create_with_shape_and_parent(self):
        link = IntentLink(
            uid="E.1.1_T.2.1",
            src="E.1.1",
            dst="T.2.1",
            intent="Passes validated records",
            shape={"type": "json", "schema": {"records": "list"}},
            parent="E_T",
        )
        assert link.shape["type"] == "json"
        assert link.parent == "E_T"

    def test_uid_empty_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            IntentLink(uid="", src="A", dst="B", intent="X")

    def test_src_empty_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            IntentLink(uid="x", src="", dst="B", intent="X")

    def test_dst_empty_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            IntentLink(uid="x", src="A", dst="", intent="X")

    def test_intent_empty_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            IntentLink(uid="x", src="A", dst="B", intent="")

    def test_derive_uid_simple(self):
        assert IntentLink.derive_uid("E.1", "T.2") == "E.1_T.2"

    def test_derive_uid_with_tag(self):
        assert IntentLink.derive_uid("E.1", "T.2", tag="auth") == "E.1_T.2#auth"

    def test_serial_round_trip(self):
        link = IntentLink(
            uid="E.3_L.1#data",
            src="E.3",
            dst="L.1",
            intent="Sends enriched data",
            shape={"protocol": "grpc"},
            parent="E_L",
        )
        d = link.to_serial_dict()
        link2 = IntentLink.from_serial_dict(d)
        assert link2.uid == link.uid
        assert link2.src == link.src
        assert link2.dst == link.dst
        assert link2.shape == link.shape
        assert link2.parent == link.parent

    def test_serial_dict_omits_none_optionals(self):
        link = IntentLink(uid="A_B", src="A", dst="B", intent="X")
        d = link.to_serial_dict()
        assert "shape" not in d
        assert "parent" not in d
