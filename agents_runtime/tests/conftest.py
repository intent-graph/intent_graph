"""Shared fixtures for ig_agents tests."""

import pytest

from intentgraph.models.graph import IntentGraph
from intentgraph.models.view import View


@pytest.fixture
def sample_graph() -> IntentGraph:
    """Small ETL graph for testing agent infrastructure."""
    g = IntentGraph(meta={"name": "test_etl"})
    g.add_node("ROOT", "ETL System", "Extract-Transform-Load pipeline")
    g.add_node_under("E", "Extract", "Data extraction", parent_uid="ROOT")
    g.add_node_under("T", "Transform", "Data transformation", parent_uid="ROOT")
    g.add_node_under("L", "Load", "Data loading", parent_uid="ROOT")
    g.add_node_under("E.1", "Parse CSV", "Parse CSV files", parent_uid="E")
    g.add_node_under("E.2", "Parse JSON", "Parse JSON files", parent_uid="E")
    g.add_link("E", "T", "Extracted data flows to transformation")
    g.add_link("T", "L", "Transformed data flows to loading")
    return g


@pytest.fixture
def sample_view(sample_graph: IntentGraph) -> View:
    return View.from_node_set(sample_graph, "level1", {"E", "T", "L"})
