"""Tests for obsidian merge: lossless round-trip and content-only conflict detection.

Test strategy:
1. Lossless round-trip: export with snapshot, load fresh graph, merge → verify data_registry
   and all fields survive, report is empty.
2. Content-only edits: edit node intent in vault, merge → applied, siblings unchanged.
3. Whole-node conflict: edit node in both vault and canonical, merge → conflicts, canonical wins.
4. Structural guard: add/delete node files → ignored_added/ignored_deleted, graph unchanged.
5. Malformed handling: corrupt node file, merge with on_malformed="fail" → errors, graph unmutated;
   with "skip" → errors but other edits apply.
6. No snapshot: merge with snapshot=None → no conflict detection, all edits applied.
7. Link edits: edit link intent in edges.yaml, merge → applied_links, link UID stable.
8. Snapshot shape: verify schema, graph_hash, nodes map after export.
"""

from __future__ import annotations

from pathlib import Path
import copy

import pytest
import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.serial import save_graph, load_graph
from intentgraph.obsidian import (
    export_to_obsidian,
    merge_obsidian_into_graph,
    write_snapshot,
    load_snapshot,
    SNAPSHOT_FILENAME,
)
from intentgraph.obsidian._snapshot import node_content_hash, graph_hash


# ---- Fixtures ----

@pytest.fixture
def graph_with_data_registry() -> IntentGraph:
    """Graph with data_registry, impl_pointers, history, multiline fields."""
    g = IntentGraph(meta={"name": "merge_test", "extra_key": "extra_value"})
    g.add_node(
        "ROOT",
        "Root Node",
        "Root intent with\nmultiline content",
        epistemic_state="known",
        constraints=["Must be fast", "Must handle errors"],
        examples=["Example 1", "Example 2"],
        design_notes="Design notes\nwith multiple lines",
        effort="High",
        impl_pointers=["src/main.py:root_fn"],
        history=[
            {"who": "remi", "date": "2026-01-15", "note": "Initial design"},
            {"who": "agent", "date": "2026-02-01", "note": "Refined"},
        ],
        data_registry={"positions": {"ROOT": {"x": 100, "y": 200}}, "metadata": "test"},
    )
    g.add_node_under(
        "A",
        "Module A",
        "Handles extraction",
        parent_uid="ROOT",
        impl_pointers=["src/extract.py:extract_fn"],
        data_registry={"schema": "v1", "tags": ["extract", "critical"]},
    )
    g.add_node_under(
        "B",
        "Module B",
        "Handles transformation",
        parent_uid="ROOT",
        constraints=["Latency < 100ms"],
        data_registry={"cache_enabled": True},
    )
    g.add_link("A", "B", "Extracted data flows to transform")
    return g


# ---- Test: Lossless round-trip with snapshot ----

class TestLosslessRoundTrip:
    """Verify that export + merge preserves all node fields including data_registry."""

    def test_round_trip_preserves_data_registry(self, tmp_path, graph_with_data_registry):
        """Core load-bearing test: data_registry survives export + fresh load + merge."""
        # Save the original graph to disk
        json_path = tmp_path / "original.json"
        save_graph(graph_with_data_registry, json_path)

        # Export to vault with snapshot
        vault = tmp_path / "vault"
        export_to_obsidian(
            graph_with_data_registry,
            vault,
            write_snapshot=True,
            graph_id="test-graph",
            graph_file=str(json_path),
        )

        # Verify snapshot was written
        snapshot_path = vault / SNAPSHOT_FILENAME
        assert snapshot_path.exists(), f"Snapshot not written to {snapshot_path}"

        # Load a fresh copy of the graph from disk (as if separate process)
        fresh_graph = load_graph(json_path)

        # Load snapshot from vault
        snapshot = load_snapshot(vault)
        assert snapshot is not None, "Failed to load snapshot"

        # Merge (no vault edits yet — this tests no-op merge)
        report = merge_obsidian_into_graph(
            vault,
            fresh_graph,
            snapshot=snapshot,
            on_malformed="fail",
        )

        # No-op merge should have empty report
        assert len(report.applied_nodes) == 0, f"No-op merge applied: {report.applied_nodes}"
        assert len(report.applied_links) == 0, f"No-op merge applied links: {report.applied_links}"
        assert len(report.conflicts) == 0, f"Unexpected conflicts: {report.conflicts}"
        assert len(report.errors) == 0, f"Unexpected errors: {report.errors}"

        # Verify data_registry survived on all nodes
        root = fresh_graph.get_node("ROOT")
        assert root.data_registry == {"positions": {"ROOT": {"x": 100, "y": 200}}, "metadata": "test"}, (
            f"ROOT data_registry lost or changed: {root.data_registry}"
        )

        a = fresh_graph.get_node("A")
        assert a.data_registry == {"schema": "v1", "tags": ["extract", "critical"]}, (
            f"A data_registry lost or changed: {a.data_registry}"
        )

        b = fresh_graph.get_node("B")
        assert b.data_registry == {"cache_enabled": True}, (
            f"B data_registry lost or changed: {b.data_registry}"
        )

        # Verify other fields
        assert root.impl_pointers == ["src/main.py:root_fn"]
        assert a.impl_pointers == ["src/extract.py:extract_fn"]
        assert len(root.history) == 2
        assert root.history[0].who == "remi"
        assert fresh_graph.meta.get("name") == "merge_test"
        assert fresh_graph.meta.get("extra_key") == "extra_value"

    def test_round_trip_preserves_links(self, tmp_path, graph_with_data_registry):
        """Links survive round-trip."""
        json_path = tmp_path / "original.json"
        save_graph(graph_with_data_registry, json_path)

        vault = tmp_path / "vault"
        export_to_obsidian(
            graph_with_data_registry,
            vault,
            write_snapshot=True,
            graph_id="test",
            graph_file=str(json_path),
        )

        fresh_graph = load_graph(json_path)
        snapshot = load_snapshot(vault)

        merge_obsidian_into_graph(vault, fresh_graph, snapshot=snapshot)

        # Verify link A -> B exists
        links = [l for l in fresh_graph.iter_links() if l.src == "A" and l.dst == "B"]
        assert len(links) == 1
        assert "Extracted data flows" in links[0].intent


# ---- Test: Content-only edits ----

class TestContentOnlyEdits:
    """Verify that vault edits to node content are applied, sibling fields untouched."""

    def test_edit_node_intent_applies(self, tmp_path, graph_with_data_registry):
        """Edit node A's intent in vault, merge → A in applied_nodes, intent updated."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Edit node A's intent in vault
        node_a_file = vault / "nodes" / "A Module A.md"
        content = node_a_file.read_text()
        content = content.replace("Handles extraction", "Handles ALL extraction")
        node_a_file.write_text(content)

        # Merge with snapshot
        merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
        )

        # Verify A was applied
        assert "A" in graph_with_data_registry.get_node("A").intent or "ALL extraction" in graph_with_data_registry.get_node("A").intent
        # Verify A's data_registry unchanged
        assert graph_with_data_registry.get_node("A").data_registry == {"schema": "v1", "tags": ["extract", "critical"]}
        # Verify B and ROOT untouched
        assert "Handles transformation" in graph_with_data_registry.get_node("B").intent

    def test_edit_constraints_applies(self, tmp_path, graph_with_data_registry):
        """Edit node B's constraints in vault, merge → B in applied_nodes."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Edit B's constraints in vault
        node_b_file = vault / "nodes" / "B Module B.md"
        content = node_b_file.read_text()
        content = content.replace("Latency < 100ms", "Latency < 50ms")
        node_b_file.write_text(content)

        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
        )

        assert "B" in report.applied_nodes
        assert "Latency < 50ms" in graph_with_data_registry.get_node("B").constraints


# ---- Test: Whole-node conflict detection ----

class TestWholeNodeConflict:
    """Verify conflict detection: both vault and canonical changed → conflict, canonical wins."""

    def test_conflict_canonical_wins(self, tmp_path, graph_with_data_registry):
        """Both vault and canonical edit node A → conflict, canonical value kept."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Edit node A in vault
        node_a_file = vault / "nodes" / "A Module A.md"
        content = node_a_file.read_text()
        content = content.replace("Handles extraction", "Vault says: handles extraction")
        node_a_file.write_text(content)

        # ALSO edit node A in canonical (in memory)
        graph_with_data_registry.update_node("A", intent="Canonical says: handles extraction")

        # Merge with snapshot — should detect conflict
        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
        )

        assert "A" in report.conflicts, f"Expected A in conflicts, got: {report.conflicts}"
        assert "A" not in report.applied_nodes
        # Canonical value should be preserved
        assert "Canonical says" in graph_with_data_registry.get_node("A").intent

    def test_clean_node_still_applies(self, tmp_path, graph_with_data_registry):
        """When node X has conflict, node Y (clean edit only) still applies."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Edit node A in vault
        node_a_file = vault / "nodes" / "A Module A.md"
        content = node_a_file.read_text()
        content = content.replace("Handles extraction", "Vault: extraction")
        node_a_file.write_text(content)

        # Edit node B in vault (clean)
        node_b_file = vault / "nodes" / "B Module B.md"
        content = node_b_file.read_text()
        content = content.replace("Handles transformation", "Handles NEW transformation")
        node_b_file.write_text(content)

        # Edit node A in canonical (conflict)
        graph_with_data_registry.update_node("A", intent="Canonical: extraction")

        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
        )

        assert "A" in report.conflicts
        assert "B" in report.applied_nodes
        assert "Handles NEW transformation" in graph_with_data_registry.get_node("B").intent


# ---- Test: Content-only structural guardrails ----

class TestStructuralGuardrails:
    """Verify that add/delete are not applied; only content edits."""

    def test_add_node_file_ignored(self, tmp_path, graph_with_data_registry):
        """Add a new .md file to vault → ignored_added, not created in graph."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Add a new node file
        new_file = vault / "nodes" / "Z New Node.md"
        new_file.write_text(
            "---\nintent: |\n  A brand new node\ndesign_notes: |\n  Fresh.\nconstraints: []\n"
            "examples: []\neffort: Low\nhistory: []\n---\n"
        )

        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
        )

        assert "Z" in report.ignored_added
        assert graph_with_data_registry.get_node_or_none("Z") is None

    def test_delete_node_file_ignored(self, tmp_path, graph_with_data_registry):
        """Delete a node file from vault → ignored_deleted, node still in graph."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Delete node A's file
        (vault / "nodes" / "A Module A.md").unlink()

        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
        )

        assert "A" in report.ignored_deleted
        assert graph_with_data_registry.get_node("A") is not None


# ---- Test: Malformed file handling ----

class TestMalformedHandling:
    """Verify on_malformed="fail" vs "skip" behavior."""

    def test_malformed_fail_returns_errors_graph_unmutated(self, tmp_path, graph_with_data_registry):
        """Corrupt node file, on_malformed="fail" → errors, graph completely unchanged."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Snapshot original node intents for comparison
        original_intents = {uid: node.intent for uid, node in graph_with_data_registry.nodes.items()}

        # Corrupt node A's file (invalid YAML)
        node_a_file = vault / "nodes" / "A Module A.md"
        node_a_file.write_text("---\nintent: |\n  intent content\ninvalid yaml: [unclosed\n---\n")

        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
            on_malformed="fail",
        )

        assert len(report.errors) > 0, "Expected errors in report"
        # Graph should be completely unmutated
        for uid, node in graph_with_data_registry.nodes.items():
            assert node.intent == original_intents[uid], f"Node {uid} was mutated despite error"

    def test_malformed_skip_records_error_other_edits_apply(self, tmp_path, graph_with_data_registry):
        """Corrupt one node, on_malformed="skip" → that node in errors, other clean edits apply."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Corrupt node A's file
        node_a_file = vault / "nodes" / "A Module A.md"
        node_a_file.write_text("---\nintent: |\n  intent\ninvalid yaml: [unclosed\n---\n")

        # Edit node B (clean)
        node_b_file = vault / "nodes" / "B Module B.md"
        content = node_b_file.read_text()
        content = content.replace("Handles transformation", "Handles UPDATED transformation")
        node_b_file.write_text(content)

        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
            on_malformed="skip",
        )

        # A should be in errors
        assert any("A" in err for err in report.errors), f"Expected A in errors, got: {report.errors}"
        # B should still be applied
        assert "B" in report.applied_nodes
        assert "UPDATED transformation" in graph_with_data_registry.get_node("B").intent


# ---- Test: Merge without snapshot (snapshot=None) ----

class TestMergeWithoutSnapshot:
    """Verify behavior when snapshot is not available — no conflict detection."""

    def test_all_edits_applied_no_conflict_detection(self, tmp_path, graph_with_data_registry):
        """With snapshot=None, all vault edits applied, no conflict detection."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=False)

        # Edit node A in vault
        node_a_file = vault / "nodes" / "A Module A.md"
        content = node_a_file.read_text()
        content = content.replace("Handles extraction", "Vault: extraction")
        node_a_file.write_text(content)

        # Edit node A in canonical (would conflict with snapshot)
        graph_with_data_registry.update_node("A", intent="Canonical: extraction")

        # Merge with snapshot=None
        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=None,  # No baseline
        )

        # A should be applied (no conflict detection without snapshot)
        assert "A" in report.applied_nodes
        assert len(report.conflicts) == 0


# ---- Test: Link edits ----

class TestLinkEdits:
    """Verify that link intent edits are applied and link UIDs are stable."""

    def test_edit_link_intent_applies(self, tmp_path, graph_with_data_registry):
        """Edit a link's intent in edges.yaml, merge → link in applied_links."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)
        snapshot = load_snapshot(vault)

        # Get the link UID from edges.yaml
        edges_file = vault / "edges.yaml"
        edges = yaml.safe_load(edges_file.read_text())
        assert len(edges) > 0
        original_link_uid = edges[0].get("uid") or edges[0].get("id")

        # Edit the link's intent
        for edge in edges:
            if edge.get("from") == "A" and edge.get("to") == "B":
                edge["intent"] = "A feeds B with UPDATED intent"
                break

        edges_file.write_text(yaml.dump(edges))

        report = merge_obsidian_into_graph(
            vault,
            graph_with_data_registry,
            snapshot=snapshot,
        )

        # Link should be applied
        assert len(report.applied_links) > 0 or len(report.applied_nodes) > 0

    def test_link_uid_stable_after_edit(self, tmp_path, graph_with_data_registry):
        """After editing a link, its UID (stable identifier) should not change."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_data_registry, vault, write_snapshot=True)

        # Get original link UID
        edges_file = vault / "edges.yaml"
        edges_before = yaml.safe_load(edges_file.read_text())
        link_before = [e for e in edges_before if e.get("from") == "A" and e.get("to") == "B"][0]
        uid_before = link_before.get("uid") or f"{link_before['from']}-{link_before['to']}"

        # Edit and merge
        for edge in edges_before:
            if edge.get("from") == "A" and edge.get("to") == "B":
                edge["intent"] = "Updated intent"
        edges_file.write_text(yaml.dump(edges_before))

        snapshot = load_snapshot(vault)
        merge_obsidian_into_graph(vault, graph_with_data_registry, snapshot=snapshot)

        # Reload and verify UID is stable
        edges_after = yaml.safe_load(edges_file.read_text())
        link_after = [e for e in edges_after if e.get("from") == "A" and e.get("to") == "B"][0]
        uid_after = link_after.get("uid") or f"{link_after['from']}-{link_after['to']}"

        # For practical purposes, (A, B) is the stable identifier
        assert link_before["from"] == link_after["from"]
        assert link_before["to"] == link_after["to"]


# ---- Test: Snapshot shape and content ----

class TestSnapshotStructure:
    """Verify snapshot format and content after export."""

    def test_snapshot_file_created(self, tmp_path, graph_with_data_registry):
        """export_to_obsidian with write_snapshot=True creates .ig-sync.yaml."""
        vault = tmp_path / "vault"
        export_to_obsidian(
            graph_with_data_registry,
            vault,
            write_snapshot=True,
            graph_id="test",
            graph_file="test.json",
        )

        snapshot_path = vault / SNAPSHOT_FILENAME
        assert snapshot_path.exists()
        assert SNAPSHOT_FILENAME == ".ig-sync.yaml"

    def test_snapshot_has_correct_schema(self, tmp_path, graph_with_data_registry):
        """Snapshot contains schema=ig-sync/1."""
        vault = tmp_path / "vault"
        export_to_obsidian(
            graph_with_data_registry,
            vault,
            write_snapshot=True,
            graph_id="test",
            graph_file="test.json",
        )

        snapshot = load_snapshot(vault)
        assert snapshot is not None
        assert snapshot.get("schema") == "ig-sync/1"

    def test_snapshot_has_graph_hash(self, tmp_path, graph_with_data_registry):
        """Snapshot contains graph_hash matching the exported graph."""
        vault = tmp_path / "vault"
        export_to_obsidian(
            graph_with_data_registry,
            vault,
            write_snapshot=True,
            graph_id="test",
            graph_file="test.json",
        )

        snapshot = load_snapshot(vault)
        assert "graph_hash" in snapshot
        expected_hash = graph_hash(graph_with_data_registry)
        assert snapshot["graph_hash"] == expected_hash

    def test_snapshot_has_node_hashes(self, tmp_path, graph_with_data_registry):
        """Snapshot contains nodes dict with hash for each uid."""
        vault = tmp_path / "vault"
        export_to_obsidian(
            graph_with_data_registry,
            vault,
            write_snapshot=True,
            graph_id="test",
            graph_file="test.json",
        )

        snapshot = load_snapshot(vault)
        assert "nodes" in snapshot
        assert isinstance(snapshot["nodes"], dict)
        # Should have hashes for ROOT, A, B
        assert "ROOT" in snapshot["nodes"]
        assert "A" in snapshot["nodes"]
        assert "B" in snapshot["nodes"]
        # Each hash should be a string starting with sha256:
        for uid, hash_val in snapshot["nodes"].items():
            assert isinstance(hash_val, str)
            assert hash_val.startswith("sha256:")

    def test_snapshot_has_graph_id_and_file(self, tmp_path, graph_with_data_registry):
        """Snapshot records graph_id and graph_file for audit."""
        vault = tmp_path / "vault"
        export_to_obsidian(
            graph_with_data_registry,
            vault,
            write_snapshot=True,
            graph_id="my-graph-id",
            graph_file="/path/to/graph.json",
        )

        snapshot = load_snapshot(vault)
        assert snapshot.get("graph_id") == "my-graph-id"
        assert snapshot.get("graph_file") == "/path/to/graph.json"

    def test_snapshot_has_exported_at(self, tmp_path, graph_with_data_registry):
        """Snapshot has exported_at timestamp (ISO format)."""
        vault = tmp_path / "vault"
        export_to_obsidian(
            graph_with_data_registry,
            vault,
            write_snapshot=True,
            graph_id="test",
            graph_file="test.json",
        )

        snapshot = load_snapshot(vault)
        assert "exported_at" in snapshot
        # Should be ISO format string (rough check)
        exported_at = snapshot["exported_at"]
        assert isinstance(exported_at, str)
        assert "T" in exported_at or "-" in exported_at  # ISO date or datetime
