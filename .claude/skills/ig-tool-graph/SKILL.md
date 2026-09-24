---
name: ig-tool-graph
description: >
  Reference for ig-tool graph lens commands — internal (graph-embedded) lens management.
  Use when creating, managing, or applying named persistent lenses stored inside the graph.
  See ig-tool-lens for the file-based lens (agent I/O mechanism).
user-invocable: false
---

# ig-tool — Graph Lens (Internal/Embedded Lens Management)

Internal lenses are **named, persistent views stored inside the graph file** (not separate files).
They differ from the file-based lens (`-l`): they live in the graph, survive across sessions, and support
canvas layout (x/y positions). Used for persistent named views, canvas exports, and round-trip to ProjectionIG.

Reference: `foundation_and_formalism/LENS_REDESIGN_SPEC.md` (internal lens design).

**Flag pattern for all `graph lens` operations:**
- `-g <graph>` — path to IG file (JSON or YAML)
- `--lens <name>` — internal lens name (required for most operations)
- `-o <output>` — output path (updated graph)

---

## Lens Lifecycle

### list — Show all internal lenses in a graph

```bash
ig-tool graph lens list -g graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `-g` | Yes | Graph file (JSON or YAML) |

Returns: names, descriptions, node counts, default flag.

---

### create — Create a new internal lens

```bash
ig-tool graph lens create -g graph.yaml --lens my-view --name "My View" --description "Focus on X" -o graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `-g` | Yes | Input graph |
| `--lens` | Yes | Internal name (machine identifier) |
| `--name` | No | Human-readable label |
| `--description` | No | Purpose description |
| `-o` | Yes | Updated graph output |

---

### delete — Remove an internal lens

```bash
ig-tool graph lens delete -g graph.yaml --lens my-view -o graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `-g` | Yes | Input graph |
| `--lens` | Yes | Lens to delete |
| `-o` | Yes | Updated graph output |

---

## Lens Content

### add-node — Add a node to an internal lens

```bash
ig-tool graph lens add-node -g graph.yaml --lens my-view --uid ROOT.1 --lod full -o graph.yaml
ig-tool graph lens add-node -g graph.yaml --lens my-view --uid ROOT.2 --lod lean --x 100 --y 200 -o graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `-g` | Yes | Input graph |
| `--lens` | Yes | Target internal lens |
| `--uid` | Yes | Node UID to add |
| `--lod` | No | `skeleton`, `lean`, or `full` (default: `skeleton`) |
| `--x`, `--y` | No | Canvas position (pixels) |
| `-o` | Yes | Updated graph output |

---

### remove-node — Remove a node from an internal lens

```bash
ig-tool graph lens remove-node -g graph.yaml --lens my-view --uid ROOT.1 -o graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `-g` | Yes | Input graph |
| `--lens` | Yes | Target internal lens |
| `--uid` | Yes | Node UID to remove |
| `-o` | Yes | Updated graph output |

---

### add-link — Add an intentlink to an internal lens

```bash
ig-tool graph lens add-link -g graph.yaml --lens my-view --uid ROOT.1_ROOT.2 -o graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `-g` | Yes | Input graph |
| `--lens` | Yes | Target internal lens |
| `--uid` | Yes | IntentLink UID |
| `-o` | Yes | Updated graph output |

---

### remove-link — Remove an intentlink from an internal lens

```bash
ig-tool graph lens remove-link -g graph.yaml --lens my-view --uid ROOT.1_ROOT.2 -o graph.yaml
```

---

### set-lod — Set LOD for a node in an internal lens

```bash
ig-tool graph lens set-lod -g graph.yaml --lens my-view --uid ROOT.1 --lod full -o graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `-g` | Yes | Input graph |
| `--lens` | Yes | Target internal lens |
| `--uid` | Yes | Node UID |
| `--lod` | Yes | `skeleton`, `lean`, or `full` |
| `-o` | Yes | Updated graph output |

---

## Canvas Layout

### set-position — Set canvas x/y for a node in an internal lens

```bash
ig-tool graph lens set-position -g graph.yaml --lens my-view --uid ROOT.1 --x 300 --y 150 -o graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `--x`, `--y` | Yes | Position in pixels |

---

### clear-position — Remove position override (revert to auto-layout)

```bash
ig-tool graph lens clear-position -g graph.yaml --lens my-view --uid ROOT.1 -o graph.yaml
```

---

## Default Selection

### set-default — Mark a lens as the default for this graph

```bash
ig-tool graph lens set-default -g graph.yaml --lens my-view -o graph.yaml
```

Only one lens can be default at a time. Used by `obsidian export-lens-canvas` when no lens is specified.

---

### unset-default — Remove default flag from a lens

```bash
ig-tool graph lens unset-default -g graph.yaml --lens my-view -o graph.yaml
```

---

## Round-Trip

### project — Export an internal lens to a standalone lens file

```bash
ig-tool graph lens project -g graph.yaml --lens my-view -o exported_lens.yaml
```

Produces a file-based lens (`-l` format) from the internal lens. Use when you need the file-based agent I/O flow (build → show → edit → diff → apply).

---

### reintegrate — Import a file-based lens back into the graph

```bash
ig-tool graph lens reintegrate -g graph.yaml --lens my-view -i updated_lens.yaml -o graph.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `-i` | Yes | Input lens file (file-based format) |
| `-m` / `--role` | No | Provenance: one-liner history note / agent role — reintegrated content changes auto-stamp a HistoryEntry at save |

Merges node LODs and canvas positions from the file-based lens back into the internal lens.

---

## Validation

### validate — Validate an internal lens for consistency

```bash
ig-tool graph lens validate -g graph.yaml --lens my-view
```

Checks: all node UIDs exist in graph, all link UIDs exist, no dangling positions. Exit code 1 if errors found.

---

## Inspection

### show — Display an internal lens contents

```bash
ig-tool graph lens show -g graph.yaml --lens my-view
ig-tool graph lens show -g graph.yaml --lens my-view -o lens_contents.yaml
```

Prints lens nodes (with LOD and position), included links, and metadata to stdout or `-o`. Does not write an updated graph.

---

## Common Mistakes

1. **Confusing `graph lens` with `lens`**: `lens` = file-based agent I/O (with `-l`). `graph lens` = internal named views (with `-g --lens`).
2. **Missing `--lens` on most operations**: All operations except `list` require `--lens`.
3. **`show` does not write `-o` to an updated graph**: `-o` on `show` writes the display output, not an updated graph.
4. **`project` produces a lens file, not an updated graph**: Use `reintegrate` to put changes back.
