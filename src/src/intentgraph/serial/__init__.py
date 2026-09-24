"""Serialization: JSON/YAML persistence, agent text format, graph overview, and ASCII tree rendering."""

from intentgraph.serial.json_yaml import (
    dict_to_graph,
    graph_to_dict,
    graph_to_json,
    graph_to_yaml,
    json_to_graph,
    load_graph,
    load_json,
    load_yaml,
    save_graph,
    save_json,
    save_yaml,
    yaml_to_graph,
)
from intentgraph.serial.agent_text import (
    EditOp,
    LinkCreate,
    LinkDelete,
    NodeCreate,
    NodeDelete,
    NodeUpdate,
    apply_edits,
    text_to_edits,
    view_to_text,
)
from intentgraph.serial.graph_overview import (
    graph_to_edge_overview,
    graph_to_structure,
    graph_to_tree_overview,
    view_text_size,
)
from intentgraph.serial.ascii_tree import (
    print_tree,
    render_ascii_tree,
    render_ascii_tree_boxed,
)
from intentgraph.serial.intent_resources import (
    load_manifest,
    resolve_graph_path,
    list_graph_ids,
)

__all__ = [
    # JSON/YAML
    "graph_to_dict",
    "dict_to_graph",
    "graph_to_json",
    "json_to_graph",
    "graph_to_yaml",
    "yaml_to_graph",
    "save_json",
    "load_json",
    "save_yaml",
    "load_yaml",
    "load_graph",
    "save_graph",
    # Agent text
    "view_to_text",
    "text_to_edits",
    "apply_edits",
    "EditOp",
    "NodeCreate",
    "NodeUpdate",
    "NodeDelete",
    "LinkCreate",
    "LinkDelete",
    # Graph overview
    "graph_to_tree_overview",
    "graph_to_edge_overview",
    "graph_to_structure",
    "view_text_size",
    # ASCII tree
    "render_ascii_tree",
    "render_ascii_tree_boxed",
    "print_tree",
    # Intent resources (manifest for inter intentlink resolution)
    "load_manifest",
    "resolve_graph_path",
    "list_graph_ids",
]
