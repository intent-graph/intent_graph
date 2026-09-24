# Implementation map (developer reference)

This document is **implementation-only**. The product spec — what the viewer
should do and why — lives in the PIG at
[`projection_ig/vscode_viewer.ig.yaml`](../projection_ig/vscode_viewer.ig.yaml)
and is queried with `ig-tool` (e.g. `ig-tool query --node LAYOUT.CUES -g
projection_ig/vscode_viewer.ig.yaml`). When this README and the PIG disagree,
the PIG wins.

The map below points at where each subsystem lives and which design choices
shape its code. It assumes you've at least skimmed the PIG's ROOT,
`INTERACTION`, `LAYOUT`, `EDITING`, `LENS_UI`, `PERSISTENCE`, and `INVARIANTS`
nodes.

---

## Top-level layout
<!-- Lines 19-61 -->

```
src/
├── extension.ts                    Activation. Output channel, command registration.
├── editor/
│   └── IntentGraphEditorProvider.ts  Custom editor host. PanelEntry, file watcher,
│                                      messenger handlers, autosave debounce.
├── host/
│   ├── autosave.ts                 Position write + autocreate 'default' lens.
│   ├── lensCrud.ts                 Lens create / rename / delete.
│   ├── lensApply.ts                lensConfigToPayload (host-side translation).
│   ├── yamlEdit.ts                 Field/node edit YAML mutation + fileHash check.
│   ├── fileHash.ts                 SHA-256 of file content (CRLF-normalised).
│   └── loadGraph.ts                Subprocess call into ig-tool to parse the IG.
├── igtool/
│   └── igToolClient.ts             Spawn + JSON streaming for ig-tool subprocess.
├── messaging/
│   └── messageTypes.ts             Wire contract for ALL host↔webview RPC.
├── shared/
│   └── graphTypes.ts               Types reused by host and webview bundles.
└── webview/
    ├── index.html.ts               HTML shell. Defines the DOM IDs the rest binds to.
    ├── main.ts                     App orchestrator. Lifecycle, lens UX, reload paths.
    ├── messaging.ts                Webview-side RPC client (mirrors messaging/).
    ├── state.ts                    WebviewState: nodeLOD, collapseSet, fileHash, viewport.
    ├── elkBridge.ts                ELK layout invocation (one shot at structural mount).
    ├── cyMount.ts                  Cytoscape construction; container wheel listener.
    ├── styles.css                  All overlay / cue / selector styling.
    ├── interaction/                Gesture dispatch.
    │   ├── gestureRouter.ts          Single owner of cy + document-level listeners.
    │   └── state.ts                  GestureState type + factory.
    ├── overlay/
    │   ├── htmlOverlayLayer.ts     Full-LOD card lifecycle, edit-mode entry/exit.
    │   └── cueLayer.ts             Dedicated cue layer for every compound.
    └── styles/
        └── cyStyle.ts              Cytoscape stylesheet.
```

Tests under [`test/unit/`](../test/unit/) are pure-logic; the user-facing
acceptance gate is manual F5 verification (see [Acceptance](#acceptance)).

---

## The five user gestures: where each lives
<!-- Lines 64-81 -->

PIG `INTERACTION.GESTURES` enumerates them. Implementation pointers, in order:

| # | Gesture | Owner | Key file:line |
|---|---|---|---|
| 1 | Single-click → LOD toggle | `GestureRouter.wireCytoscapeGestures` (onTap) | `interaction/gestureRouter.ts::onTap` |
| 2 | Double-click → enter edit | `GestureRouter.wireCytoscapeGestures` (onDbltap); promotes lean→full first | `interaction/gestureRouter.ts::onDbltap` |
| 3 | Cue click → expand/collapse | `CueLayer.handleClick` → `ec.collapse|expand` | `overlay/cueLayer.ts::createCueButton`, `handleClick` |
| 4 | Drag → persist position | `GestureRouter.wireDragGestures` (onGrab + onFree, snap-back, wasActualDrag) | `interaction/gestureRouter.ts::wireDragGestures` |
| 5 | Lens menu (switch / + / pencil / trash) | `LensSelector` + `App.handleCreate/Rename/Delete` + `lensCrud.ts` | `webview/main.ts::LensSelector`, `host/lensCrud.ts` |

**Edit-mode exit** (PIG `EDITING.EXIT`) is the document-level half of the
router: `wireDocumentGestures` attaches `pointerdown` (capture-phase) and
`keydown` (Escape) listeners that read the editing card's bounding rect and
call `commitNodeEdit` / `cancelNodeEdit` on the overlay layer.

---

## Three orthogonal state machines
<!-- Lines 84-100 -->

PIG `INTERACTION.MODES` defines them. The router enforces orthogonality.

| Machine | States | Transitioned by | Tracked on |
|---|---|---|---|
| LOD (per node) | `lean` ⇆ `full` | tap, applyLens | `state.nodeLOD: Map<Uid, NodeLOD>` (shared with `WebviewState.nodeLOD`) |
| Compound (per parent) | `expanded` ⇆ `collapsed` | cue click only (INV-9) | `state.collapseSet: Set<Uid>` (shared with `WebviewState.collapseSet`) |
| Mode (global) | `view` ⇆ `edit` | dbltap / outside-click / Escape | `state.editingUid: Uid \| null` |

The `GestureState` (in `interaction/state.ts`) is constructed via
`createGestureStateFrom(parts)` so its `nodeLOD` and `collapseSet` are the
**same instances** held by `WebviewState`. This is deliberate: the existing
snapshot/restore-on-reload code in `main.ts` already operates on those Maps,
and the router would otherwise double-track them.

---

## Key design choices
<!-- Lines 103-103 -->

### 1. Single dispatch path for every gesture
<!-- Lines 106-114 -->

Every Cytoscape pointer event and every document-level pointer/keydown event
flows through `GestureRouter`. No other module attaches `cy.on('tap'|'dbltap'|
'grab'|'free')` or `document.addEventListener('pointerdown'|'keydown')` for
gesture purposes. (The `LensSelector` keeps its own narrow document listeners
for click-outside and Escape, scoped to the dropdown — these don't dispatch
gestures, they just open/close UI.) This invariant kills the class of
prior-wave bugs where two handlers raced for the same event.

### 2. State guards, not timing windows
<!-- Lines 117-123 -->

The previous tap-vs-dbltap race used a 350 ms window. The router replaces
this with `state.editingUid`: dbltap fires before the trailing synthetic taps
(documented Cytoscape behaviour), so dbltap can stamp `state.editingUid` and
the tap handler bails on `state.editingUid === thisUid`. This is observable
and testable without a clock.

### 3. Cue layer is an independent DOM tracker
<!-- Lines 126-134 -->

`overlay/cueLayer.ts` owns one `<button class="ig-compound-cue">` per compound
(both `node.isParent()` and `cy-expand-collapse-collapsed-node` stand-ins),
appended to `#ig-overlay-root`. It has its own `cy.on('render')` listener
that positions every button per frame. This is **deliberately decoupled**
from `htmlOverlayLayer`'s overlay-card map, which is what fixed the prior
"no +/- in lean mode" bug — the overlay map only tracked full-LOD cards, so
lean compounds had no cue.

### 4. Library cue disabled
<!-- Lines 137-144 -->

`expand-collapse` is configured with `cueEnabled: false` in
[`cyMount.ts`](../src/webview/cyMount.ts#L153). The library's API methods
(`expand`, `collapse`, `isCollapsible`, `isExpandable`) remain in use; only
its canvas-drawn cue and tap handler are off. This ensures every user-driven
compound transition goes through the DOM button → CueLayer → ec API path
(INV-9).

### 5. Lens picks are host-mediated
<!-- Lines 147-154 -->

`LensSelector.onPick` sends `SelectLensRequest` to the host instead of
applying the lens client-side. The host updates `entry.activeLensName` and
broadcasts `ApplyLensNotification`; the webview's existing `onApplyLens`
handler does the visual work. This is the difference that makes lens picks
**survive reload**: the prior client-only path lost the active lens any time
the file watcher fired a structural reload.

### 6. Lens CRUD writes go through `lensCrud.ts`
<!-- Lines 157-163 -->

`host/lensCrud.ts` mirrors the YAMLMap-aware pattern of `host/autosave.ts`
(parseDocument → setIn/deleteIn → toString → writeFile, never sed/regex).
Unlike autosave, CRUD does **not** set `entry.selfWritePath` because we
*want* the file watcher to fire — the lens topology changed and the webview
needs to rebuild its dropdown.

### 7. INV-6 (no-optimistic-DOM) is preserved across reloads
<!-- Lines 166-172 -->

The pendingEdits Map and `restorePreEditDOM` live on `htmlOverlayLayer`.
When the file watcher fires while a node is in
edit mode, the overlay teardown clears `editingNodeUid` and the router's
`gestureState.editingUid = null` is reset on the next mount, so a stale
edit cannot leak across the reload boundary.

### 8. Lens visibility is membership-derived (PIG `LENSSCHEMA.VISIBILITY`)
<!-- Lines 175-218 -->

Compound expand/collapse state is **not** stored as an explicit field. It is
derived from lens membership of the compound and its children:

- compound C in lens AND ≥1 of C's children in lens → **expanded**
- compound C in lens AND no child of C in lens → **collapsed**
- C not in lens → **absent** (not displayed)

The canonical statement of this rule lives in PIG node
`LENSSCHEMA.VISIBILITY` (query: `ig-tool query --node LENSSCHEMA.VISIBILITY
-g projection_ig/vscode_viewer.ig.yaml`). The pure function realising it is
[src/shared/lensVisibility.ts](../src/shared/lensVisibility.ts)::`deriveLensVisibility`.
All visibility decisions (`applyLens`, gesture handlers, tests) consult that
function — never re-derive the rule inline.

The `lod` field on a compound entry is **meaningless for visibility** — it
is preserved on round-trip but ignored. `lod` is only meaningful for leaves
(`'lean'` default vs `'full'` overlay-shown). This separation lets a user
promote a compound to full LOD for inspection without that override
conflating with whether the compound is collapsed.

The corollary: every gesture that mutates visibility (cue collapse, cue
expand) must update `lens.nodes` membership. Collapse removes all
descendants of the target compound from the lens; expand adds direct
children. Without this, in-memory cytoscape state diverges from the
on-disk lens, and close/reopen resets the visible tree.

**New-lens default state.** A freshly created lens is initialised with
`lens.nodes = {ROOT, ROOT.children}` — root plus its direct children only.
By the rule, ROOT renders expanded (children in lens) and each L1 compound
renders collapsed (its grandchildren are not in the lens). This shows the
user the top-level structure as the starting point rather than the fully
expanded graph. Implemented in `host/lensCrud.ts::createLens` which now
takes a `topology` argument (`{rootUid, childrenOfRoot}`).

**Renderer pragmatic (applyLens).** Cytoscape always mounts the full tree;
"not displayed" cannot be realised perfectly. The renderer compromises by
collapsing absent compounds. Concretely, the set of cytoscape nodes to
collapse is `collapsedCompoundUids ∪ (compounds absent from the lens)`.
The pure rule describes intent; this union happens in `applyLens`, not in
`deriveLensVisibility` (which stays a faithful realisation of the rule).

---

## Reload paths (all the ways the cy mount can rebuild)
<!-- Lines 221-242 -->

`main.ts::loadAndRender(isReload)` is the funnel. Triggers:

1. **Initial load** — App constructor → `run()` → `loadAndRender(false)`.
2. **External file change** — file watcher → `GraphChangedNotification` →
   `handleGraphChanged()` → `loadAndRender(true)`.
3. **Edit conflict** — `EditConflictNotification` banner Reload button →
   `handleGraphChanged()`.
4. **Error retry** — error banner Retry button → `loadAndRender(isReload)`.
5. **Metadata-only reload** — same triggers as #2 but `state.diff()` returns
   `metadata`; the existing cy is kept and `overlayLayer.refreshContent` runs
   in-place. No new mount.

Lens CRUD writes deliberately go through path 2 so the
webview sees the new lens dict.

The active lens survives reloads because the host re-applies it from
`entry.activeLensName` in the `LoadGraphRequestType` handler (lines ~342–347
in `IntentGraphEditorProvider.ts`).

---

## Acceptance
<!-- Lines 245-272 -->

Unit tests (`node --test test/unit/*.test.mjs`) are a baseline-not-acceptance
check: they verify pure logic, file-scope invariants (no `vscode` import in
webview, no `cytoscape` import in host), and the source-text properties that
catch refactor regressions.

The user-facing acceptance gate for any change to interaction code is
**manual F5 verification** against `python_defaults.ig.yaml` (75 nodes, 4 L1
modules — a real graph with real compounds), used at every
step of interaction development. Browser-driven e2e tests are deliberately deferred (see
`test/unit/gestureRouter_integration.test.mjs` header for rationale).

To F5:

```
cd vscode_extension/intentgraph-vscode
npm run compile
# Then in VS Code: Run > Start Debugging (F5). Open python_defaults.ig.yaml
# (in this folder).
```

Exercise: tap a leaf to toggle LOD; double-click to edit; click outside or
press Escape to exit; click a compound's cue to expand/collapse; drag a node
and verify the position survives a reload; create / rename / delete a lens
via the top-right buttons.

---

## Backups
<!-- Lines 275-287 -->

The PIG has its own backup directory at `projection_ig/.backups/` — a timestamped copy
taken before risky edits. To roll back to one:

```
cp projection_ig/.backups/vscode_viewer.ig.yaml.<timestamp> \
   projection_ig/vscode_viewer.ig.yaml
ig-tool validate -g projection_ig/vscode_viewer.ig.yaml
node --test test/unit/*.test.mjs
```

---

## When in doubt
<!-- Lines 290-299 -->

- WHAT the viewer should do: query the PIG (`ig-tool query --node UID -g
  projection_ig/vscode_viewer.ig.yaml -o /tmp/node.yaml`).
- HOW it does it: this file + the source.
- Some seemingly-roundabout choices exist for empirical reasons (notably the
  cue's DOM-button architecture, adopted after a CSS/SVG hover approach
  proved unreliable, and an empirical-first acceptance gate for edit fixes).

---

## Observability (trace)
<!-- Lines 302-313 -->

Every panel session emits a structured JSONL trace to disk. The purpose: any
bug can be reconstructed after the fact by reading the log — which gestures
fired, which suppression decisions ran, which compound transitions happened
and why, whether the lens menu mounted, what the file watcher saw, and which
helper wrote the file. Telemetry is on by default; absence from the log is a
diagnostic signal (not silence).

**Canonical spec:** PIG node `OBSERVABILITY`
(`ig-tool query --node OBSERVABILITY -g projection_ig/vscode_viewer.ig.yaml`).
The PIG is authoritative; this section is a developer pointer to the code.

### Architecture
<!-- Lines 316-328 -->

There are **two side-by-side wrapper modules** that together enforce the trace
contract by construction (no callsite can bypass them):

- `src/webview/overlay/ecWrap.ts` — every `ec.expand` / `ec.collapse` /
  `ec.expandRecursively` / `ec.collapseRecursively` call goes through here.
  Direct calls anywhere else in `src/` fail the grep test in
  `test/unit/trace.test.mjs`. This is INV-9 enforced by trace shape.
- `src/host/diskWrite.ts::writeIgFile` — every `writeFile` to the IG file
  goes through here. Each write emits `kind:'fileWrite'` with the caller name
  (`autosave.parseAndMutateLensPosition`, `lensCrud.createLens`, etc.). When a
  reload loop appears, this is what tells you who's writing.

### Key files
<!-- Lines 331-352 -->

- `src/host/trace.ts` — `TraceSink` class. Path resolution, append queue
  (single-flight Promise chain), rotation (keeps last 5 sessions), symlink
  management with regular-file fallback. `sessionStart` entry includes
  `schemaVersion`, `pid`, `vscodeVersion`, `traceDir`, `pathSource`
  (`'configured'` / `'workspaceFolder'` / `'extensionDirFallback'`),
  `traceFile`. `sessionEnd` entry on `close()` so a reader can distinguish a
  clean shutdown from a trace cut off mid-event.
- `src/host/diskWrite.ts` — `writeIgFile` + `registerTraceSink`. The host
  calls `registerTraceSink(...)` once per panel construction; every host
  helper that writes the IG file imports `writeIgFile` and uses it instead
  of `fs.writeFile`.
- `src/webview/trace.ts` — webview emitter: monotonic `seq`, `corr()` helper,
  `initTrace()` wiring. Zero cost when disabled (early return before any
  allocation). `initTrace()` runs in App's constructor BEFORE
  `new LensSelector()` so the `lensSelectorMounted` entry is captured.
- `src/webview/overlay/ecWrap.ts` — see "Architecture" above.
- `src/editor/IntentGraphEditorProvider.ts` — host-side trace sink
  construction; the **three-gate reload pipeline** in `scheduleReload` (see
  below); `pendingReloadCorr` threading from watcher fire to
  `applyLensReinstate`.

### The three-gate reload pipeline
<!-- Lines 355-375 -->

`scheduleReload` runs three checks in order before triggering a reload. Two
of them log a `kind:'reloadSuppressed'` entry instead of reloading:

1. **selfWritePath suppression.** If `entry.selfWritePath === uri.fsPath`,
   the watcher fired in response to our own write (set by autosave/lensCrud
   paths just before they call `writeIgFile`). Emit
   `{kind:'reloadSuppressed', cause:'selfWritePathMatch'}`.
2. **Content-hash gate.** Read the file, compute SHA-256,
   compare to `entry.lastLoadedFileHash`. If they match, the watcher fired
   on a metadata-only event (macOS FSEvents and VS Code's
   `FileSystemWatcher` both do this). Emit
   `{kind:'reloadSuppressed', cause:'contentUnchanged', hashPrefix:'…'}`.
   This is the defensive layer — the right thing regardless of why the
   watcher fired.
3. **Schedule the reload.** Generate a fresh `corr`, stamp it on
   `entry.pendingReloadCorr`, emit `{kind:'reload', corr:'…'}` with both
   hash prefixes, and `setTimeout` for `FILE_WATCHER_DEBOUNCE_MS` (300 ms).
   When `LoadGraph` completes, the host emits `kind:'applyLensReinstate'`
   with the same `corr` so a reader can grep one chain.

### Two `seq` counters
<!-- Lines 378-388 -->

`seq` is monotonic **per emitter, not panel-wide**:

- The webview's `_seq` (`src/webview/trace.ts`) advances for every router /
  cue / overlay / lens / app event.
- The host's `entry.hostSeq` advances for every `host` / `fileWrite` /
  reload / lens-CRUD event.

The two streams interleave by `ts` in the file. To follow a chain across
both emitters, use the `corr` field, not `seq`.

### How to read
<!-- Lines 391-405 -->

```sh
tail -200 <workspace>/.intentgraph-traces/latest.jsonl   # workspace default
tail -200 test/traces/latest.jsonl                       # fallback (no workspace)

# Follow one chain end-to-end:
grep '"corr":"c-12-a3f7"' <workspace>/.intentgraph-traces/latest.jsonl

# Find every disk write during an idle window:
grep '"kind":"fileWrite"' <workspace>/.intentgraph-traces/latest.jsonl

# Find every suppressed reload (good — gate is doing its job):
grep '"kind":"reloadSuppressed"' <workspace>/.intentgraph-traces/latest.jsonl
```

### How to disable
<!-- Lines 408-411 -->

Set `intentgraph.trace.enabled: false` in workspace settings, or run the
command palette entry **IntentGraph: Toggle Trace**.

### Example trace lines
<!-- Lines 414-420 -->

```json
{"schemaVersion":1,"ts":"2026-04-30T11:34:01.123Z","seq":0,"src":"host","kind":"sessionStart","data":{"pid":67799,"vscodeVersion":"1.118.1","traceDir":"/path/.intentgraph-traces","pathSource":"workspaceFolder","traceFile":"/path/.intentgraph-traces/trace-2026-04-30T11-34-01Z.jsonl"}}
{"ts":"2026-04-30T11:34:02.456Z","seq":12,"src":"router","kind":"dbltap","corr":"c-12-a3f7","data":{"uid":"DISCOVER","currentLod":"lean","action":"promoteThenEdit"}}
{"ts":"2026-04-30T11:34:03.001Z","seq":3,"src":"host","kind":"reloadSuppressed","data":{"reason":"watcher","uri":"/path/file.ig.yaml","cause":"contentUnchanged","hashPrefix":"d41d8cd98f00"}}
{"ts":"2026-04-30T11:34:04.117Z","seq":7,"src":"host","kind":"fileWrite","cause":"autosave.parseAndMutateLensPosition","data":{"path":"/path/file.ig.yaml","bytes":42301,"tmp":false,"selfWritePathSet":null}}
```
