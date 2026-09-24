"""Shared fixtures for IntentGraph tests.

Provides pre-built graphs at various sizes and shapes.
"""

import pytest

from intentgraph.models.graph import IntentGraph


@pytest.fixture
def empty_graph() -> IntentGraph:
    """An empty graph with no nodes."""
    return IntentGraph(meta={"name": "empty"})


@pytest.fixture
def tiny_graph() -> IntentGraph:
    """3 nodes (ROOT + 2 children), 1 intentlink.

    Structure::

        ROOT
        ├── A
        └── B

    Links: A -> B (data_exchange)
    """
    g = IntentGraph(meta={"name": "tiny"})
    g.add_node("ROOT", "Root", "System root")
    g.add_node_under("A", "Module A", "Handles A", parent_uid="ROOT")
    g.add_node_under("B", "Module B", "Handles B", parent_uid="ROOT")
    g.add_link("A", "B", "A sends data to B")
    return g


@pytest.fixture
def medium_graph() -> IntentGraph:
    """~15 nodes across 3 levels, ~8 intentlinks.

    Structure::

        ROOT
        ├── E  (Extract)
        │   ├── E.1
        │   ├── E.2
        │   └── E.3
        ├── T  (Transform)
        │   ├── T.1
        │   ├── T.2
        │   └── T.3
        └── L  (Load)
            ├── L.1
            ├── L.2
            └── L.3
            └── L.3.1
            └── L.3.2
    """
    g = IntentGraph(meta={"name": "medium_etl"})
    g.add_node("ROOT", "ETL System", "Extract-Transform-Load pipeline")

    # Level 1
    g.add_node_under("E", "Extract", "Data extraction", parent_uid="ROOT")
    g.add_node_under("T", "Transform", "Data transformation", parent_uid="ROOT")
    g.add_node_under("L", "Load", "Data loading", parent_uid="ROOT")

    # Level 2 — Extract
    g.add_node_under("E.1", "Parse CSV", "Parse CSV files", parent_uid="E")
    g.add_node_under("E.2", "Parse JSON", "Parse JSON files", parent_uid="E")
    g.add_node_under("E.3", "Validate", "Validate extracted data", parent_uid="E")

    # Level 2 — Transform
    g.add_node_under("T.1", "Normalize", "Normalize field formats", parent_uid="T")
    g.add_node_under("T.2", "Deduplicate", "Remove duplicate records", parent_uid="T")
    g.add_node_under("T.3", "Enrich", "Enrich with external data", parent_uid="T")

    # Level 2 — Load
    g.add_node_under("L.1", "Stage", "Stage in temp tables", parent_uid="L")
    g.add_node_under("L.2", "Merge", "Merge into target", parent_uid="L")
    g.add_node_under("L.3", "Audit", "Write audit log", parent_uid="L")

    # Level 3 — under L.3
    g.add_node_under("L.3.1", "Log Success", "Log successful loads", parent_uid="L.3")
    g.add_node_under("L.3.2", "Log Failure", "Log failed loads", parent_uid="L.3")

    # Intentlinks (cross-subtree relationships)
    g.add_link("E", "T", "Extracted data flows to transformation")
    g.add_link("T", "L", "Transformed data flows to loading")
    g.add_link("E.3", "T.1", "Validated records sent for normalization")
    g.add_link("T.1", "T.2", "Normalized records sent for dedup")
    g.add_link("T.2", "T.3", "Deduped records sent for enrichment")
    g.add_link("T.3", "L.1", "Enriched records staged")
    g.add_link("L.1", "L.2", "Staged data merged into target")
    g.add_link("L.2", "L.3", "Merge outcome triggers audit")

    return g


@pytest.fixture
def deep_graph() -> IntentGraph:
    """5 levels deep, narrow tree. For edge-case testing.

    Structure::

        ROOT
        └── A
            └── A.1
                └── A.1.1
                    └── A.1.1.1
                        └── A.1.1.1.1
    """
    g = IntentGraph(meta={"name": "deep"})
    g.add_node("ROOT", "Root", "Top level")
    g.add_node_under("A", "Level 1", "First level", parent_uid="ROOT")
    g.add_node_under("A.1", "Level 2", "Second level", parent_uid="A")
    g.add_node_under("A.1.1", "Level 3", "Third level", parent_uid="A.1")
    g.add_node_under("A.1.1.1", "Level 4", "Fourth level", parent_uid="A.1.1")
    g.add_node_under("A.1.1.1.1", "Level 5", "Fifth level", parent_uid="A.1.1.1")

    g.add_link("ROOT", "A.1.1.1.1", "Root cares about deepest node")
    return g


@pytest.fixture
def wide_graph() -> IntentGraph:
    """1 level, 20 children under ROOT. For frontier breadth testing."""
    g = IntentGraph(meta={"name": "wide"})
    g.add_node("ROOT", "Root", "Wide root")
    for i in range(1, 21):
        g.add_node_under(f"C{i}", f"Child {i}", f"Child number {i}", parent_uid="ROOT")
    # A few cross-links
    g.add_link("C1", "C2", "C1 feeds C2")
    g.add_link("C5", "C10", "C5 depends on C10")
    g.add_link("C10", "C20", "C10 triggers C20")
    return g
