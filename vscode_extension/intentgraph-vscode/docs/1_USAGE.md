# 1 — Usage

How to install, launch, and interact with the IntentGraph viewer. For the deeper "why," see [2_ARCHITECTURE.md](2_ARCHITECTURE.md).

## Table of Contents

1. [Install & first launch](#install--first-launch) _(Lines 25-28)_
   1. [Install it (recommended — use the viewer in every editor window)](#install-it-recommended--use-the-viewer-in-every-editor-window) _(Lines 31-55)_
   1. [Develop it (F5 — Extension Development Host)](#develop-it-f5--extension-development-host) _(Lines 58-72)_
1. [File types recognized](#file-types-recognized) _(Lines 75-92)_
1. [Opening a file as a graph](#opening-a-file-as-a-graph) _(Lines 95-109)_
1. [Interaction model](#interaction-model) _(Lines 112-130)_
1. [Reading the rendered graph](#reading-the-rendered-graph) _(Lines 133-154)_
1. [Live reload](#live-reload) _(Lines 157-177)_
1. [Settings](#settings) _(Lines 180-198)_
1. [Limits and known limitations](#limits-and-known-limitations) _(Lines 201-210)_




---

## Install & first launch
<!-- Lines 25-28 -->

The extension is not on the marketplace; it installs from this source clone. There are
two ways to run it — pick by whether you want to _use_ the viewer or _develop_ it.

### Install it (recommended — use the viewer in every editor window)
<!-- Lines 31-55 -->

Run the idempotent installer once:

```bash
cd vscode_extension/intentgraph-vscode
./bootstrap.sh          # add --yes to accept all prompts non-interactively
```

`bootstrap.sh` builds `dist/`, ensures `ig-tool` is installed, and **symlinks** this
folder into every detected editor's extensions dir (VS Code, Cursor, Insiders, VSCodium,
Windsurf) as `intentgraph.intentgraph-0.0.1`. After it finishes, reload your editor
window (`Cmd+Shift+P` → `Developer: Reload Window`) and clicking any `*.ig.yaml` /
`*.ig.json` opens the IntentGraph Viewer automatically, in any window — no F5, no dev host.

Because it's a **symlink to the source**, deploying a code change is just: rebuild and
reload.

```bash
./bootstrap.sh --yes    # rebuilds dist/ only if sources changed; re-verifies symlinks
# then: Cmd+Shift+P → Developer: Reload Window
```

Other flags: `--no-build` (skip the build when `dist/` is already current),
`--uninstall` (remove the symlinks; the `ig-tool` CLI install is left intact).

### Develop it (F5 — Extension Development Host)
<!-- Lines 58-72 -->

For iterating on the extension itself, open the `intentgraph-vscode/` folder in VS Code
and press **F5**. VS Code launches a second window — the **Extension Development Host**,
title bar tagged `[Extension Development Host]` — running the extension from the on-disk
`dist/` build, isolated from your installed copy. To pick up source changes: stop the
debug session (`Cmd+Shift+P` → `Debug: Stop`), recompile (`npm run compile`), press F5
again — or run `npm run watch` alongside for incremental rebuilds.

You need:
- VS Code ≥ 1.85.
- Node ≥ 18 (verified by the build script).
- `ig-tool` installed and on PATH (the extension uses it for one purpose only: a "ping" smoke test that confirms the binary is reachable; the viewer does not invoke it during normal use).

---

## File types recognized
<!-- Lines 75-92 -->

The extension contributes a custom editor for these filename patterns:

| Pattern | Intent |
| --- | --- |
| `*.ig.json` | IntentGraph in JSON |
| `*.ig.yaml` | IntentGraph in YAML |
| `*.intentgraph.json` | Same; alternative naming |
| `*.intentgraph.yaml` | Same |
| `*.lens.json` | Lens snapshot in JSON |
| `*.lens.yaml` | Lens snapshot in YAML |

Plain `*.json` or `*.yaml` are **not** intercepted — the editor only activates on these specific extensions to avoid hijacking unrelated files. If you want to view an arbitrary `.json` graph, either rename it (`mv graph.json graph.ig.json`) or use `View: Reopen Editor With…` (see next section).

The file's content must follow the canonical IG schema: top-level `meta`, `nodes`, `treearcs`, and (optionally) `intentlinks`. Validate with `ig-tool validate -g <path>` before opening.

---

## Opening a file as a graph
<!-- Lines 95-109 -->

Three ways:

1. **Filename match.** If the file ends in one of the patterns above, opening it (`Cmd+O`, click in Explorer, etc.) auto-launches the IntentGraph Viewer.
2. **Right-click → Open With.** Right-click a `.json`/`.yaml` in the Explorer sidebar → `Open With…` → select **IntentGraph Viewer**. Useful for files that don't match the patterns.
3. **Reopen current editor.** With a file already open in the default text editor: `Cmd+Shift+P` → `View: Reopen Editor With…` → select **IntentGraph Viewer**.

If **IntentGraph Viewer** doesn't appear in the picker:
- Check the title bar — you must be in the Extension Development Host window, not your main VS Code window.
- Run `Cmd+Shift+P` → `Developer: Show Running Extensions` and look for `intentgraph.intentgraph-vscode`. If it's not listed or shows an error, the extension didn't activate; see [3_DEBUGGING.md](3_DEBUGGING.md).

The first paint shows a spinner over the graph area while the host parses the file and the webview lays it out. For a 75-node graph this is well under a second.

---

## Interaction model
<!-- Lines 112-130 -->

Two gestures, two distinct verbs — by design (see [2_ARCHITECTURE.md §Interaction model](2_ARCHITECTURE.md#interaction-model)):

| Gesture | Effect |
| --- | --- |
| Click `+` / `−` cue (small box at top-left of a compound) | Expand or collapse that compound's subtree. Structural — changes which nodes are visible. |
| Click a node body | Toggle that one node between `lean` and `full` LOD. Inspectional — shows or hides this node's content. |
| Double-click a node body | Enter inline edit mode (promoting to `full` LOD if needed). The `name`, `intent`, `epistemic_state`, and constraint lines become editable in place. Enter or clicking outside the card commits; Escape cancels. Empty values are rejected. Edits write back to the `.ig.yaml` with comments preserved. |
| Click empty canvas | No effect, except while editing — an outside click commits the in-progress edit. |
| Click outside the webview | No effect. |
| Click status bar item (bottom-right of VS Code) | `cy.fit` — recentre and zoom to fit all visible nodes. |
| Drag-pan, scroll-zoom | Standard Cytoscape gestures. |

Multiple nodes can be in `full` LOD simultaneously. The state persists across reload (see §Live reload). LOD does not trigger relayout — expanded nodes may overlap their neighbors. Toggle back to `lean` to recover.

The `+`/`−` cues are HTML overlays drawn outside the node body, so cue clicks never trigger LOD toggle. If you find yourself clicking a node and getting a collapse, you're hitting the cue area; aim for the rectangle's interior.

---

## Reading the rendered graph
<!-- Lines 133-154 -->

**Boxes (nodes).** Round-rectangles. Lean LOD shows the node's `name` only; full LOD shows `name`, `intent` text, `[epistemic_state]`, and up to three `• constraint` bullets. Risky/speculative/undecided epistemic states get a yellow border (the threshold is the lowercased state starting with one of those words).

**Compound boxes.** Nodes that have children appear as compounds — bigger rectangles with dashed borders, labels at the top-left, containing their children. Treearcs (the parent-child refinement edges) are NOT drawn as edges; they're encoded as the compound nesting itself.

**Edges (intentlinks).** Drawn between nodes with arrowheads. Style varies by inferred `edgeType`:
- `dataflow` — blue, thicker, single arrowhead.
- `requires` — gray, default.
- `conflicts` — red, double-headed (both endpoints carry an arrow).
- `refines` — purple, dashed.
- `unspecified` — faint gray, default.

EdgeType is inferred heuristically from the link's `intent` text (keywords like "produces", "requires", "conflicts with", "refines"). The IG core does not yet carry a first-class `kind` field; that may change in a future revision.

**Meta-edges** (the thicker solid lines that appear when you collapse a compound) are aggregated from many sub-edges. Their endpoints are the compound itself, not the original nodes.

**Minimap.** Bottom-right corner. Pan-and-zoom indicator; drag the rectangle to navigate.

**Status bar.** Bottom-right of VS Code chrome (NOT inside the webview): shows live node and link counts.

---

## Live reload
<!-- Lines 157-177 -->

The viewer watches the open file via two parallel paths:

1. **Filesystem watcher** (`vscode.workspace.createFileSystemWatcher`) — catches changes from outside VS Code (e.g., `ig-tool node set …`, edits in another editor app, CLI scripts).
2. **Save event** (`vscode.workspace.onDidSaveTextDocument`) — catches saves from any VS Code editor instance, even on filesystems where the FS watcher is flaky.

Either signal triggers a 300ms-debounced reload. The reload classifies the change:

| Diff classification | Behavior |
| --- | --- |
| **Metadata-only** (intent / epistemic / constraints / name change; node set + treearc set + intentlink endpoints unchanged) | Skip ELK + remount; update node `data` in place. Node label refreshes to new `name`. Nodes currently in `full` LOD re-render with the new content. EdgeType is reinferred. Viewport and collapse state untouched. |
| **Structural** (any node added or removed, any treearc changed, any link endpoint changed) | Snapshot viewport + collapse-set + LOD-set → tear down Cytoscape → rebuild ELK + remount → restore viewport, collapse, and LOD where UIDs survived. |

If you edit just `intent` text on a node currently in `lean` LOD, you won't see any visible change — the node's label is `name`, and `name` didn't change. Toggle the node to `full` to see the new text.

A "reload-in-flight" flag prevents overlapping reloads; if a second save lands during processing, it's coalesced into one extra reload after the first completes.

Reload **does not** survive VS Code restart or the "Developer: Reload Window" command. View state lives in the webview's runtime memory only.

---

## Settings
<!-- Lines 180-198 -->

Exactly one setting is exposed:

| Key | Default | Effect |
| --- | --- | --- |
| `intentgraph.igToolPath` | `""` | Absolute path to the `ig-tool` binary. Empty falls back to PATH lookup. |

Set it via `Cmd+,` → search "intentgraph" → fill in the path. Used only for the activation ping; not in the hot path.

There is one contributed command:

| Command ID | Title | Trigger |
| --- | --- | --- |
| `intentgraph.fit` | (none — fired by status bar click) | Click the status bar item. |

No keybindings are registered by the extension. Bind manually if you want one.

---

## Limits and known limitations
<!-- Lines 201-210 -->

- **Scoped inline editing only.** Double-click a `full`-LOD node to edit its `name`, `intent`, `epistemic_state`, and existing constraint strings in place (writes back to disk, comments preserved). Not yet editable: adding/removing nodes, constraints, or links; reparenting; multi-line fields (`design_notes`, `history`, …); clearing a field to empty. There is no in-app undo — use git or VS Code "Revert File".
- **No persistent view state.** Closing and reopening the editor (or reloading VS Code) starts you over with the default depth-2 layout, all nodes lean, no collapse. Persistence is planned for a future revision.
- **Single-view per IG.** No named views or saved lenses. Multi-view is planned for a future revision.
- **Canvas labels are plain.** Multi-line, single font, single color, no HTML. The `full` LOD content is `\n`-joined plain text. Text rendering quality is planned for a future revision.
- **Multi-edge UID collisions** in `loadGraph.ts` use a counter suffix; in unusual graphs with many parallel intentlinks the suffix scheme may produce non-deterministic IDs across reloads.
- **Status bar text** does not refresh when switching focus between two open IG editors; it reflects the most-recently-loaded one.
- **`cytoscape-expand-collapse` is unmaintained** upstream and pinned at `4.1.1`. If a bug surfaces there, we cannot rely on a fix.

For each, see [4_EXTENSION_POINTS.md](4_EXTENSION_POINTS.md) for the path forward.
