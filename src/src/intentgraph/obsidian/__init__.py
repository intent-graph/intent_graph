"""Obsidian vault import/export for IntentGraph.

Provides bidirectional synchronization between an IntentGraph object (the
single source of truth) and an Obsidian vault folder containing:

- ``nodes/*.md``  — one markdown file per intentnode (YAML frontmatter + wiki-links)
- ``edges.yaml``  — all intentlinks as a YAML list
- ``viz/*.canvas`` — Obsidian Canvas JSON files for each non-leaf node
- ``viz/__FT_ROOT.canvas`` — ROOT + all L1 + all descendants; ``viz/_FT_{L1}.canvas`` — one L1 expanded (leading _ so FT canvases sort to top)

Usage::

    from intentgraph.obsidian import export_to_obsidian, import_from_obsidian

    # Export: IntentGraph -> Obsidian vault
    export_to_obsidian(graph, output_dir="./my_vault")

    # Import: Obsidian vault -> IntentGraph
    graph = import_from_obsidian(vault_dir="./my_vault")

    # Diff: compare vault edits against a reference graph
    changes = diff_obsidian_vs_graph("./my_vault", reference_graph=graph)
"""

from intentgraph.obsidian._export import (
    apply_global_layout,
    compute_auto_layout,
    detect_canvas_pins,
    detect_pinned_positions,
    export_lens_canvas,
    export_to_obsidian,
    export_view_canvas,
    generate_full_tree_canvas,
    generate_portal_overview_canvas,
)
from intentgraph.obsidian._plugins import (
    PluginReport,
    ensure_vault_plugins,
    plugin_cache_dir,
    required_plugins,
)
from intentgraph.obsidian._radial import RadialConfig, compute_radial_layout
from intentgraph.obsidian._import import import_from_obsidian
from intentgraph.obsidian._diff import diff_obsidian_vs_graph
from intentgraph.obsidian._snapshot import (
    SNAPSHOT_FILENAME,
    graph_hash,
    load_snapshot,
    node_content_hash,
    write_snapshot,
)
from intentgraph.obsidian._merge import MergeReport, merge_obsidian_into_graph

__all__ = [
    "export_to_obsidian",
    "export_view_canvas",
    "export_lens_canvas",
    "generate_full_tree_canvas",
    "generate_portal_overview_canvas",
    "compute_auto_layout",
    "detect_canvas_pins",
    "detect_pinned_positions",
    "apply_global_layout",
    "compute_radial_layout",
    "RadialConfig",
    "import_from_obsidian",
    "diff_obsidian_vs_graph",
    "SNAPSHOT_FILENAME",
    "write_snapshot",
    "load_snapshot",
    "node_content_hash",
    "graph_hash",
    "merge_obsidian_into_graph",
    "MergeReport",
    "PluginReport",
    "ensure_vault_plugins",
    "plugin_cache_dir",
    "required_plugins",
]
