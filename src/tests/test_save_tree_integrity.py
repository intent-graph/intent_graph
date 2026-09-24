"""Save-time orphan check (``_check_tree_integrity``).

A dotted UID with no parent is an orphan only when the UID-parent it names
exists in the graph. A prefix naming no node is a namespace: ``PIG-OBS.ROOT``
is a legitimate ProjectionIG root, and radial/portal Obsidian export must be
able to save layout back into such a graph.
"""

from pathlib import Path

import pytest

from intentgraph.errors import TreeInvariantViolation
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import load_graph, save_graph

PROJECTION_DIR = Path(__file__).resolve().parents[2] / "projection"


def test_namespaced_projection_root_saves(tmp_path):
    graph = load_graph(PROJECTION_DIR / "obsidian_defaults.ig.yaml")
    assert graph.get_node("PIG-OBS.ROOT").parent_uid is None
    save_graph(graph, tmp_path / "out.ig.yaml")  # must not raise


def test_unattached_child_of_existing_node_is_rejected(tmp_path):
    graph = IntentGraph()
    graph.add_node("ROOT", "Root", "Top-level goal")
    graph.add_node("API", "API", "Serve requests")
    graph.attach("ROOT", "API")
    graph.add_node("API.CLIENT", "Client", "Call the API")  # never attached
    with pytest.raises(TreeInvariantViolation, match="API.CLIENT"):
        save_graph(graph, tmp_path / "out.ig.yaml")
