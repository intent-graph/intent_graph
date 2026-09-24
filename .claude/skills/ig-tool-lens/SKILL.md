---
name: ig-tool-lens
description: >
  Reference for ig-tool lens commands — the primary agent I/O mechanism.
  Use when building, navigating, editing, or applying a Lens view of the IntentGraph.
user-invocable: false
---

# ig-tool — Lens (Agent I/O)

The Lens is the primary way agents interact with an IntentGraph. It provides a full-tree view with per-node Level of Detail (LOD), change tracking, and git-like apply/discard semantics.

## Key Concepts

- **Lens file** (`-l`): YAML or JSON — the working copy. Separate from the source graph (`-g`).
- **LOD levels**: `skeleton` (uid+name) < `lean` (uid+name+intent+epistemic_state) < `full` (all fields)
- **IV assignment**: target + direct neighbors = `full`, ancestors = `lean`, L1 brim = `lean`, rest = `skeleton`
- **Budget** (`-b`): token estimate in thousands (e.g., `-b 30` = 30,000 tokens)
- **Change tracking**: edits are staged in the lens, then diff/apply/discard against the source graph

## Lifecycle

```
build → show/tree → [focus/promote/demote/set-lod/prune/expand] → diff → apply
                                                                       → discard
```

1. **Build** a lens from a target node
2. **Show/tree** to render agent-readable output
3. **Reshape** (focus, promote, demote, prune, expand) as needed
4. **Diff** to see staged changes
5. **Apply** to commit to graph, or **discard** to revert

## Critical Flag Pattern

- **`-l`** = lens file (input/output for lens operations)
- **`-g`** = source graph file (JSON or YAML; needed for operations that look up the graph: build, focus, expand, set-budget, diff, apply)
- **`-o`** = output file (for build, show, and any command that writes a new file)

Many commands read `-l` and write back to `-o` (often the same file). Some need `-g` too.

---

## build — Create a lens

```bash
ig-tool lens build -g graph.json -t TARGET_UID -b 30 -o lens.yaml
```

| Flag | Meaning | Required |
|------|---------|----------|
| `-g` | Source graph JSON | Yes |
| `-t` | Target node UID | Yes |
| `-b` | Token budget in thousands | No (default: 30) |
| `-o` | Output lens YAML | Yes |

## show — Render to agent-readable YAML

```bash
ig-tool lens show -l lens.yaml -o agent_view.yaml
```

Serializes the lens with full/lean/skeleton detail per node. This is what agents read.

## tree — ASCII tree with LOD annotations

```bash
ig-tool lens tree -l lens.yaml
```

Prints to stdout. Shows LOD per node:
```
ROOT (skeleton)
├── D (full)
│   ├── D.1 (lean)
│   └── D.2 (lean)
└── E (skeleton)
```

## info — Lens metadata and statistics

```bash
ig-tool lens info -l lens.yaml
```

Returns: target, budget, node counts by LOD, link count, pending changes count.

---

## Reshaping Commands

### focus — Change target node

```bash
ig-tool lens focus -l lens.yaml -g graph.json --uid NEW_TARGET -o lens.yaml
```

Shifts focus. Pending edits are retained. LOD is recomputed around new target.
**Needs `-g`** for neighbor lookup.

### promote — Increase LOD (e.g., skeleton → lean → full)

```bash
ig-tool lens promote -l lens.yaml --uid NODE_UID -o lens.yaml
```

### demote — Decrease LOD

```bash
ig-tool lens demote -l lens.yaml --uid NODE_UID -o lens.yaml
```

### set-lod — Set LOD explicitly

```bash
ig-tool lens set-lod -l lens.yaml --uid NODE_UID --lod full -o lens.yaml
```

Values: `skeleton`, `lean`, `full`.

### prune — Remove a subtree from the lens

```bash
ig-tool lens prune -l lens.yaml --uid SUBTREE_ROOT -o lens.yaml
```

Excludes the node and all descendants. Use `list-pruned` to see what's pruned.

### expand — Add children into the lens

```bash
ig-tool lens expand -l lens.yaml -g graph.json --uid NODE_UID --depth 1 -o lens.yaml
```

**Needs `-g`** for child lookup. `--depth` controls how many levels (default: 1).

### set-budget — Change token budget

```bash
ig-tool lens set-budget -l lens.yaml -g graph.json -b 15 -o lens.yaml
```

Auto-demotes nodes to fit if reducing. **Needs `-g`**.

### list-pruned — Show pruned nodes

```bash
ig-tool lens list-pruned -l lens.yaml
```

---

## Staging Commands

### diff — Compare lens against source graph

```bash
ig-tool lens diff -l lens.yaml -g graph.json -o diff.yaml
```

Outputs §5 diff format. Shows node creates/updates/deletes, link creates/updates/deletes.

### apply — Commit lens changes to graph

```bash
ig-tool lens apply -l lens.yaml -g graph.json -o updated_graph.json
```

| Flag | Meaning |
|------|---------|
| `-l` | Input lens YAML |
| `-g` | Source graph JSON |
| `-o` | Updated graph JSON (**required, never overwrites `-g`**) |
| `--role` | Agent role for provenance (`who: agent:<role>`) |
| `-m` | One-liner history note (commit-style; omitted → auto diff summary) |

**IMPORTANT:** `-o` is required and must differ from `-g` conceptually (the original is never overwritten by the tool itself).

**Provenance:** the save stamps a HistoryEntry on every changed node automatically (write-boundary). `--dry-run` is still NOT a `lens apply` flag — it belongs on `ig-tool apply`.

### discard — Revert all pending changes

```bash
ig-tool lens discard -l lens.yaml -o lens.yaml
```

Resets lens to match source graph state.

---

## Common Mistakes

1. **Forgetting `-g` on commands that need it**: `build`, `focus`, `expand`, `set-budget`, `diff`, `apply` all need the source graph.
2. **Using `-g` where only `-l` is needed**: `show`, `tree`, `info`, `promote`, `demote`, `set-lod`, `prune`, `list-pruned`, `discard` work from the lens alone.
3. **Confusing `show` and `tree`**: `show` produces machine-readable YAML (for agent consumption). `tree` produces human-readable ASCII (for orientation).
4. **Forgetting `--uid`**: All node-targeting reshaping commands need `--uid`.
