# vscode_viewer — Design

The vscode_viewer is the VS Code custom editor that renders IntentGraphs as interactive
node-link diagrams and allows field-level text editing that writes back to the IG YAML file.

## Table of Contents

1. [Audience and goals](#audience-and-goals) _(Lines 25-32)_
1. [Interaction model](#interaction-model) _(Lines 35-63)_
1. [LOD model](#lod-model) _(Lines 66-83)_
1. [Editing model](#editing-model) _(Lines 86-106)_
1. [Lens model](#lens-model) _(Lines 109-144)_
1. [Persistence policy](#persistence-policy) _(Lines 147-164)_
1. [Invariants (the rules nothing may break)](#invariants-the-rules-nothing-may-break) _(Lines 167-181)_
1. [Non-goals](#non-goals) _(Lines 184-194)_
1. [Open questions / known issues](#open-questions--known-issues) _(Lines 197-220)_
1. [Tree appendix](#tree-appendix) _(Lines 223-273)_



---

## Audience and goals
<!-- Lines 25-32 -->

Two roles: **architect** (reads and edits graph intent) and **agent reviewer** (validates
agent output against intent). Both need to read full-LOD text without eyestrain and submit
text edits. Neither uses the viewer for structural graph authoring — that is ig-tool's job.
The viewer is a reading and light-editing surface, not an alternative to ig-tool.

---

## Interaction model
<!-- Lines 35-63 -->

```
GESTURES (view mode only)
  single-click node body  ──►  toggle LOD lean <-> full
  double-click full-LOD   ──►  ENTER EDIT MODE  ───┐
  drag node               ──►  reposition (fires cy.on('free') on release)    │
  click +/- cue           ──►  expand / collapse compound subtree             │
  lens control panel      ──►  switch / create / rename / delete lens         │
                                                                               │
VIEW MODE (default)                                                            │
  all gestures active                                                          │
  overlays visible for full-LOD nodes                                         │
                                                                               ▼
                                                        EDIT MODE (per-node, one at a time)
                                                          camera centers on node (animate)
                                                          ALL fields editable simultaneously
                                                          cy tap/drag suppressed for this node
                                                          Escape: CANCEL (no write) ──────────────────┐
                                                          pointerdown outside card: COMMIT ────────────┤
                                                                                                       │
                                                                              ◄────── camera restores ─┘
                                                                              VIEW MODE restored
```

State machine note: blur on a field is NOT an exit trigger — only pointerdown outside the
overlay card bounding rect or Escape are valid exits.

---

## LOD model
<!-- Lines 66-83 -->

Three tiers; current implementation collapses skeleton and lean into one visual:

| Tier | Rect (derived, not stored) | Content |
| ---- | ------------------------- | ------- |
| skeleton | 160 x 60 px | uid + name only (canvas label) |
| lean (default) | 160 x 60 px | name label on Cytoscape canvas |
| full | 240 x 180 px | HTML overlay: name (bold), intent (wrapped), epistemic_state (italic), constraints (bulleted) |

**Rect dimensions are derived, never stored.** Rect = f(lod, collapse-state-of-self,
collapse-state-of-descendants). The tier defaults above are the canonical values.
Current code has 320x360 (Amend 4); a generator MUST update `elkBridge.ts` constants
to 240x180 before next build. See `LAYOUT.RECT`.

(@TODO: uid should always be displayed before title, like `EXAMPLE.DETAILS.1: The_title_of_the_node`)

---

## Editing model
<!-- Lines 86-106 -->

**Entry.** Double-click on a full-LOD node. A lean node must be toggled to full first.
On entry: camera animates to center the node; overlay switches to a unified edit form;
cy gesture handlers for that node are suppressed.

**Scope.** User requirement (verbatim): "All the content of the detailed node should be
editable in the same edit mode (not acting as separate fields)." Name, intent, and all
constraint strings are simultaneously editable. `EditNodeRequestType` is the wire contract.

**Exit.** `pointerdown` event anywhere outside the overlay card's bounding rect commits
(submit). Escape cancels (no write). Internal tab-navigation does not exit. This is not
yet cleanly implemented: current code uses blur events (glitchy — `EDITING.EXIT` is `undecided`).

**Persistence.** DOM is NOT updated optimistically. Fields show pre-edit values until
`ok=true` arrives from the host. On `ok=false`: fields revert; a NON-DISMISSABLE banner
appears with error text and a Reload button; the failure is logged to the `IntentGraph`
output channel. Root cause of current save failures: silent `fileHash` mismatch (see
`DIAGNOSTICS.EDIT_CONFLICT`).

---

## Lens model
<!-- Lines 109-144 -->

**Lenses are view configuration, not projections.** A lens stores user-decidable visual
state: per-node LOD and per-node position. Lenses do NOT transform content — they are
selection + visual choices. The vscode_viewer ITSELF is the real ProjectionIG (it projects
the IG into a GUI). Keep this distinction crisp.

**Sources.** Lenses live inside the IG file as `lenses: {name: LensConfig}`. The loader
surfaces them in `LoadGraphResponse.lenses`. `meta.default_lens` names the lens applied
automatically on open (after `BootCompleteNotification`).

**Control panel.** A persistent control panel in the top-right of the webview provides:

- Active-lens dropdown (`LENS_UI.CTRLPANEL.1`): switch active lens
- New (+) button (`LENS_UI.CTRLPANEL.2`): create a named lens; auto-activates; toast shown
- Rename pencil (`LENS_UI.CTRLPANEL.3`): inline rename of active lens
- Delete trash (`LENS_UI.CTRLPANEL.4`): delete with confirmation; if active/default, unsets accordingly

No Save or Discard buttons. Auto-save model: any state change writes the lens file
immediately via a ~500ms debounce (`PERSISTENCE.AUTOSAVE`).

**Auto-create.** On first drag-release when no lens is active, the viewer silently creates
a lens named `default` and sets `meta.default_lens` (`PERSISTENCE.AUTOCREATE`). Toast shown.

**Default lens.** If `meta.default_lens` is set, it auto-applies after boot. The active
lens name is in-memory only on `PanelEntry`; it is never written to workspaceState.

**Diagnostics.** When a lens references stale UIDs, a dismissable banner at the bottom of
the panel lists each diagnostic. The viewer never refuses to render.

**Intentlinks visibility.** Each lens carries a list of which intentlinks are visible via the
existing `LensConfig.intentlinks: list[Uid]` field. Not all intentlinks are shown in every
lens. This field is per-lens configurable and is separate from, and unchanged by, the
`LensConfig.nodes` schema redesign (`LENSSCHEMA.NODESHAPE`).

---

## Persistence policy
<!-- Lines 147-164 -->

| What | Where | Notes |
|------|-------|-------|
| Field text edits (name, intent, constraints) | IG YAML file | Canonical, git-tracked, shareable |
| Named lenses | IG YAML file (lenses dict) | Canonical |
| Per-node LOD | Lens entry (inside IG file) | User-decidable visual state |
| Per-node position (x, y) | Lens entry (inside IG file) | Parent-relative; center coordinates (MVP) |
| Active lens name | In-memory (PanelEntry) | Lost on panel close; re-derived from default_lens |
| Pan / zoom | workspaceState (ephemeral) | Machine-local; not git-tracked |

**Position coordinate frame:** parent-relative (A2). `(x, y)` is offset from parent
top-left. ROOT position is implicit `(0, 0)` and never stored. Position stores the
Cytoscape node CENTER (not top-left), matching `cy.node.position()` API directly.
Tradeoff: LOD toggle shifts the visible rect around the center — acceptable for MVP
(`risky | unvalidated` in `PERSISTENCE.POSITIONS`).

---

## Invariants (the rules nothing may break)
<!-- Lines 167-181 -->

- **INV-1** (`INVARIANTS`): No `vscode.*` API in the webview bundle.
- **INV-2** (`INVARIANTS`): No `cytoscape` or `elkjs` imports in the extension host.
- **INV-3** (`INVARIANTS`): CSP — no inline scripts, no eval, no blob script sources.
- **INV-4** (`INVARIANTS`): No relayout on LOD toggle. ELK runs once at structural mount.
- **INV-5** (`INVARIANTS`): IG file is canonical; viewer state is derivative.
- **INV-6** (`INVARIANTS`): No optimistic DOM update for edits. Write must succeed first.
- **INV-7** (`INVARIANTS`): Overlay visibility is coupled to node visibility. If node is not
  visible on canvas (parent collapsed, off-screen), its overlay must not be visible.
- **INV-8** (`INVARIANTS`): **Lens is the only store for user-authored visual state.** Product
  nodes hold no rendering data. Positions and LOD assignments belong exclusively in
  `LensConfig.nodes` entries.

---

## Non-goals
<!-- Lines 184-194 -->

- No lens diff/merge UI.
- No agent dialogue UI (chat pane, elicitor integration).
- No reintegrate UI. Use `ig-tool lens reintegrate`.
- No add/remove/reparent nodes from the GUI (Phase 1/2 boundary).
- No WebGL renderer (dashed edges require canvas).
- No web-worker elkjs (deferred).
- No `WebviewPanelSerializer` for cross-session state restore (deferred).

---

## Open questions / known issues
<!-- Lines 197-220 -->

| Node | Summary |
|------|---------|
| `LAYOUT.RECT` | Code has 320x360 (Amend 4); canonical target is 240x180 per user. Must update before next build. |
| `LAYOUT.ALGORITHM` | MVP = ELK force globally. Phase 2 per-compound algorithm choice deferred; aesthetic regression possible. |
| `LAYOUT.OVERLAY` | Orphan-overlay fix (node.visible() guard in tickOne) written but unverified in current build. |
| `EDITING.MODES` | Edit mode exit via blur is glitchy; needs pointerdown-outside-card listener. |
| `EDITING.SCOPE` | Whole-node form not yet implemented; current code does per-field dbltap hit-testing. |
| `EDITING.EXIT` | Exit condition undecided/unimplemented (document-level pointerdown containment check). |
| `EDITING.PERSISTENCE` | Silent fileHash mismatch drops edits with no visible feedback. Three-fix scope documented. |
| `EDITING.ENTER` | Camera center on entry not yet implemented; relies on INTERACTION.FOCUS (see intentlink EDITING.ENTER → INTERACTION.FOCUS). |
| `LENS_UI` | Control panel (top-right) not yet present in panel. |
| `LENS_UI.CTRLPANEL` | Four controls (dropdown, new, rename, delete) not yet implemented. |
| `PERSISTENCE.POSITIONS` | cy.on('free') not wired; no positions currently saved. Position schema requires LENSSCHEMA IG-core changes first. |
| `PERSISTENCE.AUTOSAVE` | Debounced write not yet implemented. |
| `PERSISTENCE.AUTOCREATE` | First-drag auto-create not yet implemented. |
| `LENSSCHEMA` | LensNodeEntry schema change not yet implemented in the core library. |
| `LENSSCHEMA.SPECDOC` | LENS_REDESIGN_SPEC.md not yet updated to reflect new LensNodeEntry shape, new CLI subcommands, and V-POS1/V-POS2 validation rules. |
| `INTERACTION.DRAG` | Bounds-clip and snap-back on drag not yet implemented. |
| `DIAGNOSTICS.EDIT_CONFLICT` | Conflict banner is dismissable (too easy to miss). Must become non-dismissable. |
| `DIAGNOSTICS.LOGGING` | ok=false events not yet logged to output channel. |

---

## Tree appendix
<!-- Lines 223-273 -->

```
ROOT: vscode_viewer Projection
├── AUDIENCE: Primary Audience
├── OPERATIONS: User Operations
├── INTERACTION: Interaction Model
│   ├── INTERACTION.GESTURES: Gesture Vocabulary
│   ├── INTERACTION.MODES: View and Edit Modes
│   ├── INTERACTION.FOCUS: Camera Focus Rules
│   └── INTERACTION.DRAG: Drag Gesture Spec
├── LAYOUT: Visual Layout
│   ├── LAYOUT.LOD: LOD Tier Definitions
│   ├── LAYOUT.RECT: Node Rect Derivation  [derived: lean 160x60, full 240x180]
│   ├── LAYOUT.OVERLAY: HTML Overlay Tracking  [data_registry: min_readable_height 50px]
│   ├── LAYOUT.WRAP: Wrap Not Truncate
│   ├── LAYOUT.CUES: Always-Visible Expand/Collapse Cues
│   └── LAYOUT.ALGORITHM: Layout Algorithm  [MVP: ELK force + force.fixed]
├── EDITING: Bidirectional Editing
│   ├── EDITING.ENTER: Edit Mode Entry  [→ INTERACTION.FOCUS for camera-center rule]
│   ├── EDITING.SCOPE: Whole-Node Edit Form
│   ├── EDITING.EXIT: Edit Mode Exit Condition
│   └── EDITING.PERSISTENCE: Edit Write-Back
├── LENS_UI: Lens Control Panel
│   ├── LENS_UI.SELECTOR: Control Panel Layout
│   ├── LENS_UI.SOURCES: Lens Data Sources
│   ├── LENS_UI.DIAGNOSTICS: Stale-UID Diagnostics Banner
│   └── LENS_UI.CTRLPANEL: Control Panel Controls
│       ├── LENS_UI.CTRLPANEL.1: Active-Lens Dropdown
│       ├── LENS_UI.CTRLPANEL.2: New Lens Button
│       ├── LENS_UI.CTRLPANEL.3: Rename Active Lens
│       └── LENS_UI.CTRLPANEL.4: Delete Active Lens
├── PERSISTENCE: Persistence Policy
│   ├── PERSISTENCE.IG_FILE: IG File Writes
│   ├── PERSISTENCE.POSITIONS: Node Position Persistence  [lens-based, parent-relative, center MVP]
│   ├── PERSISTENCE.WORKSPACE_STATE: Ephemeral workspaceState  [pan/zoom only]
│   ├── PERSISTENCE.LENS_STATE: Active Lens -- In-Memory
│   ├── PERSISTENCE.AUTOSAVE: Debounced Auto-Save  [~500ms debounce, single-flight]
│   └── PERSISTENCE.AUTOCREATE: Auto-Create Default Lens  [first-drag trigger]
├── DIAGNOSTICS: Diagnostics and Logging
│   ├── DIAGNOSTICS.LENS_BANNER: Lens Diagnostics Banner
│   ├── DIAGNOSTICS.EDIT_CONFLICT: Edit Conflict Notification
│   └── DIAGNOSTICS.LOGGING: Output Channel Logging
├── NON_GOALS: Explicit Non-Goals
├── INVARIANTS: Cross-Cutting Invariants
└── LENSSCHEMA: IG-Core Lens Schema Changes
    ├── LENSSCHEMA.NODESHAPE: LensNodeEntry Shape  [dict[uid, {lod, position?}]]
    ├── LENSSCHEMA.MIGRATION: Fixture Migration Script
    ├── LENSSCHEMA.IGCMDS: New ig-tool Subcommands  [set-position, clear-position]
    ├── LENSSCHEMA.VALIDATION: Position Validation Rules
    └── LENSSCHEMA.SPECDOC: Spec Document Update  [LENS_REDESIGN_SPEC.md §4/§6/§8]
```
