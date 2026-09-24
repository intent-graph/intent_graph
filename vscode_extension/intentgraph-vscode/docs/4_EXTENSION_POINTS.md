# 4 — Extension Points

Where to plug in new behavior without rearchitecting. Every entry below names the file, the existing pattern, and the gotchas to expect.

## Table of Contents

1. [Adding a new message type](#adding-a-new-message-type) _(Lines 24-26)_
   1. [Case A — webview asks host for something (request / response)](#case-a--webview-asks-host-for-something-request--response) _(Lines 29-52)_
   1. [Case B — host pushes to webview (notification)](#case-b--host-pushes-to-webview-notification) _(Lines 55-77)_
1. [Adding a status bar action or command](#adding-a-status-bar-action-or-command) _(Lines 80-100)_
1. [Adding a Cytoscape style rule](#adding-a-cytoscape-style-rule) _(Lines 103-125)_
1. [Adding a node data field](#adding-a-node-data-field) _(Lines 128-155)_
1. [Adding a webview UI element](#adding-a-webview-ui-element) _(Lines 158-168)_
1. [Adding a setting](#adding-a-setting) _(Lines 171-200)_
1. [Adding a file pattern](#adding-a-file-pattern) _(Lines 203-214)_
1. [Things that look easy but aren't](#things-that-look-easy-but-arent) _(Lines 217-227)_



---

## Adding a new message type
<!-- Lines 24-26 -->

Three concrete cases below. The pattern is the same for any new RPC.

### Case A — webview asks host for something (request / response)
<!-- Lines 29-52 -->

1. **Define the type** in `src/messaging/messageTypes.ts`:
   ```ts
   export interface MyRequest { uid: string; }
   export interface MyResponse { ok: boolean; payload?: SomeShape; error?: string; }
   export const MyRequestType: RequestType<MyRequest, MyResponse> = {
     method: 'intentgraph/my-request'
   };
   ```
2. **Register a handler on the host** in `IntentGraphEditorProvider.resolveCustomEditor`:
   ```ts
   messenger.onRequest(MyRequestType, async (req) => {
     // ... compute response ...
     return { ok: true, payload: ... };
   }, { sender: participant });
   ```
3. **Expose a typed call on the webview** in `src/webview/messaging.ts`:
   ```ts
   myRequest(req: MyRequest): Promise<MyResponse> {
     return this.messenger.sendRequest(MyRequestType, HOST_EXTENSION, req);
   }
   ```
4. **Call it** from `main.ts`. Errors throw — handle with try/catch.

### Case B — host pushes to webview (notification)
<!-- Lines 55-77 -->

1. Define a `NotificationType<P>` in `messageTypes.ts`.
2. **Add the method to `broadcastMethods`** when registering the panel:
   ```ts
   const participant = messenger.registerWebviewPanel(panel, {
     broadcastMethods: [
       GraphChangedNotification.method,
       FitNotification.method,
       MyNotification.method  // ← add here
     ]
   });
   ```
   Forgetting this step makes the notification silently drop — this cost hours to track down once.
3. Send via `messenger.sendNotification(MyNotification, BROADCAST, params?)`. The `BROADCAST` import comes from `vscode-messenger-common`.
4. Register a handler in `webview/messaging.ts`:
   ```ts
   onMy(cb: (params: P) => void): void {
     this.messenger.onNotification(MyNotification, (params) => cb(params));
   }
   ```

---

## Adding a status bar action or command
<!-- Lines 80-100 -->

The current extension contributes one command (`intentgraph.fit`). Pattern for another:

1. **Declare in `package.json`** under `contributes.commands`:
   ```json
   { "command": "intentgraph.myAction", "title": "IntentGraph: My Action" }
   ```
2. **Register in `extension.ts activate()`**:
   ```ts
   ctx.subscriptions.push(
     vscode.commands.registerCommand('intentgraph.myAction', () => {
       // ... do something ...
     })
   );
   ```
3. **Wire to the status bar** if it should be a click target — see `extension.ts` for the existing item pattern. The status bar item's `command` property is just the command id string.

For commands that need to talk to the active webview, route through the panel registry the editor provider exposes (`getActiveEntry()` returns the entry for the currently-focused IG editor; null if none). Send a notification through `entry.messenger.sendNotification(...)`.

---

## Adding a Cytoscape style rule
<!-- Lines 103-125 -->

Edit `src/webview/styles/cyStyle.ts`. The export is `cyStyles: cytoscape.StylesheetStyle[]`. Append a new entry:

```ts
{
  selector: 'node[?someBoolean]',  // matches when data.someBoolean is truthy
  style: {
    'background-color': '#abcdef',
    'border-width': 3
  }
}
```

Selectors are evaluated in order; later rules override earlier ones for matching elements. For LOD-driven differences, use the existing `node[lod = "lean"]` and `node[lod = "full"]` selectors (note the spaces around `=` — required by Cytoscape's parser).

**Do not** use `var(--vscode-*)` color values. Cytoscape composites onto a canvas and ignores the browser CSS cascade — these silently become invalid styles. Use literal hex.

To data-bind a property: `'width': 'data(myWidth)'`. The data field must contain a number. To data-bind a label: `'label': 'data(myLabel)'`. Multi-line labels need `'text-wrap': 'wrap'` plus `'text-max-width'`.

After changing styles, recompile and reload. Webview hot-reload is not yet wired.

---

## Adding a node data field
<!-- Lines 128-155 -->

To make a new piece of data available for selectors and labels:

1. **Decide where it comes from.** If it's already in the IG schema, add it to the `RawNode` interface in `loadGraph.ts` and propagate to `IntentNode` in `shared/graphTypes.ts`. If it's derived (e.g. like the existing `epistemicRisk`), compute it in `loadGraph.ts` or in `cyMount.ts buildElements`.
2. **Write it to the node's `data`** in `cyMount.ts buildElements`:
   ```ts
   const data: Record<string, unknown> = {
     id: uid,
     name: node.name,
     epistemicRisk: ...,
     myField: ...        // ← add
   };
   ```
3. **Reference it from a selector** (`'node[myField = "x"]'`) or a label/style binding (`'data(myField)'`).
4. **Refresh on metadata reload.** Find the metadata-only branch in `main.ts loadAndRender` and update the data inline:
   ```ts
   for (const [uid, src] of next.nodes) {
     const node = cy.getElementById(uid);
     if (!node.nonempty()) continue;
     if (node.data('myField') !== src.myField) {
       node.data('myField', src.myField);
     }
   }
   ```
   Otherwise the data stays stale until the next structural reload.

---

## Adding a webview UI element
<!-- Lines 158-168 -->

The webview HTML is generated by `src/webview/index.html.ts renderHtml(webview, extensionUri)`. Add a `<div>` (or other element) inside the body. Style it via `src/webview/styles.css` — DOM CSS works fine for elements outside the Cytoscape canvas.

If the element needs to react to graph state, drive it from `App` in `main.ts`. Use a method on `App` (not a global function) so it can read `this.state` and `this.handle.cy`.

Pin position with absolute / fixed positioning relative to `#cy`. The cy container fills the webview viewport; overlays live above it via z-index.

CSP: inline `<style>` tags need a nonce; inline scripts are forbidden. The current pattern serves CSS via a `<link>` and JS via a single `<script nonce="...">` for the bundle. Adding more scripts means more nonces — easier to add to the bundle entry.

---

## Adding a setting
<!-- Lines 171-200 -->

Three places to touch:

1. **`package.json`** under `contributes.configuration.properties`:
   ```json
   "intentgraph.mySetting": {
     "type": "boolean",
     "default": false,
     "description": "What this controls."
   }
   ```
2. **Read it** wherever you need it:
   ```ts
   const value = vscode.workspace.getConfiguration('intentgraph').get<boolean>('mySetting', false);
   ```
3. **React to changes** if the setting is hot-swappable:
   ```ts
   ctx.subscriptions.push(
     vscode.workspace.onDidChangeConfiguration((e) => {
       if (e.affectsConfiguration('intentgraph.mySetting')) {
         // ... re-read and apply ...
       }
     })
   );
   ```

For settings the webview needs to know about, push them via a notification on change.

---

## Adding a file pattern
<!-- Lines 203-214 -->

Edit `package.json` `contributes.customEditors[0].selector` and append:
```json
{ "filenamePattern": "*.my-pattern.yaml" }
```

`priority: "default"` means VS Code auto-uses the IG viewer for that pattern. `"option"` means it shows up in `Open With…` but won't be the default. The current selectors are all `default`.

Be careful with broad patterns (`*.json`, `*.yaml`) — they hijack unrelated files. Stick to specific suffixes that signal "this is an IntentGraph."

---

## Things that look easy but aren't
<!-- Lines 217-227 -->

A non-exhaustive list of changes that look one-line but have hidden costs.

- **Switching from canvas labels to HTML overlays.** Cytoscape doesn't render HTML. The community extension `cytoscape-node-html-label` works but is unmaintained, and you'd have to position overlay divs on every pan/zoom (`cy.on('pan zoom', updatePositions)`) — performance scales poorly past a few hundred visible nodes.
- **Adding a `WebviewPanelSerializer`.** Looks small (one register call) but the serializer must reconstruct an `IntentGraphModel`-ready URI and re-acquire the document, plus deserialize the persisted state into the right class shapes. Every Wave assumed an editor reload starts fresh.
- **Letting the user edit text in the viewer.** Implies bidirectional sync, conflict resolution with external edits, YAML preservation (comments, anchors, key ordering), and validation before save. See §Bidirectional edits for a proposed path.
- **Animating layout changes.** ELK gives final positions only. Cytoscape's `position()` is instantaneous. Animation requires an interpolated path between old and new positions, which is fine if you maintain a "previous positions" map but expensive to wire post-hoc.
- **Multiple panels showing the same file.** The current panel registry handles multiple files but assumes one panel per document. Two panels on the same file will both reload on change — likely fine, but the status bar text only reflects the most recently focused.
- **Updating LOD content without remount.** The metadata path already does this: it edits `node.data('fullLabel', ...)` in place. If you want a CSS-only animation on toggle, you'd need to listen for `data` changes on the node and animate via Cytoscape's animation API, which doesn't tween between style states by default.
- **Using `ig-tool` for queries during normal use.** The host parses YAML directly because `ig-tool query --structure` omits treearcs. Switching back to `ig-tool` would require either a `--full` mode in `ig-tool` or post-processing the missing data on the webview side.
- **Keeping `cytoscape-expand-collapse` working long-term.** Upstream is unmaintained. Pinned at `4.1.1`. If a real bug surfaces, you'll need to either fork or migrate to a different complexity-management approach.
