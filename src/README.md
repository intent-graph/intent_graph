# IntentGraph Core Library

Standalone Python library implementing the IntentGraph data model, Lens/View operations, and agent serialization — grounded in the [Phase 0 formalism](../foundation_and_formalism/VOCABULARY_AND_FORMALISM.md). Wire format specification: [SERIALIZATION_FORMAT.md](../foundation_and_formalism/SERIALIZATION_FORMAT.md).

## Quick Start
<!-- Lines 7-12 -->

```bash
cd src
uv run --extra dev pytest
```

## Usage
<!-- Lines 15-52 -->

```python
from intentgraph import IntentGraph, View
from intentgraph.ops.lens_ops import build_lens, promote, demote
from intentgraph.serial import view_to_text, text_to_edits, apply_edits
from intentgraph.serial import render_ascii_tree, print_tree
from intentgraph.serial import save_json, load_json

# Build a graph
g = IntentGraph(meta={"name": "ETL Pipeline"})
g.add_node("ROOT", "ETL System", "Extract-Transform-Load pipeline")
g.add_node_under("E", "Extract", "Data extraction", parent_uid="ROOT")
g.add_node_under("T", "Transform", "Data transformation", parent_uid="ROOT")
g.add_node_under("L", "Load", "Data loading", parent_uid="ROOT")
g.add_link("E", "T", "Extracted data flows to transformation")
g.add_link("T", "L", "Transformed data flows to loading")

# Quick ASCII visualization
print_tree(g, show_intent=True)

# A View is a uniform full-detail working set of nodes
view = View.from_depth(g, "top-level", depth=1)

# A Lens is a full-tree view with variable per-node LOD (skeleton < lean < full)
lens = build_lens(g, target_uid="T", budget=30, name="lens-demo")
promote(lens, "E")   # skeleton -> lean -> full
demote(lens, "E")    # full -> lean -> skeleton

# Serialize a View for agent I/O
text = view_to_text(view)         # YAML text an agent can read/modify
edits = text_to_edits(text, g)    # parse back into structured edits
apply_edits(g, edits)             # apply edits to the graph

# Persist
save_json(g, "my_graph.json")
g2 = load_json("my_graph.json")
```

## Package Structure
<!-- Lines 55-66 -->

```
src/intentgraph/
├── models/           # IntentNode, IntentLink, IntentGraph, View, Lens, LensConfig, NodeLayout
├── ops/              # iv_context (IV_ profile), projection (rep, project_links), lens_ops (build/promote/demote/focus/prune/expand/diff/apply)
├── serial/           # JSON/YAML round-trip, agent text format (View <-> text), graph overview, ascii_tree, lens_file I/O, intent_resources manifest
├── obsidian/         # Bidirectional Obsidian vault sync (export, import, diff, merge, canvas layout)
├── validation.py     # Lens validation (V-L1-V-L7, cross-IG V-CG1-V-CG4) and inter-intentlink checks
├── errors.py         # Domain exceptions (one per invariant violation)
└── _types.py         # Reusable constrained types (NonEmptyStr)
```

## Invariants Enforced
<!-- Lines 69-82 -->

| ID | Name | Where |
|----|------|-------|
| T1 | Tree property (treearcs form a directed rooted tree) | `IntentGraph.attach()` / `detach()` |
| T3 | Intentlink well-formedness (endpoints exist, descendant rule) | `IntentGraph.add_link()` |
| T4 | Refinement coherence (meaning-stability) | Semi-formal — logged for Critic agent review |
| C1 | Lens ancestor completeness (every displayed node's ancestors are displayed) | `LensConfig.add_node()` (by construction); validated by `validate_lenses()` (V-L3) |
| C3 | Lens link endpoint closure (both endpoints of a displayed link are displayed) | `LensConfig.add_link()` raises `ClosureViolation`; validated by `validate_lenses()` (V-L4) |

The former flat-antichain display concept and its bring-into-view / drop-from-view operation pair
are replaced by the Lens: a full-tree view where every node is always present, shown at a variable
Level of Detail, with ancestor- and link-closure enforced by construction (`LensConfig`) and
checked by `validate_lenses()`.

## Tests
<!-- Lines 85-98 -->

Tests cover:
- Model validation (node, link field constraints)
- Invariant enforcement (T1, T3)
- Query operators (parent, children, anc, desc, is_above, siblings)
- View construction and Lens operations (build, promote, demote, focus, prune/expand subtree, diff, apply, discard)
- Ilink projection (rep, lifting, dominance)
- JSON/YAML round-trip serialization
- Agent text format (serialize, parse, edit ops, round-trip, history, impl_pointers, auto history injection)
- Graph overview (tree overview, edge overview, view size estimation)
- ASCII tree visualization (simple/boxed styles, intent display, custom root, text wrapping)
- Obsidian export/import/diff/merge (format helpers, round-trip, canvas generation, pinned layout)
- Property-based tests (Hypothesis: random trees, random views, random projections)

## Example
<!-- Lines 101-106 -->

The `examples/` directory contains a full end-to-end demonstration — see [examples/README.md](examples/README.md) for what it is and how to run it. In short: it's an illustrative "SQL Function Sync Validator" (an invented tool), used here as a demonstration target for IntentGraph, built to exercise every library feature at once: graph construction, View navigation at 3 depth levels, Lens LOD navigation (promote/demote/focus/prune/expand), intentlink projection with lifting, agent text round-trip (serialize → modify → parse → apply edits), and JSON persistence.

- **`build_validator_graph.py`** — Builds the example IntentGraph (21 nodes, 19 intentlinks, 49 constraints across 3 depth levels).
- **`validator_graph.json`** — The persisted graph output (loadable via `load_json()`).

## Obsidian Sync
<!-- Lines 109-119 -->

The `intentgraph.obsidian` module provides bidirectional sync between an `IntentGraph` and an Obsidian vault:

- **Export** (`export_to_obsidian`): Graph -> `nodes/*.md` + `edges.yaml` + `viz/*.canvas`
- **Import** (`import_from_obsidian`): Obsidian vault -> `IntentGraph`
- **Diff** (`diff_obsidian_vs_graph`): Field-level structured diff between vault and reference graph
- **Merge** (`merge_obsidian_into_graph`): Apply vault edits back onto a reference graph
- **View / Lens canvas** (`export_view_canvas`, `export_lens_canvas`): Recursive ancestor-group algorithm — ancestors become visual groups, visible nodes become file references, intentlinks route to groups or nodes
- **Pinned layout** (`compute_auto_layout`, `detect_pinned_positions`): Positions are auto-computed by default. When a human moves nodes in Obsidian, `detect_pinned_positions` identifies user-moved nodes (vs auto). Pinned positions are stored sparsely and survive serialization round-trips.

Demo vault: `examples/validator_vault/` (open in Obsidian).
