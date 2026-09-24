# IntentGraph Core Library — Example

This is an illustrative **"SQL Function Sync Validator"** (an invented tool), used here as a
demonstration target for IntentGraph. It models a small, self-contained tool that
compares the source of user-defined functions (UDFs) stored in a PostgreSQL database against
the source code tracked in a git repository, and reports drift (missing source, signature
mismatches, body differences). The example exists to exercise the `intentgraph` library
end-to-end on something with realistic shape — multiple depth levels, data-flow dependencies,
constraints, and design tradeoffs.

## Files
<!-- Lines 13-29 -->

- **`build_validator_graph.py`** — Builds the IntentGraph for the example (21 nodes, 19
  intentlinks, 49 constraints across 3 depth levels: ROOT → 5 capabilities → 15
  sub-capabilities) and runs it through the full library surface: graph construction, View
  navigation at 3 depth levels, Lens LOD navigation (promote/demote/focus/prune/expand),
  intentlink projection with lifting, an agent-text round-trip (serialize → modify → parse →
  apply edits), and JSON/YAML persistence.
- **`validator_graph.json`** — The persisted graph output of `build_validator_graph.py`,
  loadable via `intentgraph.serial.load_json()`. Regenerate it by re-running the script (see
  below) if you change `build_validator_graph.py`.
- **`validator_vault/`** — An Obsidian vault demonstrating the library's bidirectional Obsidian
  sync (`intentgraph.obsidian`): one markdown file per node under `nodes/`, an `edges.yaml`,
  and `.canvas` visualizations under `viz/`. Open the folder directly in Obsidian to browse it.
  Regenerated from `validator_graph.json` via `ig-tool obsidian export`, so its node filenames
  and cross-references use the current semantic UIDs (`ROOT`, `DISCOVER`, `PARSE`, `VALIDATE`,
  `REPORT`, `ORCHESTRATE`).

## Running it
<!-- Lines 32-39 -->

```bash
cd src
uv run python examples/build_validator_graph.py
```

This rebuilds the graph in memory, prints a walkthrough of every demo (View navigation,
Lens LOD navigation, projection, agent-text round-trip), and rewrites `validator_graph.json`.
