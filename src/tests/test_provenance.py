"""Write-boundary provenance capture (ops/provenance.py).

Contract under test (formalism §4, "Provenance capture"):
- one commit-style HistoryEntry per changed node at save, same message on all
- created / content-changed / reparented nodes stamp; untouched nodes don't
- history itself is excluded from the diff (no recursion)
- note: caller override wins, else auto diff summary
"""

from __future__ import annotations

from intentgraph.models.graph import IntentGraph
from intentgraph.ops.provenance import content_snapshot, stamp_provenance


def _graph() -> IntentGraph:
    g = IntentGraph()
    g.add_node("ROOT", "Root", "System root")
    g.add_node("A", "A", "Module A")
    g.add_node("B", "B", "Module B")
    g.attach("ROOT", "A")
    g.attach("ROOT", "B")
    return g


class TestStampProvenance:
    def test_untouched_graph_stamps_nothing(self):
        g = _graph()
        baseline = content_snapshot(g)
        stamped = stamp_provenance(g, baseline, who="remi")
        assert stamped == []
        assert all(not n.history for n in g.nodes.values())

    def test_content_change_stamps_only_changed_node(self):
        g = _graph()
        baseline = content_snapshot(g)
        g.update_node("A", intent="Updated intent", constraints=["c1"])
        stamped = stamp_provenance(g, baseline, who="agent:steward")
        assert stamped == ["A"]
        entry = g.get_node("A").history[-1]
        assert entry.who == "agent:steward"
        assert "intent" in entry.note and "constraints" in entry.note
        assert not g.get_node("B").history

    def test_created_node_stamps_created(self):
        g = _graph()
        baseline = content_snapshot(g)
        g.add_node("C", "C", "Module C")
        g.attach("ROOT", "C")
        stamped = stamp_provenance(g, baseline, who="remi")
        assert stamped == ["C"]
        assert g.get_node("C").history[-1].note == "created"

    def test_reparent_stamps_reparented(self):
        g = _graph()
        baseline = content_snapshot(g)
        g.detach("ROOT", "B")
        g.attach("A", "B", skip_uid_validation=True)
        stamped = stamp_provenance(g, baseline, who="remi")
        assert stamped == ["B"]
        assert "reparented" in g.get_node("B").history[-1].note

    def test_message_override_applies_to_all_changed_nodes(self):
        g = _graph()
        baseline = content_snapshot(g)
        g.update_node("A", intent="new A")
        g.update_node("B", intent="new B")
        stamp_provenance(g, baseline, who="remi", note="narrow scope per review")
        assert g.get_node("A").history[-1].note == "narrow scope per review"
        assert g.get_node("B").history[-1].note == "narrow scope per review"

    def test_history_append_is_not_a_change(self):
        g = _graph()
        g.get_node("A")  # ensure exists
        baseline = content_snapshot(g)
        from intentgraph.models.node import HistoryEntry
        g.get_node("A").history.append(
            HistoryEntry(who="remi", date="2026-07-15", note="manual")
        )
        stamped = stamp_provenance(g, baseline, who="remi")
        assert stamped == []

    def test_in_place_list_mutation_is_detected(self):
        # baseline deep-copies values, so aliasing cannot hide edits
        g = _graph()
        baseline = content_snapshot(g)
        g.get_node("A").constraints.append("sneaky in-place edit")
        stamped = stamp_provenance(g, baseline, who="remi")
        assert stamped == ["A"]

    def test_empty_baseline_stamps_everything_as_created(self):
        g = _graph()
        stamped = stamp_provenance(g, {}, who="remi via:obsidian")
        assert sorted(stamped) == ["A", "B", "ROOT"]
        assert g.get_node("ROOT").history[-1].who == "remi via:obsidian"

    def test_explicit_now_used_as_date(self):
        g = _graph()
        baseline = content_snapshot(g)
        g.update_node("A", intent="x")
        stamp_provenance(g, baseline, who="remi", now="2026-07-15T10:00")
        assert g.get_node("A").history[-1].date == "2026-07-15T10:00"
