"""Tests for the intentgraph.obsidian module — export, import, and diff.

Test strategy:
1. Round-trip: export a graph, import it back, verify structural equality.
2. Diff detection: export, modify files, run diff, verify changes detected.
3. Edge cases: empty graph, single-node graph, deeply nested graphs.
4. Example data: validator_graph.json round-trip.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.models.node import IntentNode
from intentgraph.obsidian import (
    diff_obsidian_vs_graph,
    export_to_obsidian,
    import_from_obsidian,
)
from intentgraph.obsidian._format import (
    LayoutConfig,
    compute_grid_positions,
    compute_group_size,
    edge_id,
    file_node_id,
    group_id,
    node_filename,
    node_stem,
    to_canvas_id,
    uid_from_stem,
)


# ------------------------------------------------------------------ #
#  Fixtures                                                          #
# ------------------------------------------------------------------ #

@pytest.fixture
def single_node_graph() -> IntentGraph:
    """A graph with a single root node (no children, no links)."""
    g = IntentGraph(meta={"name": "single"})
    g.add_node("ROOT", "Root Node", "The only node")
    return g


@pytest.fixture
def two_level_graph() -> IntentGraph:
    """Root + 3 children, 2 intentlinks. Simple but exercises all features."""
    g = IntentGraph(meta={"name": "two_level"})
    g.add_node("ROOT", "System", "Top-level system goal")
    g.add_node_under("A", "Module A", "Handles input", parent_uid="ROOT")
    g.add_node_under("B", "Module B", "Processes data", parent_uid="ROOT")
    g.add_node_under("C", "Module C", "Produces output", parent_uid="ROOT")
    g.add_link("A", "B", "A sends data to B")
    g.add_link("B", "C", "B sends results to C")
    return g


@pytest.fixture
def three_level_graph() -> IntentGraph:
    """3 levels with multiple children at each level, plus cross-links."""
    g = IntentGraph(meta={"name": "three_level"})
    g.add_node("ROOT", "Pipeline", "Data pipeline system")
    g.add_node_under("E", "Extract", "Extract data", parent_uid="ROOT")
    g.add_node_under("T", "Transform", "Transform data", parent_uid="ROOT")
    g.add_node_under("L", "Load", "Load data", parent_uid="ROOT")
    g.add_node_under("E.1", "Read CSV", "Parse CSV files", parent_uid="E")
    g.add_node_under("E.2", "Read JSON", "Parse JSON files", parent_uid="E")
    g.add_node_under("T.1", "Normalize", "Normalize fields", parent_uid="T")
    g.add_node_under("T.2", "Validate", "Validate records", parent_uid="T")
    g.add_node_under("L.1", "Stage", "Stage data", parent_uid="L")
    g.add_node_under("L.2", "Merge", "Merge into target", parent_uid="L")

    g.add_link("E", "T", "Extracted data flows to transform")
    g.add_link("T", "L", "Transformed data flows to load")
    g.add_link("E.1", "T.1", "CSV records for normalization")
    g.add_link("T.1", "T.2", "Normalized records for validation")
    g.add_link("T.2", "L.1", "Valid records to staging")
    g.add_link("L.1", "L.2", "Staged data to merge")
    return g


@pytest.fixture
def graph_with_all_fields() -> IntentGraph:
    """Graph using all node fields (epistemic_state, constraints, history, impl_pointers)."""
    g = IntentGraph(meta={"name": "full_fields"})
    g.add_node(
        "ROOT",
        "Full System",
        "A system with all fields populated",
        epistemic_state="known — well-tested",
        constraints=["Must be fast", "Must be reliable"],
        design_notes="Designed with care: handles edge cases well",
        examples=["Example 1: basic usage", "Example 2: advanced"],
        effort="High",
        impl_pointers=["src/main.py:entry_point"],
        history=[
            {"who": "remi", "date": "2026-01-15", "note": "Initial design"},
            {"who": "agent:extractor", "date": "2026-02-12", "note": "Refined"},
        ],
    )
    g.add_node_under(
        "A",
        "Sub Module",
        "A child module",
        parent_uid="ROOT",
        epistemic_state="risky — needs validation",
        constraints=["Max latency: 100ms"],
    )
    g.add_link("ROOT", "A", "Root oversees A")
    return g


@pytest.fixture
def graph_with_multiline_fields() -> IntentGraph:
    """Graph with multiline content in examples, constraints, and history note."""
    g = IntentGraph(meta={"name": "multiline"})
    multiline_example = "### Decision: Composite PK\n\nEntity: problems. PK: (topic_id, id).\n\n---"
    multiline_constraint = "All decisions must document\ntrade-offs and rejected alternatives."
    g.add_node(
        "ROOT",
        "Multiline Node",
        "Node with multiline fields",
        epistemic_state="known",
        constraints=[
            "Single-line constraint",
            multiline_constraint,
        ],
        examples=[
            "Single-line example",
            multiline_example,
        ],
        history=[
            {"who": "remi", "date": "2026-01-15", "note": "Line one.\nLine two.\nLine three."},
        ],
    )
    return g


# ------------------------------------------------------------------ #
#  Format helper tests                                               #
# ------------------------------------------------------------------ #

class TestFormatHelpers:
    """Tests for _format.py utility functions."""

    def test_node_filename_with_name(self):
        assert node_filename("IG.1", "Establish Foundation") == "IG.1 Establish Foundation.md"

    def test_node_filename_no_name(self):
        assert node_filename("IG.1", "") == "IG.1.md"

    def test_node_stem_with_name(self):
        assert node_stem("IG.1", "Establish Foundation") == "IG.1 Establish Foundation"

    def test_uid_from_stem_with_name(self):
        assert uid_from_stem("IG.1.1 Define Core Terms") == "IG.1.1"

    def test_uid_from_stem_uid_only(self):
        assert uid_from_stem("IG.1.1") == "IG.1.1"

    def test_grid_positions_3_cols(self):
        positions = compute_grid_positions(5)
        assert len(positions) == 5
        # First row: 3 nodes at y=300
        assert positions[0] == {"x": 300, "y": 300}
        assert positions[1] == {"x": 1200, "y": 300}
        assert positions[2] == {"x": 2100, "y": 300}
        # Second row: 2 nodes at y=1160
        assert positions[3] == {"x": 300, "y": 1160}
        assert positions[4] == {"x": 1200, "y": 1160}

    def test_group_size_matches_reference(self):
        """Verify group sizing matches the reference implementation."""
        # IG.canvas: 7 children -> width=3000, height=3080
        size = compute_group_size(7)
        assert size == {"width": 3000, "height": 3080}

        # IG.1.canvas: 4 children -> width=3000, height=2220
        size = compute_group_size(4)
        assert size == {"width": 3000, "height": 2220}

    # -- Canvas-id encoding (regression: underscore-in-UID collision) -----

    def test_canvas_id_legacy_dot_only_uids(self):
        """UIDs without underscores encode as before — backward compatible
        with existing canvas files (e.g. _implementation__LEGACY/viz/IG.*.canvas)."""
        assert to_canvas_id("ROOT") == "ROOT"
        assert to_canvas_id("IG.1.3") == "IG_1_3"
        assert to_canvas_id("ERRORS.HANDLER") == "ERRORS_HANDLER"

    def test_canvas_id_underscore_in_uid_is_doubled(self):
        """When a UID contains an underscore (allowed since the underscore-in-UID
        policy), encode the underscore by doubling so dot- and underscore-bearing
        UIDs do NOT collide. Without doubling, `LEXER_TOKENS` and `LEXER.TOKENS`
        would map to the same canvas id and silently overwrite each other in
        the export `id_to_uid` lookup table."""
        assert to_canvas_id("LEXER_TOKENS") == "LEXER__TOKENS"
        assert to_canvas_id("LEXER.PARSER_INTERFACE") == "LEXER_PARSER__INTERFACE"
        # The whole point: distinct UIDs must produce distinct canvas ids.
        assert to_canvas_id("LEXER_TOKENS") != to_canvas_id("LEXER.TOKENS")

    def test_canvas_id_helpers_compose_correctly(self):
        """group_id, file_node_id, edge_id all use to_canvas_id and inherit
        its bijective property."""
        assert group_id("LEXER.TOKENS") == "group_LEXER_TOKENS"
        assert file_node_id("LEXER_TOKENS") == "node_LEXER__TOKENS"
        assert edge_id("A.B", "C_D") == "edge_A_B_C__D"


# ------------------------------------------------------------------ #
#  Export tests                                                      #
# ------------------------------------------------------------------ #

class TestExport:
    """Tests for export_to_obsidian."""

    def test_creates_directory_structure(self, tmp_path, two_level_graph):
        export_to_obsidian(two_level_graph, tmp_path / "vault")
        vault = tmp_path / "vault"
        assert (vault / "nodes").is_dir()
        assert (vault / "viz").is_dir()
        assert (vault / "edges.yaml").is_file()

    def test_creates_node_files(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        nodes = list((vault / "nodes").glob("*.md"))
        assert len(nodes) == 4  # ROOT, A, B, C
        filenames = {f.name for f in nodes}
        assert "ROOT System.md" in filenames
        assert "A Module A.md" in filenames

    def test_node_has_frontmatter(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        content = (vault / "nodes" / "A Module A.md").read_text()
        assert content.startswith("---\n")
        assert "intent:" in content
        assert "Handles input" in content

    def test_root_has_down_and_contains(self, tmp_path, two_level_graph):
        # With --nav-links full, root keeps DOWN + CONTAINS and has no UP.
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault, nav_links="full")

        content = (vault / "nodes" / "ROOT System.md").read_text()
        assert "DOWN: [[ROOT.canvas|EXPLODE]]" in content
        assert "CONTAINS:" in content
        assert "[[A Module A]]" in content
        # Root should NOT have UP
        assert "UP:" not in content

    def test_full_leaf_has_up_only(self, tmp_path, two_level_graph):
        # --nav-links full: an L1 node (A) gets UP but no DOWN/CONTAINS (it's a leaf).
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault, nav_links="full")

        content = (vault / "nodes" / "A Module A.md").read_text()
        assert "UP: [[ROOT.canvas|ROOT]]" in content
        assert "DOWN:" not in content
        assert "CONTAINS:" not in content

    def test_minimal_nav_is_default(self, tmp_path, two_level_graph):
        # Default (--nav-links minimal): only L1 nodes carry an UP link, nothing else.
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        root = (vault / "nodes" / "ROOT System.md").read_text()
        assert "UP:" not in root and "DOWN:" not in root and "CONTAINS:" not in root

        a = (vault / "nodes" / "A Module A.md").read_text()  # A is L1
        assert "UP: [[ROOT.canvas|ROOT]]" in a
        assert "DOWN:" not in a and "CONTAINS:" not in a

    def test_creates_canvas_for_parent(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        canvas_path = vault / "viz" / "ROOT.canvas"
        assert canvas_path.is_file()
        canvas = json.loads(canvas_path.read_text())
        # Group + 3 children = 4 nodes
        assert len(canvas["nodes"]) == 4
        # 2 edges (A->B, B->C)
        assert len(canvas["edges"]) == 2

    def test_no_canvas_for_leaf(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        # Leaf nodes should not have canvas files
        assert not (vault / "viz" / "A.canvas").exists()
        assert not (vault / "viz" / "B.canvas").exists()

    def test_edges_yaml_structure(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        edges_data = yaml.safe_load((vault / "edges.yaml").read_text())
        assert isinstance(edges_data, list)

        treearcs = [e for e in edges_data if e.get("type") == "treearc"]
        intentlinks = [e for e in edges_data if e.get("type") == "intentlink"]

        # Treearcs record the tree: ROOT->A, ROOT->B, ROOT->C.
        assert {(e["from"], e["to"]) for e in treearcs} == {
            ("ROOT", "A"), ("ROOT", "B"), ("ROOT", "C"),
        }
        for e in treearcs:
            assert set(e) >= {"from", "to", "type"}

        # Intentlinks: A->B, B->C, each with intent.
        assert len(intentlinks) == 2
        for e in intentlinks:
            assert set(e) >= {"from", "to", "type", "intent"}

    def test_canvas_json_structure(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        canvas = json.loads((vault / "viz" / "ROOT.canvas").read_text())
        # Check group node
        group = canvas["nodes"][0]
        assert group["type"] == "group"
        assert group["label"] == "System"
        # Check file nodes
        file_nodes = [n for n in canvas["nodes"] if n["type"] == "file"]
        assert len(file_nodes) == 3
        for fn in file_nodes:
            assert fn["file"].startswith("nodes/")
            assert fn["file"].endswith(".md")

    def test_canvas_edge_format(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        canvas = json.loads((vault / "viz" / "ROOT.canvas").read_text())
        edge = canvas["edges"][0]
        assert "fromNode" in edge
        assert "toNode" in edge
        assert edge["fromSide"] == "right"
        assert edge["toSide"] == "left"
        assert "label" in edge

    def test_all_fields_in_frontmatter(self, tmp_path, graph_with_all_fields):
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_all_fields, vault)

        content = (vault / "nodes" / "ROOT Full System.md").read_text()
        assert "epistemic_state:" in content
        assert "known" in content
        assert "constraints:" in content
        assert "Must be fast" in content
        assert "history:" in content
        assert "remi" in content
        assert "impl_pointers:" in content
        assert "src/main.py" in content

    def test_empty_fields_omitted_from_frontmatter(self, tmp_path, three_level_graph):
        """Nodes with empty examples/history/constraints do not emit those keys (no clutter)."""
        vault = tmp_path / "vault"
        export_to_obsidian(three_level_graph, vault)

        # Leaf node with no examples, history, or constraints
        content = (vault / "nodes" / "E.1 Read CSV.md").read_text()
        assert "examples: []" not in content
        assert "history: []" not in content
        # constraints only appear when non-empty
        if "constraints:" in content:
            assert "constraints: []" not in content

    def test_multiline_examples_and_constraints_valid_yaml(self, tmp_path, graph_with_multiline_fields):
        """Multiline examples and constraints are emitted as literal blocks (valid YAML)."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_multiline_fields, vault)

        content = (vault / "nodes" / "ROOT Multiline Node.md").read_text()
        # Frontmatter must parse as valid YAML (no broken quoted strings)
        assert content.startswith("---\n")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert fm is not None
        assert "examples" in fm
        assert len(fm["examples"]) == 2
        assert "### Decision: Composite PK" in fm["examples"][1]
        assert "\n" in fm["examples"][1]
        assert "constraints" in fm
        assert "trade-offs" in fm["constraints"][1]
        assert "\n" in fm["constraints"][1]
        assert "history" in fm
        assert len(fm["history"]) == 1
        # YAML literal block may add trailing newline
        assert fm["history"][0]["note"].strip() == "Line one.\nLine two.\nLine three."

    def test_multiline_fields_roundtrip(self, tmp_path, graph_with_multiline_fields):
        """Export then import preserves multiline examples, constraints, and history note."""
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_multiline_fields, vault)
        imported = import_from_obsidian(vault)

        node = imported.get_node("ROOT")
        assert node is not None
        assert len(node.examples) == 2
        assert node.examples[0] == "Single-line example"
        assert "### Decision: Composite PK" in node.examples[1]
        assert "\n" in node.examples[1]
        # "---" in content is exported as " - - - " and unescaped on import
        assert node.examples[1].strip().endswith("---")

        assert len(node.constraints) == 2
        assert node.constraints[0] == "Single-line constraint"
        assert "trade-offs" in node.constraints[1]
        assert "\n" in node.constraints[1]

        assert len(node.history) == 1
        assert node.history[0].note.strip() == "Line one.\nLine two.\nLine three."

    def test_idempotent_export(self, tmp_path, three_level_graph):
        """Running export twice produces identical output."""
        vault1 = tmp_path / "vault1"
        vault2 = tmp_path / "vault2"
        export_to_obsidian(three_level_graph, vault1)
        export_to_obsidian(three_level_graph, vault2)

        # Compare all files
        for f1 in sorted(vault1.rglob("*")):
            if f1.is_dir():
                continue
            f2 = vault2 / f1.relative_to(vault1)
            assert f2.exists(), f"Missing in vault2: {f1.relative_to(vault1)}"
            assert f1.read_text() == f2.read_text(), (
                f"Content differs: {f1.relative_to(vault1)}"
            )

    def test_single_node_graph(self, tmp_path, single_node_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(single_node_graph, vault)

        nodes = list((vault / "nodes").glob("*.md"))
        assert len(nodes) == 1
        # Tree-overview canvases (FULL_TREE.canvas + __FT_ROOT.canvas)
        canvases = list((vault / "viz").glob("*.canvas"))
        assert len(canvases) == 2


# ------------------------------------------------------------------ #
#  Import tests                                                      #
# ------------------------------------------------------------------ #

class TestImport:
    """Tests for import_from_obsidian."""

    def test_import_recreates_nodes(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        imported = import_from_obsidian(vault)
        assert imported.node_count() == 4
        assert set(imported.nodes.keys()) == {"ROOT", "A", "B", "C"}

    def test_import_recreates_tree(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        imported = import_from_obsidian(vault)
        # Check tree structure
        root = imported.get_node("ROOT")
        assert root.parent_uid is None
        assert set(root.children_uids) == {"A", "B", "C"}

        child = imported.get_node("A")
        assert child.parent_uid == "ROOT"

    def test_import_recreates_links(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        imported = import_from_obsidian(vault)
        assert imported.link_count() == 2

    def test_import_preserves_content(self, tmp_path, graph_with_all_fields):
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_all_fields, vault)

        imported = import_from_obsidian(vault)
        root = imported.get_node("ROOT")
        assert "all fields populated" in root.intent
        assert root.epistemic_state is not None
        assert "well-tested" in root.epistemic_state
        assert len(root.constraints) == 2
        assert root.effort == "High"
        assert root.impl_pointers is not None
        assert any("src/main.py" in p for p in root.impl_pointers)

    def test_import_three_level_tree(self, tmp_path, three_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(three_level_graph, vault)

        imported = import_from_obsidian(vault)
        assert imported.node_count() == 10  # ROOT + E,T,L + E.1,E.2 + T.1,T.2 + L.1,L.2

        # Check level 2
        e = imported.get_node("E")
        assert set(e.children_uids) == {"E.1", "E.2"}

        # Check leaf
        e1 = imported.get_node("E.1")
        assert e1.parent_uid == "E"
        assert len(e1.children_uids) == 0


# ------------------------------------------------------------------ #
#  Round-trip tests                                                  #
# ------------------------------------------------------------------ #

class TestRoundTrip:
    """Export -> Import -> verify structural equality."""

    def _assert_graph_equal(self, original: IntentGraph, imported: IntentGraph) -> None:
        """Assert two graphs have the same structure and content."""
        assert original.node_count() == imported.node_count(), (
            f"Node count: {original.node_count()} vs {imported.node_count()}"
        )
        assert set(original.nodes.keys()) == set(imported.nodes.keys())

        for uid in original.nodes:
            orig_node = original.get_node(uid)
            imp_node = imported.get_node(uid)
            assert orig_node.name == imp_node.name, f"Name mismatch on {uid}"
            assert orig_node.intent.strip() == imp_node.intent.strip(), (
                f"Intent mismatch on {uid}"
            )
            assert orig_node.parent_uid == imp_node.parent_uid, (
                f"Parent mismatch on {uid}: {orig_node.parent_uid} vs {imp_node.parent_uid}"
            )
            assert set(orig_node.children_uids) == set(imp_node.children_uids), (
                f"Children mismatch on {uid}"
            )

        # Link count (UIDs may differ due to derivation, compare by src/dst/intent)
        orig_link_keys = {(l.src, l.dst) for l in original.iter_links()}
        imp_link_keys = {(l.src, l.dst) for l in imported.iter_links()}
        assert orig_link_keys == imp_link_keys, (
            f"Link keys differ: {orig_link_keys - imp_link_keys} extra in original, "
            f"{imp_link_keys - orig_link_keys} extra in imported"
        )

    def test_round_trip_two_level(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)
        imported = import_from_obsidian(vault)
        self._assert_graph_equal(two_level_graph, imported)

    def test_round_trip_three_level(self, tmp_path, three_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(three_level_graph, vault)
        imported = import_from_obsidian(vault)
        self._assert_graph_equal(three_level_graph, imported)

    def test_round_trip_single_node(self, tmp_path, single_node_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(single_node_graph, vault)
        imported = import_from_obsidian(vault)
        self._assert_graph_equal(single_node_graph, imported)

    def test_round_trip_deep_graph(self, tmp_path, deep_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(deep_graph, vault)
        imported = import_from_obsidian(vault)
        self._assert_graph_equal(deep_graph, imported)

    def test_round_trip_all_fields(self, tmp_path, graph_with_all_fields):
        vault = tmp_path / "vault"
        export_to_obsidian(graph_with_all_fields, vault)
        imported = import_from_obsidian(vault)
        self._assert_graph_equal(graph_with_all_fields, imported)

    def test_round_trip_validator_graph(self, tmp_path):
        """Round-trip the validator_graph.json example."""
        example_path = Path(__file__).parent.parent / "examples" / "validator_graph.json"
        if not example_path.exists():
            pytest.skip("validator_graph.json not found")

        from intentgraph.serial.json_yaml import load_json

        original = load_json(example_path)
        vault = tmp_path / "validator_vault"
        export_to_obsidian(original, vault)

        # Verify files were created
        nodes = list((vault / "nodes").glob("*.md"))
        assert len(nodes) == original.node_count()
        canvases = list((vault / "viz").glob("*.canvas"))
        # Canvases: one per non-leaf node + tree-overview canvases (FULL_TREE.canvas + __FT_ROOT.canvas)
        non_leaf_count = sum(
            1 for n in original.iter_nodes() if not n.is_leaf
        )
        # Filter out tree-overview canvases and compare
        per_node_canvases = [c for c in canvases if not c.stem.startswith("_") and c.stem != "FULL_TREE"]
        assert len(per_node_canvases) == non_leaf_count

        # Round-trip
        imported = import_from_obsidian(vault)
        self._assert_graph_equal(original, imported)


# ------------------------------------------------------------------ #
#  Diff tests                                                        #
# ------------------------------------------------------------------ #

class TestDiff:
    """Tests for diff_obsidian_vs_graph."""

    def test_no_changes(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        diff = diff_obsidian_vs_graph(vault, two_level_graph)
        assert not diff.has_changes
        assert diff.summary == "No changes"

    def test_detect_modified_intent(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        # Modify a node's intent in the vault
        node_file = vault / "nodes" / "A Module A.md"
        content = node_file.read_text()
        content = content.replace("Handles input", "Handles ALL input now")
        node_file.write_text(content)

        diff = diff_obsidian_vs_graph(vault, two_level_graph)
        assert diff.has_changes
        assert len(diff.nodes_modified) == 1
        mod = diff.nodes_modified[0]
        assert mod.uid == "A"
        intent_diff = [f for f in mod.changed_fields if f.field == "intent"]
        assert len(intent_diff) == 1
        assert "ALL input now" in intent_diff[0].new

    def test_detect_added_node(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        # Add a new node file
        new_file = vault / "nodes" / "D New Node.md"
        new_file.write_text(
            "---\nintent: |\n  A brand new node\ndesign_notes: |\n  Fresh.\n"
            "constraints: []\nexamples: []\neffort: Low\nhistory: []\n---\n"
        )

        diff = diff_obsidian_vs_graph(vault, two_level_graph)
        assert "D" in diff.nodes_added

    def test_detect_deleted_node(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        # Delete a node file
        (vault / "nodes" / "C Module C.md").unlink()

        diff = diff_obsidian_vs_graph(vault, two_level_graph)
        assert "C" in diff.nodes_deleted

    def test_detect_added_link(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        # Add a link to edges.yaml
        edges_file = vault / "edges.yaml"
        content = edges_file.read_text()
        content += (
            "- from: A\n"
            "  to: C\n"
            "  type: intentlink\n"
            "  intent: A also sends to C\n\n"
        )
        edges_file.write_text(content)

        diff = diff_obsidian_vs_graph(vault, two_level_graph)
        assert len(diff.links_added) == 1
        assert diff.links_added[0].src == "A"
        assert diff.links_added[0].dst == "C"

    def test_detect_deleted_link(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        # Remove all links from edges.yaml
        (vault / "edges.yaml").write_text("")

        diff = diff_obsidian_vs_graph(vault, two_level_graph)
        assert len(diff.links_deleted) == 2

    def test_diff_summary(self, tmp_path, two_level_graph):
        vault = tmp_path / "vault"
        export_to_obsidian(two_level_graph, vault)

        # Delete a node and modify another
        (vault / "nodes" / "C Module C.md").unlink()
        node_file = vault / "nodes" / "A Module A.md"
        content = node_file.read_text()
        content = content.replace("Handles input", "Changed intent")
        node_file.write_text(content)

        diff = diff_obsidian_vs_graph(vault, two_level_graph)
        assert "1 nodes deleted" in diff.summary
        assert "1 nodes modified" in diff.summary


# ------------------------------------------------------------------ #
#  Layout tests: NodeLayout, compute_auto_layout, pinned positions   #
# ------------------------------------------------------------------ #

from intentgraph.models.layout import NodeLayout
from intentgraph.models.view import View
from intentgraph.obsidian import compute_auto_layout, detect_pinned_positions, export_view_canvas


class TestNodeLayout:
    """Tests for the NodeLayout Pydantic model."""

    def test_create_with_defaults(self):
        nl = NodeLayout(x=100, y=200)
        assert nl.x == 100
        assert nl.y == 200
        assert nl.width == 600
        assert nl.height == 560

    def test_create_with_all_fields(self):
        nl = NodeLayout(x=10, y=20, width=300, height=250)
        assert nl.width == 300
        assert nl.height == 250

    def test_round_trip_dict(self):
        nl = NodeLayout(x=42, y=99, width=500, height=400)
        d = nl.model_dump()
        nl2 = NodeLayout(**d)
        assert nl == nl2


class TestComputeAutoLayout:
    """Tests for compute_auto_layout — the pure layout function."""

    def test_returns_all_visible_nodes(self, three_level_graph):
        """Auto layout should return positions for view nodes + ancestors."""
        v = View.from_node_set(three_level_graph, "test", {"E.1", "E.2", "T", "L"})
        # View: {E.1, E.2, T, L}
        # Ancestors: {E, ROOT}
        layout = compute_auto_layout(v)
        assert "E.1" in layout
        assert "E.2" in layout
        assert "T" in layout
        assert "L" in layout
        assert "E" in layout    # ancestor group
        assert "ROOT" in layout  # ancestor group

    def test_positions_are_integers(self, two_level_graph):
        v = View.from_node_set(two_level_graph, "test", {"A", "B", "C"})
        layout = compute_auto_layout(v)
        for uid, nl in layout.items():
            assert isinstance(nl.x, int)
            assert isinstance(nl.y, int)
            assert isinstance(nl.width, int)
            assert isinstance(nl.height, int)

    def test_is_deterministic(self, three_level_graph):
        """Same view produces identical layout every time."""
        v = View.from_node_set(three_level_graph, "test", {"E", "T", "L"})
        l1 = compute_auto_layout(v)
        l2 = compute_auto_layout(v)
        assert l1 == l2


class TestPinnedPositions:
    """Tests for detect_pinned_positions against an exported view canvas."""

    def test_detect_no_changes_returns_empty(self, tmp_path, two_level_graph):
        """If canvas matches auto layout, detect_pinned_positions returns empty."""
        v = View.from_node_set(two_level_graph, "test", {"A", "B", "C"})

        canvas_path = tmp_path / "test.canvas"
        export_view_canvas(v, canvas_path)

        pinned = detect_pinned_positions(v, canvas_path)
        assert pinned == {}

    def test_detect_moved_node(self, tmp_path, two_level_graph):
        """Moving a node in the canvas should be detected as pinned."""
        v = View.from_node_set(two_level_graph, "test", {"A", "B", "C"})

        canvas_path = tmp_path / "test.canvas"
        export_view_canvas(v, canvas_path)

        # Simulate user moving node A in Obsidian
        canvas = json.loads(canvas_path.read_text())
        for node in canvas["nodes"]:
            if node["id"] == "node_A":
                node["x"] = 9999
                node["y"] = 8888
        canvas_path.write_text(json.dumps(canvas))

        pinned = detect_pinned_positions(v, canvas_path)
        assert "A" in pinned
        assert pinned["A"].x == 9999
        assert pinned["A"].y == 8888

    def test_detect_respects_tolerance(self, tmp_path, two_level_graph):
        """Small movements within tolerance should NOT be detected as pinned."""
        v = View.from_node_set(two_level_graph, "test", {"A", "B", "C"})

        canvas_path = tmp_path / "test.canvas"
        export_view_canvas(v, canvas_path)

        # Simulate tiny Obsidian rounding — shift by 2 pixels
        canvas = json.loads(canvas_path.read_text())
        for node in canvas["nodes"]:
            if node["id"] == "node_A":
                node["x"] += 2
                node["y"] -= 1
        canvas_path.write_text(json.dumps(canvas))

        pinned = detect_pinned_positions(v, canvas_path, tolerance=5)
        assert "A" not in pinned

    def test_detect_moved_group(self, tmp_path, three_level_graph):
        """Moving a group (ancestor) should also be detected."""
        v = View.from_node_set(three_level_graph, "test", {"E.1", "E.2", "T", "L"})
        # View: {E.1, E.2, T, L}, Ancestors: {E, ROOT}

        canvas_path = tmp_path / "test.canvas"
        export_view_canvas(v, canvas_path)

        # Move the E group
        canvas = json.loads(canvas_path.read_text())
        for node in canvas["nodes"]:
            if node["id"] == "group_E":
                node["x"] = 7777
                node["y"] = 6666
        canvas_path.write_text(json.dumps(canvas))

        pinned = detect_pinned_positions(v, canvas_path)
        assert "E" in pinned
        assert pinned["E"].x == 7777


# ------------------------------------------------------------------ #
#  Fit-height: image-aware node sizing (--fit-height)               #
# ------------------------------------------------------------------ #

from PIL import Image

from intentgraph.obsidian._export import (
    _FIT_CONTENT_WIDTH,
    _FIT_IMAGE_CAPTION,
    _FIT_IMAGE_GAP,
    _FIT_IMAGE_MAX_H,
    _FIT_SECTION_HEADING,
    _apply_fit_height,
    _body_image_height,
    _format_samples,
    _image_render_height,
    estimate_node_height,
)


def _write_png(path: Path, width: int, height: int) -> Path:
    """Write a solid-colour PNG of the given pixel dimensions."""
    Image.new("RGB", (width, height), (128, 128, 128)).save(path)
    return path


class TestImageRenderHeight:
    """_image_render_height — scale a real image to the node content width."""

    def test_scales_to_content_width(self, tmp_path):
        # 520-wide content, source 1040x520 (2:1) -> scaled height 260.
        img = _write_png(tmp_path / "wide.png", 1040, 520)
        assert _image_render_height(img) == 260

    def test_square_image(self, tmp_path):
        # 400x400 square -> content-width height (520), but capped at max.
        img = _write_png(tmp_path / "sq.png", 400, 400)
        assert _image_render_height(img) == min(_FIT_IMAGE_MAX_H, _FIT_CONTENT_WIDTH)

    def test_tall_image_capped(self, tmp_path):
        # Very tall image: raw scaled height would exceed the cap.
        img = _write_png(tmp_path / "tall.png", 100, 2000)
        assert _image_render_height(img) == _FIT_IMAGE_MAX_H

    def test_missing_file_returns_zero(self, tmp_path):
        assert _image_render_height(tmp_path / "nope.png") == 0

    def test_undecodable_file_returns_zero(self, tmp_path):
        bad = tmp_path / "bad.png"
        bad.write_text("not an image")
        assert _image_render_height(bad) == 0


class TestBodyImageHeight:
    """_body_image_height — sum embed heights plus section chrome."""

    def test_no_embeds_is_zero(self, tmp_path):
        assert _body_image_height("Just text, no images.", tmp_path) == 0

    def test_single_embed(self, tmp_path):
        _write_png(tmp_path / "a.png", 1040, 520)  # renders to 260
        body = "## Samples\n\n![[a.png]]\n"
        expected = _FIT_SECTION_HEADING + _FIT_IMAGE_CAPTION + 260 + _FIT_IMAGE_GAP
        assert _body_image_height(body, tmp_path) == expected

    def test_multiple_embeds_accumulate(self, tmp_path):
        _write_png(tmp_path / "a.png", 1040, 520)  # 2:1 -> 260
        _write_png(tmp_path / "b.png", 520, 780)   # scaled 780, capped to max
        body = "![[a.png]]\n![[b.png]]\n"
        expected = (
            _FIT_SECTION_HEADING
            + (_FIT_IMAGE_CAPTION + 260 + _FIT_IMAGE_GAP)
            + (_FIT_IMAGE_CAPTION + _FIT_IMAGE_MAX_H + _FIT_IMAGE_GAP)
        )
        assert _body_image_height(body, tmp_path) == expected

    def test_non_image_embed_ignored(self, tmp_path):
        # A note transclusion is not an image; contributes no height.
        assert _body_image_height("![[SomeNote]]\n", tmp_path) == 0

    def test_broken_embed_adds_chrome_only(self, tmp_path):
        # Missing image still reserves heading + caption + gap, but 0 render px.
        body = "![[missing.png]]\n"
        expected = _FIT_SECTION_HEADING + _FIT_IMAGE_CAPTION + 0 + _FIT_IMAGE_GAP
        assert _body_image_height(body, tmp_path) == expected


class TestEstimateNodeHeightExtraBody:
    """estimate_node_height — extra_body_height threads through additively."""

    def test_extra_body_adds_exactly(self):
        node = IntentNode(uid="N", name="N", intent="short intent")
        base = estimate_node_height(node)
        assert estimate_node_height(node, extra_body_height=500) == base + 500

    def test_zero_extra_is_baseline(self):
        node = IntentNode(uid="N", name="N", intent="short intent")
        assert estimate_node_height(node, extra_body_height=0) == \
            estimate_node_height(node)


class TestFormatSamples:
    """_format_samples — render data_registry.samples as a ## Samples section."""

    def test_no_samples_is_empty(self):
        node = IntentNode(uid="N", name="N", intent="x")
        assert _format_samples(node) == ""

    def test_dict_sample_with_caption(self):
        node = IntentNode(
            uid="N", name="N", intent="x",
            data_registry={"samples": [{"path": "img/a.png", "caption": "A oak"}]},
        )
        out = _format_samples(node)
        assert out.startswith("## Samples")
        assert "**A oak**" in out
        assert "![[img/a.png]]" in out

    def test_string_sample_no_caption(self):
        node = IntentNode(
            uid="N", name="N", intent="x",
            data_registry={"samples": ["img/b.png"]},
        )
        out = _format_samples(node)
        assert "![[img/b.png]]" in out
        assert "**" not in out  # no caption emitted

    def test_multiple_samples(self):
        node = IntentNode(
            uid="N", name="N", intent="x",
            data_registry={"samples": [
                {"path": "img/a.png", "caption": "one"},
                {"path": "img/b.png"},
            ]},
        )
        out = _format_samples(node)
        assert "![[img/a.png]]" in out
        assert "![[img/b.png]]" in out
        assert out.endswith("\n")

    def test_skips_pathless_and_malformed(self):
        node = IntentNode(
            uid="N", name="N", intent="x",
            data_registry={"samples": [
                {"caption": "no path"},   # dropped: no path
                123,                       # dropped: wrong type
                {"path": "img/c.png"},     # kept
            ]},
        )
        out = _format_samples(node)
        assert "![[img/c.png]]" in out
        assert out.count("![[") == 1


class TestApplyFitHeight:
    """_apply_fit_height — canvas file-nodes resized to fitted content height."""

    def test_image_node_taller_than_plain_node(self, tmp_path):
        g = IntentGraph(meta={"name": "fit"})
        g.add_node("ROOT", "Root", "root intent")
        g.add_node_under("PLAIN", "Plain Node", "no images here", parent_uid="ROOT")
        g.add_node_under(
            "IMG", "Image Node", "has a sample",
            parent_uid="ROOT",
            data_registry={"samples": [{"path": "img/wide.png", "caption": "w"}]},
        )

        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()
        (tmp_path / "img").mkdir()
        _write_png(tmp_path / "img" / "wide.png", 1040, 520)
        # Write the IMG node's markdown so _apply_fit_height can read its body.
        img_node = g.get_node_or_none("IMG")
        (nodes_dir / node_filename("IMG", "Image Node")).write_text(
            _format_samples(img_node), encoding="utf-8",
        )

        canvas = json.dumps({"nodes": [
            {"id": "1", "type": "file", "file": "nodes/PLAIN Plain Node.md",
             "height": 560},
            {"id": "2", "type": "file", "file": "nodes/IMG Image Node.md",
             "height": 560},
            {"id": "3", "type": "group", "label": "grp", "height": 560},
        ]})

        out = json.loads(_apply_fit_height(
            canvas, g, nodes_dir=nodes_dir, vault_root=tmp_path,
        ))
        by_id = {n["id"]: n for n in out["nodes"]}
        # Image node is taller than the plain node by exactly the body height.
        plain_h = by_id["1"]["height"]
        img_h = by_id["2"]["height"]
        assert img_h > plain_h
        assert img_h - plain_h == _body_image_height(
            _format_samples(img_node), tmp_path,
        )
        # Group node is untouched.
        assert by_id["3"]["height"] == 560

    def test_without_dirs_no_image_measurement(self, tmp_path):
        g = IntentGraph(meta={"name": "fit"})
        g.add_node("ROOT", "Root", "root intent")
        canvas = json.dumps({"nodes": [
            {"id": "1", "type": "file", "file": "nodes/ROOT Root.md",
             "height": 560},
        ]})
        # No nodes_dir/vault_root -> falls back to frontmatter-only estimate.
        out = json.loads(_apply_fit_height(canvas, g))
        node = g.get_node_or_none("ROOT")
        assert out["nodes"][0]["height"] == estimate_node_height(node)
