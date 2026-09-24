# Design Intent — Obsidian Layout & Layout Control

**Status:** Layout engines **implemented** — three selectable via `--layout`: `grid` (legacy default), `radial` (one global multi-ring layout + position persistence + pin round-trip), and `portal` (a read-only zoom-out **map**: ROOT + each L1 branch as an Advanced-Canvas portal, arranged radially; each branch its own vertical-tree canvas). Flat radial was tried on a real graph and read poorly at scale → portal supersedes it as the recommended overview. Visual grammar (Phase 2) and plugin (Phase 4) still deferred. The Obsidian projection intent is captured as its own ProjectionIG: `projection/obsidian_defaults.ig.yaml` (`PIG-OBS.*`); see especially `PIG-OBS.NAVIGATION` for the portal read-only-map decision. See §10 for the portal engine and §11 for `--fit-height` node sizing (Pillow-measured image samples).

**Scope:** The **Obsidian projection** of an IntentGraph — specifically how nodes are *positioned* on the Canvas views, and how that positioning could be chosen and controlled. This is about the `ig-tool obsidian export` pipeline and its Canvas output, **not** the VSCode extension.

---

## Table of Contents

1. [1. Context — where we are today](#1-context--where-we-are-today) _(Lines 34-40)_
1. [2. The problem](#2-the-problem) _(Lines 43-47)_
1. [3. Intent — what a good layout must achieve](#3-intent--what-a-good-layout-must-achieve) _(Lines 50-60)_
1. [4. Direction — global radial tree via a real layout engine](#4-direction--global-radial-tree-via-a-real-layout-engine) _(Lines 63-73)_
1. [5. Where positions live (persistence)](#5-where-positions-live-persistence) _(Lines 76-99)_
1. [6. Controlling the layout from Obsidian (plugin)](#6-controlling-the-layout-from-obsidian-plugin) _(Lines 102-113)_
1. [7. Decisions already taken](#7-decisions-already-taken) _(Lines 116-125)_
1. [8. Open questions for the implementing session](#8-open-questions-for-the-implementing-session) _(Lines 128-135)_
1. [9. Pointers](#9-pointers) _(Lines 138-148)_
1. [10. Portal engine (nested overview) — implemented](#10-portal-engine-nested-overview--implemented) _(Lines 151-218)_
1. [11. Node height fitting (`--fit-height`) — implemented](#11-node-height-fitting---fit-height--implemented) _(Lines 221-264)_
1. [12. Whole-box + portal pins (`obsidian_layout`) — implemented](#12-whole-box--portal-pins-obsidian_layout--implemented) _(Lines 267-274)_
   1. [Storage shape](#storage-shape) _(Lines 277-295)_
   1. [Mechanism (three parts)](#mechanism-three-parts) _(Lines 298-322)_
   1. [Why diff against stored `computed`, not a fresh recompute (the load-bearing choice)](#why-diff-against-stored-computed-not-a-fresh-recompute-the-load-bearing-choice) _(Lines 325-335)_
   1. [Two projections, disjoint storage (no collision)](#two-projections-disjoint-storage-no-collision) _(Lines 338-355)_



---

## 1. Context — where we are today
<!-- Lines 34-40 -->

`ig-tool obsidian export` renders an IntentGraph into a vault:
- `nodes/*.md` — one file per node (no spatial layout; Obsidian's Graph View auto-lays-out from wiki-links).
- `viz/*.canvas` — **JSON Canvas** files where layout IS explicit (integer pixel `x, y, width, height` per node). One canvas per non-leaf node, plus full-tree canvases (`__FT_ROOT`, `_FT_{L1}`).

The Canvas layout is computed by `compute_grid_positions` (in `src/src/intentgraph/obsidian/_format.py`), driven by a `LayoutConfig`. It is a **fixed 3-column grid**, computed **independently per canvas** — a node's coordinates differ depending on which canvas you open.

## 2. The problem
<!-- Lines 43-47 -->

The 3-column grid **becomes hard to read when an L1 node has more than 3–4 children.** It wraps into a tall/wide block with no visual center; edges from the parent group cross awkwardly; there is no sense of "this node's neighborhood." Degree does not scale gracefully.

A second, subtler problem: because layout is recomputed **per canvas**, a node sits at a *different* position in the full-tree view than in its parent's view. The eye loses its map as you navigate — there is no stable mental model of "where things are."

## 3. Intent — what a good layout must achieve
<!-- Lines 50-60 -->

The layout is a **projection** of the tree's structure into 2-D space. It should:

1. **Scale with degree** — a parent with 8 children should read as cleanly as one with 3. (A circle of 8 works; a 3-wide grid of 8 does not.)
2. **Be globally stable** — a node occupies **one** position, computed once for the whole tree. Every per-node canvas is a **crop (sub-view)** of that single global coordinate space, not a fresh recomputation. Navigating between canvases preserves the map.
3. **Guarantee non-overlap** — boxes must not collide; this is a solved problem in real layout engines and should not be hand-rolled.
4. **Be pluggable** — "radial tree" is the first target, but the layout algorithm should be a swappable choice, not hardwired. Grid stays available (and is a sensible fallback for small fan-out).
5. **Be overridable** — user-dragged positions (pins) should survive re-export rather than being clobbered.

**Key reframing vs. today:** compute **one** `{uid → (x, y, w, h)}` map for the entire tree, persist it, and have each canvas *look up* positions for the nodes it shows. This replaces the current per-canvas recomputation.

## 4. Direction — global radial tree via a real layout engine
<!-- Lines 63-73 -->

**Chosen approach (see §7):** use **Graphviz `twopi`** — its purpose-built **radial tree** engine — invoked as a subprocess (`graph → DOT → twopi -Tplain → parse x,y`).

Rationale:
- `twopi` is a real radial-tree layout with non-overlap handling; far better than hand-rolled trig.
- The `twopi` (and `dot`) binaries are **already installed** on the dev machine (`/usr/local/bin`).
- **Zero new Python dependencies** — the core library (`src/`, package `intentgraph`) intentionally depends only on `pydantic` + `pyyaml`. Shelling out keeps that clean. Feature-detect `twopi` and **fall back to the current grid** if it is absent.
- The layout/subprocess code should live in the tooling layer (`agents_runtime/` / CLI), **not** in the pure core library (`src/`), so the core stays dependency-free and side-effect-free.

The JSON Canvas format only needs integer `x, y, width, height` per node, so any engine's output drops straight in — no change to the canvas serializer's structure.

## 5. Where positions live (persistence)
<!-- Lines 76-99 -->

**Chosen approach (see §7):** persist the layout into each node's
**`data_registry.obsidian_layout`** — the whole box (`x, y, width, height`) for
every node, plus each L1 branch's portal position, split into `computed` (what
the engine last wrote) and `pinned` (a human assertion). See **§12** for the
full model, the mechanism, and the fit-height rationale; this section states
only the *where* and *why*.

Why:
- `data_registry` **round-trips losslessly** through the `obsidian merge`
  machinery already built — so layout survives export → edit → merge → reload,
  with **zero merge-code changes**.
- Layout lives *with the graph* (source of truth), so it is stable across
  exports and can be **pinned / user-edited**.
- The key is **Obsidian-scoped** (`obsidian_layout`, not a generic `positions`)
  so it never collides with another projection's layout store — the VSCode
  extension keeps its own disjoint `lenses.*.position` (see §12).

Flow: **read back the last export's canvases → record human moves/resizes as
pins → compute fresh layout, pins overriding it → write each canvas → store the
boxes as written back into `computed`.** A pinned node is respected on the next
export instead of being recomputed; the retraction gesture (delete the `pinned`
block, `merge`) returns it to computed. Full detail in §12.

## 6. Controlling the layout from Obsidian (plugin)
<!-- Lines 102-113 -->

The longer-term intent: let the user **choose and re-trigger** the layout from *inside* Obsidian, not only via the CLI.

An Obsidian plugin (desktop-only) would expose a small control surface — e.g. a side panel — to:
- pick the layout algorithm (radial / grid / …) and its parameters,
- re-run layout on the current graph (shelling out to `ig-tool`),
- surface user drags back as pins.

This is the same front-end vehicle already envisioned for **two-way sync** (the plugin would drive `ig-tool obsidian merge`). Layout control and sync control naturally share one plugin. Deployment intent (from the prior discussion): **desktop-only, single user, symlink-deployed so one build serves all vaults with a clean iteration loop** — but that is a plugin-deployment concern, tracked wherever the plugin work is planned; it is out of scope for the *layout* work itself.

**Sequencing:** the layout engine (CLI-side) is valuable on its own and should land **first** — it improves every export regardless of whether the plugin ever ships. The plugin is a later control layer on top.

## 7. Decisions already taken
<!-- Lines 116-125 -->

| Decision | Choice | Rationale |
|---|---|---|
| Layout model | **One global layout; every canvas reads from it** | Stable mental map; a node keeps its position everywhere. *Realized: `FULL_TREE.canvas` is the whole-graph zoom-out view; per-node canvases look up the same coords.* |
| Layout engine | ~~Graphviz `twopi`~~ → **pure-Python radial** (`_radial.py`), grid default/fallback | **REVISED.** The non-overlap logic was already owned by `_subtree_span`/`_assign_x`; radial is that algorithm with angular span instead of horizontal. Pure-Python keeps the core library dependency-free, deterministic, and unit-testable — and offline `.canvas` generation is the stable path regardless, so `twopi`'s only advantage (free non-overlap) was moot. `twopi` may return later as an opt-in engine for very large graphs. |
| Position storage | **`data_registry.obsidian_layout`** — per-node whole box + branch portal position, split `computed`/`pinned`, engine-scoped | Round-trips via merge with zero new merge code; the whole box (not just x/y) and portals are pinnable; lives with the graph; Obsidian-scoped so it never collides with another projection. Whole-box + portal + fit-height-drift-guarded pin round-trip verified. See §12. |
| First target | **Radial always** (angular budget handles small fan-out) | Solves the L1 > 3–4 readability problem; one code path. Each L1 gets 1/8–1/6 of a half-circle, so 2–3 children cluster near the parent instead of a full-circle-of-two. |
| Portals | ~~embed child canvases~~ → **rejected** | **REVISED.** The user wants to zoom out on ONE canvas to see the whole graph shape, not navigate embedded sub-canvases. One global radial layout serves that directly; portals would fragment it. |
| Code location | **core library `src/`** (`obsidian/_radial.py` + `_export.py`) | Since the engine is pure-Python with zero deps, it stays in the core library — no need to push it to the tooling layer as the `twopi` plan required. |

## 8. Open questions for the implementing session
<!-- Lines 128-135 -->

- **Where radial applies:** per-node canvases only at first, or also the full-tree `__FT_ROOT`? (Prior lean: per-node canvases first — that's where the pain is.)
- **Small-n behavior:** radial always, or grid below ~4 children and radial at/above? (Prior lean: threshold — a circle of 2–3 looks odd.)
- **Deep trees:** keep one-ring-per-parent (nesting handled by separate canvases, as now), or a true multi-ring radial-tree on one canvas? (Prior lean: keep one-ring-per-canvas — avoids rewriting the viz-tree builder.)
- **Pin precedence:** exact rule for merging user-dragged positions with a freshly computed layout (which wins, and when).
- **`twopi` absence:** confirm the grid fallback path and how the CLI communicates which engine was used.
- **Config surface:** what layout parameters are exposed on `LayoutConfig` / the CLI (algorithm, radius/spacing, threshold).

## 9. Pointers
<!-- Lines 138-148 -->

- Current layout math: `src/src/intentgraph/obsidian/_format.py` — `compute_grid_positions`, `compute_group_size`, `LayoutConfig`.
- Canvas generation: `src/src/intentgraph/obsidian/_export.py` — `_generate_canvas`, `_build_viz_tree`, `compute_auto_layout`, `_assign_positions`, `detect_pinned_positions`.
- Radial engine: `src/src/intentgraph/obsidian/_radial.py` — `RadialConfig`, `compute_radial_layout`; orchestration `apply_global_layout` in `_export.py`.
- Portal engine: `_export.py` — `_generate_l1_subtree_canvas`, `generate_portal_overview_canvas` (see §10).
- Existing pin detection: `ig-tool obsidian detect-pins` (see `.claude/skills/ig-tool-obsidian/SKILL.md`).
- Position round-trip guarantee: `data_registry` losslessness — `docs/PROJECT_RESOURCES_SPEC.md §4.4` (sync snapshot) and the `obsidian merge` verb.
- JSON Canvas spec: https://jsoncanvas.org/ (open format; `{ "nodes": [], "edges": [] }`, integer pixel geometry).
- Advanced JSON Canvas (portals, styleAttributes): superset spec `1.0-1.0`, `Developer-Mike/obsidian-advanced-canvas`.
- Graphviz radial engine: `twopi` — considered and rejected (see §7 table); pure-Python radial used instead.

## 10. Portal engine (nested overview) — implemented
<!-- Lines 151-218 -->

`--layout portal` composes two layout regimes into a **zoom-out map**:

- **OVERVIEW.canvas** — the root at the centre, and each L1 branch rendered as a
  **portal** (an Advanced-Canvas embedded canvas, `"portal": true`), arranged
  radially around the root. Each portal is sized to its branch's bounding box;
  the ring radius grows so portals cannot overlap. `root → portal` treearc edges.
- **L1_{uid}.canvas** — one per branch: that L1 + all descendants laid out as a
  clean **vertical tree** (reuses `_subtree_span` / `_assign_x` rooted at the L1).

**Why this, not flat radial:** flat radial (`--layout radial`) was exercised on a
real 37-node graph and read poorly — outer rings crowded, the whole tree fanned
into an awkward half-disc. A vertical tree is the right shape for a single branch;
radial is the right shape for arranging ~6 peer branches around a hub. Portal uses
each where it is strong.

**Read-only-map constraint (important).** Portals are a read-only visual embed.
Verified against Advanced Canvas 6.4.0: the plugin tags portal-embedded nodes
`data-is-from-portal` and applies `pointer-events: none`, so nodes shown *inside*
a portal **cannot be edited and their links cannot be clicked** — this is
intentional plugin behaviour with no toggle. Therefore the overview is a MAP; the
workflow is **overview → open the real branch canvas (portal door icon, or the
node's DOWN link) → read and edit there.**

**Plugin dependency is export-owned, per vault.** Obsidian has no system-level
plugin install: plugins live in `<vault>/.obsidian/plugins/<id>/` and are enabled
per vault via `community-plugins.json`. Vault isolation is deliberate on
Obsidian's part (a plugin has full filesystem and network access), so a global
"install once" does not exist to depend on.

This makes the plugin an **export responsibility, not a user setup step**: a
portal vault without Advanced Canvas fails *silently* — vanilla Obsidian ignores
the unknown `"portal": true` key and renders a static file card that never
expands, with no error. The user sees a permanently collapsed map and has no
signal why. Since `export` creates the vault, it provisions the plugin into the
vault root's `.obsidian/` (`_plugins.py`, applied after the canvases are
written).

Two constraints shape that implementation:

- **Bytes come from a local cache, never the network**
  (`~/.local/share/intentgraph/obsidian-plugins/`, `$INTENTGRAPH_OBSIDIAN_PLUGIN_DIR`
  to override). An export must work offline, and must never silently fetch and
  execute third-party code as a side effect of rendering a graph.
- **A missing cache warns rather than fails.** The vault's nodes, edges and
  canvases are all still correct without the plugin — only the *rendering* of
  portals degrades. Failing the export would discard correct output over a
  presentation concern, so the CLI exits `status: warning` with the remedy.

Vanilla engines (`grid`, `radial`) emit only stock canvas features and so
install nothing; the engine→plugin map lives in `_REQUIRED_PLUGINS`.

**Navigation is engine-aware.** Because portal mode does not emit per-node or
full-tree canvases, `_format_navigation` retargets `UP`/`DOWN` wiki-links so none
dangle: in portal mode `UP → OVERVIEW` (branch head) or `L1_{branch}.canvas`
(deeper node); `DOWN → OVERVIEW` (root) or `L1_{branch}.canvas`. Grid/radial nav
is unchanged. A regression test asserts no `*.canvas` link points at a file the
active engine did not generate.

**Code:** `src/src/intentgraph/obsidian/_export.py` —
`_generate_l1_subtree_canvas`, `generate_portal_overview_canvas`,
`l1_canvas_stem`, `portal_node_id`, `_l1_ancestor_uid`, and the `portal` branch of
`export_to_obsidian` + `_format_navigation`. Tests: `tests/test_obsidian_portal.py`.

**Open tuning (deferred):** ring radius is generous (portals are large) and portal
internal aspect is wide (children in one row) — candidates for a tighter ring
and/or multi-column branch trees. Intent recorded in `PIG-OBS.NAVIGATION`.

## 11. Node height fitting (`--fit-height`) — implemented
<!-- Lines 221-264 -->

By default a markdown node's canvas box uses a fixed tall height. `--fit-height`
instead sizes each box to its **estimated content height**, so short nodes stop
wasting vertical space and image nodes grow to actually show their images.

**Two contributions, summed** (`estimate_node_height` in `_export.py`):

- **Frontmatter estimate** — a per-field pixel model: a fixed base plus one row
  per non-empty field, each row's height driven by its wrapped line count (prose
  capped at 3 lines, matching Obsidian's scalar-property clip; lists uncapped). A
  small `_FIT_MARGIN` errs tall so a box never clips.
- **Body image height** (`_body_image_height`) — when `nodes_dir`/`vault_root` are
  known, the node's markdown body is scanned for image embeds (a `## Samples`
  section; see below). Each image is measured with **Pillow**, scaled to the node
  content width, capped at `_FIT_IMAGE_MAX_H`, and added with per-image caption +
  gap chrome. A missing or undecodable image contributes 0 render height (a broken
  embed never inflates the box) but still reserves its section/caption chrome.

Only markdown **file-nodes** with a resolvable UID are resized; group and portal
nodes are left untouched. In portal mode fit-height touches only the OVERVIEW's
ROOT node (the L1 embeds are branch canvases, already sized).

**Image samples are IG-owned.** A node declares images in
`data_registry.samples` (list of `{path, caption?}`); `_format_samples` renders
them as a regenerated `## Samples` body section, so the images **survive
`--force`** — they are part of the graph, not hand-added vault content. This is
what makes image-aware fit-height reproducible across re-exports.

**Dependency:** Pillow (`Pillow>=10.0`), declared in both the root `pyproject.toml`
(the installed `intentgraph-tools` package, authoritative for the `ig-tool` venv)
and `src/pyproject.toml` (the core dev venv). Both matter: the tool
venv resolves deps from the top-level file only.

**Code:** `_export.py` — `estimate_node_height`, `_apply_fit_height`,
`_body_image_height`, `_image_render_height`, `_format_samples`, and the
`_FIT_*` constants. Tests: `tests/test_obsidian.py` (`TestImageRenderHeight`,
`TestBodyImageHeight`, `TestEstimateNodeHeightExtraBody`, `TestFormatSamples`,
`TestApplyFitHeight`) and `tests/test_obsidian_navlinks_fit.py`.

**Open tuning (deferred):** the frontmatter estimate is a heuristic calibrated to
the default node width, not a true render measurement — `CANVAS_INSTRUMENT.js`
(paste into Obsidian's dev console) measures real rendered heights to recalibrate
the `_FIT_*` constants if Obsidian's styling drifts.

## 12. Whole-box + portal pins (`obsidian_layout`) — implemented
<!-- Lines 267-274 -->

When a human hand-edits the Obsidian layout — moves or resizes a node box, or
drags a branch's portal on the OVERVIEW ring — that edit **survives the next
`ig-tool obsidian export`** and survives reload / new-vault / `merge`. The whole
OVERVIEW layout is preserved, in the one canonical IG. This is Feature 2, the
complement to §11's `--fit-height`: fit-height sets a good *default* box;
`obsidian_layout` lets a human *override* it and keeps the override.

### Storage shape
<!-- Lines 277-295 -->

Layout lives on each node under `data_registry.obsidian_layout`:

```yaml
data_registry:
  obsidian_layout:
    engine: radial | portal            # coordinate frame these boxes live in
    computed: {x, y, width, height}    # box the last export WROTE — overwritten every export
    pinned:   {x, y, width, height}    # human assertion — STICKY; set by detection, cleared by retraction
    portal:                            # L1 nodes only: the branch's portal on OVERVIEW
      computed: {x, y}
      pinned:   {x, y}                 # position-only (portal size is plugin-forced)
```

**Precedence (render):** every field is `pinned if present else computed-fresh`.
A pin (human assertion) beats the engine; otherwise the engine's fresh output is
used. It rides `data_registry` — already a diffed, round-tripping field — so the
whole feature needs **zero** `_diff.py` / `_merge.py` / `_import.py` changes.

### Mechanism (three parts)
<!-- Lines 298-322 -->

**1. Detection — read back the canvas, diff vs stored `computed`.** On export,
*before* rewriting any canvas, if a canvas file already exists on disk each real
file-node's box is read and compared to the node's stored
`obsidian_layout.computed` (the box the last export wrote) — **not** to a fresh
recompute. Map canvas id → uid the same way the writers do (`file_node_id`,
`portal_node_id`); ids that map to no uid (portal-as-branch-embeds, groups) are
skipped. No stored `computed` → first export in this frame, never a pin. A
difference beyond ~2px → a human moved/resized it → the on-disk box becomes
`pinned` (portal → x/y only). Two call-site families: **OVERVIEW.canvas**
(ROOT's box + every portal position) and each **`L1_<branch>.canvas`** (branch
boxes); radial reads its global canvases. `detect_canvas_pins` in `_export.py`.

**2. Honor + refresh.** The generators render `pinned ?? computed-fresh` for all
fields (radial map in `apply_global_layout`; branch boxes in
`_generate_l1_subtree_canvas`; ROOT box + portal x/y in
`generate_portal_overview_canvas`). After writing, the box **actually written**
(post fit-height) is stored back into `computed` (`_store_computed`) so the next
detection has a true baseline. Fit-height never overrides a pinned box.

**3. Retraction.** Pins are sticky. To retract, the human deletes the
`obsidian_layout.pinned` block from the node's `.md` frontmatter and runs
`ig-tool obsidian merge` → the pin clears and the node returns to computed
layout. This falls out of `data_registry` diffing for free — no new CLI verb.

### Why diff against stored `computed`, not a fresh recompute (the load-bearing choice)
<!-- Lines 325-335 -->

`--fit-height` recomputes heights heuristically, so a fresh recompute of an
*untouched* node can differ from what is on disk — under a recompute-based diff
that would be mis-detected as a resize and **frozen forever**. Diffing against
the last export's stored `computed` makes fit-height drift (and a just-retracted
pin's stale canvas, still showing the old position) invisible to detection. This
is the whole reason `computed` and `pinned` are separate fields — do not collapse
them. The `engine` field is the second guard: radial coords are global, portal
coords are branch-local, so a layout block from a different engine is a different
frame and is dropped (pins included) rather than misread.

### Two projections, disjoint storage (no collision)
<!-- Lines 338-355 -->

Obsidian stores layout on each node under `data_registry.obsidian_layout`. The
**VSCode extension** stores its layout in the **top-level `lenses` block**
(`lenses.<name>.nodes.<uid>.position` = absolute cytoscape x/y, leaves only,
per-lens) and never touches `data_registry`. They are independent projections of
the same truth — different frames, disjoint keys — and this work touches only
`data_registry`; VSCode is left entirely alone.

**Code:** `_export.py` — `_LAYOUT_KEY`, `detect_canvas_pins`,
`apply_global_layout`, `_store_computed`, `_pinned_box` / `_computed_box` /
`_portal_xy` and the `_set_pinned` / `_set_portal_pinned` writers, plus the
pin-honoring branches of `_generate_l1_subtree_canvas` and
`generate_portal_overview_canvas`, and the reordered `export_to_obsidian` (detect
→ compute → write canvases → capture `computed` → write markdown). The CLI saves
the mutated graph back on a radial/portal export (`obsidian.py`). Tests:
`tests/test_obsidian_box_pins.py` (detection, honor, portal pins, drift guard,
retraction, round-trip, engine-frame isolation) and the updated
`tests/test_obsidian_radial_export.py::TestPinOverride`.
