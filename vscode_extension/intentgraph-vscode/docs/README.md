# IntentGraph VS Code Extension — Documentation

Layered, rough-to-fine documentation for the IntentGraph viewer extension (with scoped inline editing). Start at the level that matches your need; each doc links to the next deeper one.

---

## Reading order

| If you want to... | Read |
| --- | --- |
| Install / deploy the extension (`bootstrap.sh` symlink) | [1_USAGE.md §Install](1_USAGE.md#install--first-launch) |
| Open an `.ig.yaml` file and use the viewer | [1_USAGE.md](1_USAGE.md) |
| Understand how the system is put together | [2_ARCHITECTURE.md](2_ARCHITECTURE.md) |
| Diagnose why something isn't working | [3_DEBUGGING.md](3_DEBUGGING.md) |
| Add a new feature or modify behavior | [4_EXTENSION_POINTS.md](4_EXTENSION_POINTS.md) |

The four numbered docs cover the **current MVP** (scaffold, renderer, LOD/polish, and bidirectional editing).

---

## Layered overview

The viewer is a single VS Code custom editor that renders an IntentGraph file in a webview. Three layers, each owning one thing:

1. **Extension host** (Node.js process) — file I/O, watcher, status bar, RPC handlers, command registration.
2. **Webview** (sandboxed iframe) — Cytoscape.js rendering, ELK layout, expand/collapse cues, in-node LOD toggle, minimap.
3. **Wire protocol** (vscode-messenger) — typed RPC and notifications between the two.

The graph file on disk is the source of truth. The host parses it. The webview is a pure renderer fed by serialized POJOs.

See [2_ARCHITECTURE.md §Data flow](2_ARCHITECTURE.md#data-flow) for the full pipeline.

---

## What the extension does (and doesn't) do

**Does:**
- Opens `*.ig.json`, `*.ig.yaml`, `*.intentgraph.{json,yaml}`, `*.lens.{json,yaml}` in a custom editor.
- Lays out the graph top-down with `elkjs` (layered, INCLUDE_CHILDREN, orthogonal routing).
- Renders nodes + intentlinks in Cytoscape; treearcs become compound nesting.
- Click-to-expand-collapse via the `+`/`−` cues at the top-left of every compound.
- Click a node body → toggle that node between `lean` LOD (name only) and `full` LOD (name + intent + epistemic_state + first 3 constraints inline).
- Double-click a `full` node → edit its `name`, `intent`, `epistemic_state`, and constraint strings inline; commits write back to the file with comments preserved.
- Reload on file change, preserving viewport, collapse-set, and LOD-set.
- Status bar item showing `<n> nodes · <m> links`; click to fit the graph.

**Does not:**
- Structurally edit the graph (add/remove nodes, links, or constraints; reparent). Inline editing is scoped to existing scalar fields — see [1_USAGE.md](1_USAGE.md#limits-and-known-limitations).
- Persist view state across VS Code restarts (no `WebviewPanelSerializer` yet).
- Render rich text (Cytoscape's canvas labels are single-font, single-style).
- Manage multiple lenses or named views per IG.

A design doc proposes how to lift each of those in a future revision.

---

## Pinned stack

| Package | Version | Reason |
| --- | --- | --- |
| `cytoscape` | `^3.31.0` | Core renderer (canvas; WebGL not used — would drop dashed edges) |
| `cytoscape-expand-collapse` | `4.1.1` (exact) | Collapse cues; **unmaintained upstream** — pin exactly |
| `cytoscape-navigator` | `2.0.2` | Minimap |
| `elkjs` | `^0.11.0` | Layout (bundled, no worker) |
| `vscode-messenger` (+ `-webview`) | `^0.6.0` | Typed RPC across host/webview |
| `yaml` (eemeli) | `^2.8.0` | YAML parser (NOT `js-yaml`) |
| `esbuild` | latest | Two-target bundler |

No `tippy.js`, no `cytoscape-popper` (removed when LOD replaced tooltips). No `@vscode/webview-ui-toolkit` (deprecated upstream).

**Why these exact pins:** `cytoscape-expand-collapse` and `cytoscape-navigator` are both effectively unmaintained
upstream, so their versions are pinned exactly rather than with a caret range — an unreviewed transitive bump could
silently change collapse/minimap behavior. `yaml` (eemeli) was chosen over `js-yaml` for comment- and AST-preserving
round-trips, needed by inline editing. `elkjs` and `vscode-messenger` use caret ranges since both are actively
maintained and their public APIs used here are stable across minor versions.

---

## How this documentation is organized

Each numbered doc opens with a one-paragraph summary, then deepens. Line-number TOCs at the top of each file. Cross-refs use relative markdown links. No version numbers or dates in the body — git tracks history.

If you change behavior, update the relevant doc + run `md-structure-sync` from the project root.
