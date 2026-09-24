---
name: ig-tool-obsidian
description: >
  Reference for ig-tool obsidian commands: export, import, merge, diff, export-canvas,
  export-tree, export-lens-canvas, detect-pins. Use when syncing an IntentGraph
  with an Obsidian vault (export = IG→vault; merge = vault→IG, two-way).
user-invocable: false
---

# ig-tool — Obsidian Vault Sync

Bidirectional sync between IntentGraph and Obsidian markdown vaults. The Obsidian vault is a **projection** of the graph — downstream, not the source of truth.

## What Gets Created on Export

```
vault_dir/
├── nodes/*.md          # One markdown file per node (YAML frontmatter + wiki-links)
├── edges.yaml          # All intentlinks
├── viz/*.canvas           # Obsidian Canvas files for each non-leaf node
├── viz/__FT_ROOT.canvas   # (by default) ROOT + all L1; leading __ so it sorts first
└── viz/_FT_{L1}.canvas    # (by default) One per L1 focus; leading _ so FT canvases sort to top
```

---

## export

```bash
# Single-graph vault (vault root = output dir)
ig-tool obsidian export -g graph.yaml -o my_vault/ [--force]

# Multi-graph vault (canvas paths relative to vault root)
ig-tool obsidian export -g graph.yaml -o my_vault/product_ig/ --vault-root my_vault/
ig-tool obsidian export -g pig.yaml -o my_vault/projection_ig/ --vault-root my_vault/
```

| Flag | Meaning |
|------|---------|
| `-g` | Input graph file (JSON or YAML, by extension) |
| `-o` | Output vault directory |
| `--vault-root` | Obsidian vault root (for multi-graph vaults, fixes canvas paths) |
| `--force` | Overwrite existing vault directory |
| `--intentlinks {all,siblings,none}` | Which intentlinks to show in FT canvases: `all` (default), `siblings` only, or `none` |
| `--no-ft-canvases` | Do not write `__FT_ROOT.canvas` and `_FT_{L1}.canvas` (they are written by default) |
| `--layout {grid,radial,portal}` | Canvas layout engine. `grid` (default) = legacy 3-column per-node grid, writes no layout. `radial` = one global multi-ring layout. `portal` = read-only zoom-out **map** (see below). radial/portal persist layout to `data_registry.obsidian_layout`, detect hand moves/resizes as sticky pins, and **save the graph file back** so pins survive re-export/merge/new vaults (see *Layout persistence & pins*). |
| `--radial-ring-gap PX` | Radial only: base pixel distance between depth rings (default 900) |
| `--radial-sweep DEG` | Radial only: total fan-out arc in degrees (default 180; auto-expands to 360 on spill) |
| `--nav-links {minimal,full,none}` | Navigation wiki-links in node bodies: `minimal` (**default**: only an `UP` link on L1 branch nodes — keeps node files clean), `full` (`UP`/`DOWN`/`CONTAINS` on every node, the old behaviour), or `none`. |
| `--no-install-plugins` | Skip installing the Obsidian community plugins this layout needs into the vault's `.obsidian/` (see *Plugin provisioning*). |
| `--fit-height` | Size each markdown node's box to its **estimated content height** instead of the fixed tall default. Sums a per-field pixel estimate of the frontmatter plus the measured rendered height of any images embedded in the node body — e.g. a `## Samples` section (see below), whose images are read with **Pillow** and scaled to the node width. Errs slightly tall (a small margin) so a box never clips. Group and portal nodes are left untouched. |

**Tree structure is stored in `edges.yaml`, not the nav links.** Export writes the
tree as `type: treearc` entries in `edges.yaml` (alongside `type: intentlink`), and
`import` rebuilds the tree from those. So `--nav-links minimal|none` round-trips
losslessly — the navigation links are purely cosmetic. (Legacy vaults without
treearc entries fall back to scraping `CONTAINS:` from node bodies.)

### Layout engines

- **`grid`** (default) — one `.canvas` per non-leaf node, 3-column grid. Unchanged legacy behaviour; writes no positions.
- **`radial`** — a single global `{uid→x,y}` layout: every canvas reads the same coordinates, so a node sits in the same place everywhere. Layout persists in each node's `data_registry.obsidian_layout` and round-trips through `merge`; a hand-moved/resized box wins on re-export (see *Layout persistence & pins*).
- **`portal`** — composes two regimes: an **`OVERVIEW.canvas`** with ROOT at the centre and each L1 branch embedded as a radial **portal** (`"portal": true`), plus one **`L1_{uid}.canvas`** per branch laid out as a vertical tree. Portal mode does **not** write per-node or `FULL_TREE` canvases; navigation links are retargeted so none dangle.
  - **Requires the Advanced Canvas Obsidian plugin** for portals to render — **export installs it automatically** (see *Plugin provisioning*). Without it, a portal renders as a static file card that never expands no matter how far you zoom, and Obsidian shows no error.
  - **The overview is READ-ONLY**: portal-embedded nodes can't be edited and their links can't be clicked (a hardcoded plugin behaviour, `pointer-events: none`). Workflow: zoom out on `OVERVIEW` → open the real `L1_{branch}.canvas` (portal door icon, or the node's DOWN link) → edit there.
  - Design/decision detail: `docs/DESIGN_OBSIDIAN_LAYOUT.md §10` and `PIG-OBS.NAVIGATION` in `projection/obsidian_defaults.ig.yaml`.

### Plugin provisioning

**Obsidian has no system-level plugin install.** Plugins live per-vault in
`<vault>/.obsidian/plugins/<id>/` and are enabled by listing their id in
`<vault>/.obsidian/community-plugins.json`. Vault isolation is deliberate (a
plugin has full filesystem and network access), so "install once, applies
everywhere" is not available.

Since `export` *creates* the vault, it owns that config: a portal vault whose
canvases can't render is an incomplete export, not a user setup step. Export
therefore installs and enables what the chosen engine needs:

| Engine | Plugins installed |
|--------|-------------------|
| `grid`, `radial` | none (stock canvas features only) |
| `portal` | `advanced-canvas` |

- **Installed at the vault ROOT**, not `-o` — in a multi-graph vault,
  `product_ig/` and `projection_ig/` share one `.obsidian/`.
- **Source is a local cache, never the network** — an export must work offline
  and must not silently pull code from the internet:
  ```
  ~/.local/share/intentgraph/obsidian-plugins/<plugin-id>/{manifest.json,main.js,styles.css}
  ```
  Override with `$INTENTGRAPH_OBSIDIAN_PLUGIN_DIR`. Populate it by copying from
  a vault that already has the plugin, or from the plugin's GitHub release.
- **Idempotent**: a plugin whose installed version matches the cache is left
  alone (`plugins_already_current` in the report); enabling is a set-union, so
  your other plugins are never dropped.
- **A missing cache warns, never fails** — the vault's markdown, edges and
  canvases are all still correct; only portal *rendering* degrades. Export exits
  `status: warning` with a `note` saying how to populate the cache.
- **Retrofit an existing vault** without re-exporting:
  ```python
  from intentgraph.obsidian import ensure_vault_plugins
  ensure_vault_plugins("path/to/vault", layout_engine="portal")
  ```

### Layout persistence & pins (radial / portal)

Manual **moves AND resizes** of node boxes, *and* **repositioning of a branch
portal** on the OVERVIEW ring, are preserved across re-export, `merge`, reload,
and export into a brand-new vault. The layout lives in the graph, per node:

```yaml
data_registry:
  obsidian_layout:
    engine: radial | portal            # frame these coords live in
    computed: {x, y, width, height}    # box the last export wrote (overwritten each export)
    pinned:   {x, y, width, height}    # your hand-edit — sticky until retracted
    portal:                            # L1 nodes only: the branch's portal on OVERVIEW
      computed: {x, y}
      pinned:   {x, y}                 # position only — portal size is plugin-forced
```

- **How a pin is set:** on export, before rewriting a canvas that already exists,
  each box is read back and compared to the stored `computed`. A difference
  beyond ~2px means you moved/resized it by hand → it becomes `pinned` and is
  honoured (`pinned` beats `computed`) from then on. First export never pins.
- **Portals pin position only** (x/y) — you cannot meaningfully resize a portal;
  the plugin forces its size to the branch's content bbox.
- **To retract a pin:** delete the `pinned` block from the node's `.md`
  frontmatter and run `ig-tool obsidian merge`. The node returns to computed
  layout. No dedicated verb — it rides `data_registry` round-tripping.
- **The graph file is saved back** on a radial/portal export (the report shows
  `graph_updated`), because pins and the `computed` baseline must live in the IG.
- **Disjoint from VSCode:** this touches only `data_registry.obsidian_layout`;
  the VSCode extension's `lenses.*.position` is a different projection, left alone.
- Full model + the fit-height drift rationale: `docs/DESIGN_OBSIDIAN_LAYOUT.md §12`.

### Node image samples (`## Samples`)

A node can carry image samples in `data_registry.samples` — a list of `{path, caption?}` entries (a bare string path also works). Export renders them as a `## Samples` body section, one `![[path]]` embed per entry (with the caption in bold above it). Because the images are declared **in the graph**, they are IG-owned: the section is regenerated on every export and **survives `--force`** (unlike anything hand-added to a node file, which `--force` overwrites).

Pair with `--fit-height` so image nodes are sized to actually show their images — fit-height measures each embed with Pillow and grows the box accordingly. Paths are resolved relative to the vault root; a missing or undecodable image still reserves its section chrome but adds no image height (a broken embed never inflates the box).

**CRITICAL GOTCHAS:**

1. **Use `--vault-root` for multi-graph vaults** — without it, canvas file paths point to the wrong location. Standard structure:
   ```
   obsidian_export/
   ├── product_ig/     # exported with --vault-root obsidian_export/
   └── projection_ig/  # exported with --vault-root obsidian_export/
   ```

2. **Canvases require populated treearcs** — if treearcs are empty in the graph, no canvases are generated. Populate treearcs from the UID hierarchy first.

3. **Use `--force`** to overwrite an existing export. Without it, the command fails if the directory exists.

4. **JSON or YAML** — `-g` accepts `.json`, `.yaml`, or `.yml`; format is inferred from extension.

Exit code 1 if vault directory exists without `--force`.

---

## import

```bash
ig-tool obsidian import -i vault_dir/ -o graph.json
```

Parses `nodes/*.md` and `edges.yaml` back into a graph.
Exit code 1 if vault structure is invalid.

---

## diff

```bash
ig-tool obsidian diff -g reference_graph.yaml -i vault_dir/ [-o diff_report.yaml] [--names-only]
```

Compares vault against reference graph. Detects added/deleted/modified nodes and links.

- Exit code 0 always (status "warning" if changes detected)
- Report includes: `nodes_added`, `nodes_deleted`, `nodes_modified`, `links_added`, etc.
- **`nodes_modified_details` shows `old` → `new` values per changed field BY DEFAULT** — this is what lets you tell a real edit from a round-trip artifact. Pass `--names-only` to reduce the payload to bare field names.
- `links_modified_details` shows changed link fields; `links_deleted_details` lists dropped links.

**Diff/merge workflow (use this order):**
1. `ig-tool obsidian diff -g graph -i vault/` — inspect the `old` → `new` values. Distinguish genuine edits from artifacts (see gotchas).
2. `ig-tool obsidian merge -g graph -i vault/ --dry-run` — preview what merge would apply/ignore/conflict.
3. `ig-tool obsidian merge -g graph -i vault/` — apply.

**GOTCHAS (learned the hard way):**
- **Report schema differs stdout vs `-o` file.** With `-o`, the details nest under a top-level `details:` key (`details.nodes_modified_details`, etc.); stdout prints them flatter. Parse from `details` when reading a saved report.
- **Two classic false positives on a pre-snapshot vault** (one exported before `.ig-sync.yaml` existed — you'll see a `no baseline` warning):
  1. **All intentlinks appear `deleted`** — the vault's `edges.yaml` predates the link-`uid` fix, so link identity can't be matched. `merge` is content-only and never deletes links, so this is harmless — but don't mistake it for a real edit.
  2. **`name` changes that are `/`→space** (or other stripped chars) are **Obsidian filename sanitization**, not edits — the node name can't safely contain `/\:*?"<>|[]#^` (see PRIMER_01 § Node Name Content Safety). Merging them degrades the canonical name.

---

## merge — Flow vault edits back into the canonical graph (vault → IG)

The **two-way** counterpart to `export`. `merge` reads a vault edited in Obsidian and applies the changes back into the canonical graph file. Unlike `import` (which rebuilds the whole graph from scratch and **overwrites** — dropping `data_registry`, `meta`, `inter_intentlinks`, `lenses`, and link UIDs), `merge` mutates the loaded graph **in place**, touching only the fields that changed. The graph file is always the source of truth.

```bash
# Merge vault edits into the graph, in place
ig-tool obsidian merge -g graph.yaml -i vault_dir/

# Preview only (writes nothing)
ig-tool obsidian merge -g graph.yaml -i vault_dir/ --dry-run

# Write to a new file instead of in place
ig-tool obsidian merge -g graph.yaml -i vault_dir/ -o merged.yaml
```

| Flag | Meaning |
|------|---------|
| `-i` | Vault directory to merge from (required) |
| `-g` | Canonical graph file. If omitted, resolved from the vault's `.ig-sync.yaml` snapshot (`graph_file`) |
| `-o` | Output graph path (default: in place over `-g`) |
| `--dry-run` | Print the merge report (applied / conflicts / ignored / errors); write nothing |
| `--force` | Proceed even if the canonical graph changed since export (see conflict model) |
| `--skip-malformed` | Skip unparseable `.md` files instead of halting; skipped nodes are left untouched (never deleted) |
| `-m` / `--role` | Provenance: one-liner history note / agent role. Merged nodes auto-stamp a HistoryEntry at save; without `--role` the actor resolves to the human identity with a `via:obsidian` qualifier |

**Scope — content-only (phase 1).** `merge` applies edits to node content fields (frontmatter) and intentlink fields (`edges.yaml`). It does **not** create, delete, or reparent nodes from the vault:
- A new `.md` file → reported as `ignored_added` (not created).
- A `.md` deleted from the vault → reported as `ignored_deleted` (the canonical node is **kept**, never deleted).

**Conflict model — the graph file wins, whole-node granularity.** `export` writes a baseline snapshot (`<vault>/.ig-sync.yaml`, see `PROJECT_RESOURCES_SPEC.md §4.4`). At merge time:
- If the canonical graph's overall `graph_hash` differs from the snapshot (it changed since export), `merge` refuses unless `--force`.
- Per node: a node the vault edited is applied **only if** the canonical node is unchanged since export. If both sides changed a node, the **whole node is a conflict** — the vault edit is skipped, the canonical value stands, and the node is listed in the report's `conflicts`.
- Without a snapshot (`--force`, or vault never carried one), all vault-edited nodes are applied with no conflict detection (weaker guarantee).

**Malformed files fail loud by default.** A `.md` that can't be parsed aborts the merge with an error and makes **zero** mutations (so a typo can't masquerade as a deletion). Use `--skip-malformed` to proceed, leaving the unreadable nodes untouched.

**GOTCHAS:**
1. `merge` requires the vault to have been produced by `export` (for the `.ig-sync.yaml` snapshot). Merging a snapshot-less vault works but loses conflict detection.
2. `merge` never deletes canonical nodes or links — structural changes are out of scope in this phase.
3. Always `--dry-run` first on an unfamiliar vault to see the planned changes.

---

## export-canvas — Export a working view to canvas

```bash
ig-tool obsidian export-canvas -g graph.yaml --nodes E,T,L -o output.canvas
```

Select the view to draw with `--nodes UID,UID,…`. For custom visualizations beyond the automatic per-node canvases from `export`.

---

## export-tree — FT treemap canvas

All FT canvases show **ROOT + all L1**; optionally one L1's subtree is expanded. Use leading underscores so FT canvases sort to the top of the viz list: **`__FT_ROOT`** (double) for the full tree, **`_FT_{L1}`** (single) for each L1 focus.

```bash
# __FT_ROOT: full tree — all L1 subtrees expanded (double _ so root sorts first)
ig-tool obsidian export-tree -g graph.yaml -o viz/__FT_ROOT.canvas

# _FT_{L1}: expand only one L1's descendants
ig-tool obsidian export-tree -g graph.yaml -o viz/_FT_DISCOVER.canvas --focus-l1 DISCOVER

# With intentlinks control
ig-tool obsidian export-tree -g graph.yaml -o viz/__FT_ROOT.canvas --intentlinks siblings
```

| Flag | Default | Notes |
|------|---------|-------|
| `--nodes-prefix` | `nodes` | Vault-relative path to node `.md` files |
| `--width` | 2400 | Canvas width in pixels |
| `--focus-l1` | none | L1 UID to expand; default = full tree |
| `--intentlinks {all,siblings,none}` | `all` | Which intentlinks to draw |

(Renamed from `full-tree` in Phase 3; the legacy `full-tree` alias was removed 2026-07-15.)

**By default**, `obsidian export` writes `viz/__FT_ROOT.canvas` and `viz/_FT_{L1}.canvas` for each L1. Use `--no-ft-canvases` to skip them. The standalone `obsidian export-tree` command is still available when you need a single FT canvas (e.g. custom path or nodes-prefix).

---

## export-lens-canvas — Export a named internal lens as canvas

```bash
ig-tool obsidian export-lens-canvas -g graph.yaml --lens my-view -o viz/my_view.canvas
```

Renders an internal (graph-embedded) lens as an Obsidian canvas with LOD-aware rendering.
(Renamed from `lens-canvas` in Phase 3; the legacy `lens-canvas` alias was removed 2026-07-15.)

---

## detect-pins — Find user-moved nodes in canvas

```bash
ig-tool obsidian detect-pins -g graph.yaml --nodes E,T,L --canvas existing.canvas [-o pins.yaml] [--tolerance 5]
```

Select the view the canvas was generated from with `--nodes UID,UID,…`. Compares canvas positions against auto-computed layout. Returns pinned node UIDs and positions.

---

## Standard Export Workflow

The canonical export pattern for a workflow root:

```bash
# Both graphs — YAML or JSON accepted equally
ig-tool obsidian export -g graph.yaml -o obsidian_export/product_ig/ --vault-root obsidian_export/ --force
ig-tool obsidian export -g pig.yaml -o obsidian_export/projection_ig/ --vault-root obsidian_export/ --force
```

Always export to `{workflow_root}/obsidian_export/` with subfolders `product_ig/` and `projection_ig/`.
