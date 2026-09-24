# IntentGraph for VS Code

Viewer + scoped inline editor for IntentGraph files (`*.ig.json`, `*.ig.yaml`,
`*.intentgraph.*`, `*.lens.*`) backed by Cytoscape.js + elkjs +
cytoscape-expand-collapse. Click a compound's `+`/`-` cue to expand or
collapse; click a node's body to toggle its content between a compact
`lean` view and a `full` view (intent + epistemic state + constraints);
double-click a full node to edit its `name`, `intent`, `epistemic_state`, and
constraint lines in place (writes back to disk, comments preserved).

## Install
<!-- Lines 13-35 -->

**Use it in every editor window** (recommended): run the idempotent installer, which
builds `dist/` and **symlinks** this folder into each detected editor (VS Code, Cursor,
Insiders, VSCodium, Windsurf):

```sh
./bootstrap.sh --yes
# then: Cmd+Shift+P → Developer: Reload Window
```

After that, clicking any `*.ig.json` / `*.ig.yaml` opens the viewer automatically — no
F5. Because the install is a symlink to this source, **deploying a change is just
re-running `./bootstrap.sh --yes` (it rebuilds only if sources changed) and reloading the
window**. Remove with `./bootstrap.sh --uninstall`.

**Moved or renamed the repo?** The editor symlink and the `ig-tool` install both hold
absolute paths, so both go stale. Re-run `./bootstrap.sh --yes` from the new location;
it repairs both. Details: [docs/3_DEBUGGING.md](docs/3_DEBUGGING.md#extension-or-ig-tool-stopped-working-after-moving-the-repo).

**Develop it** (Extension Development Host): `npm install && npm run compile`, then F5 in
VS Code — runs from `dist/` in an isolated second window. See
[docs/1_USAGE.md](docs/1_USAGE.md#install--first-launch) for both paths in detail.

## Feature history
<!-- Lines 38-48 -->

- Scaffold, custom-editor registration, `ig-tool` ping smoke-test.
- Real graph rendering: `yaml.parse` → ELK layout → Cytoscape mount,
  expand/collapse cues at compound top-left, navigator minimap, file-watcher
  reload preserving viewport.
- In-node LOD rendering (replaces tooltip popovers),
  full snapshot/restore on file reload (viewport + collapse-set + LOD-set),
  status-bar item, this README, smoke-test fixture.
- Lenses, bidirectional inline edits, persisted positions,
  tracing.

## Smoke test
<!-- Lines 51-62 -->

A canonical sample lives at `test/fixtures/validator.ig.json` (21 nodes,
19 intentlinks, depth 2). Open it after `npm run compile` + F5; expect a
sub-second cold render with all five L1 children visible and the navigator
minimap bottom-right.

```sh
ig-tool validate -g test/fixtures/validator.ig.json
```

should return `status: ok` with 0 errors and 0 warnings.

## Status bar
<!-- Lines 65-70 -->

When an IntentGraph editor is the active tab, the bottom-right of the
VS Code chrome shows `IntentGraph: <n> nodes · <m> links`. Clicking the
item recentres the cytoscape view (`cy.fit`). The same action is available
via the command palette as `IntentGraph: Recentre View`.

## Known limitations
<!-- Lines 73-89 -->

- `cytoscape-expand-collapse` is unmaintained upstream. Pinned to `4.1.1`.
  Bug reports there will not be addressed; if the extension breaks under a
  Cytoscape major bump, downgrade Cytoscape rather than the plugin.
- LOD toggle does NOT relayout. Multiple `full` nodes coexist and may
  overlap neighbours. Toggle back to `lean` to recover. This is intentional
  — relayout-on-LOD introduces UX-jarring jumps at every click.
- File watcher uses a directory-anchored fallback when the file is outside
  any workspace folder. May be flaky on some OSes
  (`microsoft/vscode#164925`).
- Web extensions (`vscode.dev`) are not supported (file-watching limitation;
  `ig-tool` is a Python CLI, not available in the browser context).
- `retainContextWhenHidden: true` keeps the cytoscape canvas in memory when
  the editor tab is hidden — convenient but costs ~tens of MB at 1-2k nodes.
- Restart survival via `WebviewPanelSerializer` is NOT implemented yet
  (`TODO`); reopening a fresh window re-renders from scratch.

## Architecture pointers
<!-- Lines 92-95 -->

- [docs/README.md](docs/README.md) — layered doc index; start here.
- [docs/2_ARCHITECTURE.md](docs/2_ARCHITECTURE.md) — data flow, ELK plumbing, message protocol, LOD rendering.
- [docs/3_DEBUGGING.md](docs/3_DEBUGGING.md) — symptoms → causes, including a stale install after a repo move.
