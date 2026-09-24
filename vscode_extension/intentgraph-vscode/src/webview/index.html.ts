// Build the HTML document served to the webview.
// Content Security Policy for the webview.
// retainContextWhenHidden=true is the locked decision (memory cost
// documented in README; revisit once Cytoscape is mounted).

import * as vscode from 'vscode';
import { randomBytes } from 'crypto';

function makeNonce(): string {
  return randomBytes(16).toString('base64');
}

export function renderHtml(webview: vscode.Webview, extensionUri: vscode.Uri): string {
  const nonce = makeNonce();

  const scriptUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'dist', 'webview', 'main.js')
  );
  const styleUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'dist', 'webview', 'styles.css')
  );

  const cspSource = webview.cspSource;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="
    default-src 'none';
    img-src ${cspSource} https: data:;
    font-src ${cspSource};
    style-src ${cspSource} 'unsafe-inline';
    script-src 'nonce-${nonce}';
  ">
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="stylesheet" href="${styleUri}" />
  <title>IntentGraph</title>
</head>
<body>
  <div id="app">Loading IntentGraph...</div>
  <div id="cy"></div>
  <div id="ig-overlay-root"></div>
  <div id="cy-navigator"></div>
  <div id="banner" hidden></div>
  <div id="spinner" hidden><div class="ig-spinner"></div></div>
  <div id="status">(initialising)</div>
  <div id="lens-selector" class="lens-selector lens-selector--empty" aria-label="Lens selector">
    <button id="lens-selector-btn" type="button" class="lens-selector__btn" disabled>
      <span id="lens-selector-label" class="lens-selector__label">No lens</span>
      <span class="lens-selector__arrow" aria-hidden="true">&#9660;</span>
    </button>
    <ul id="lens-selector-list" class="lens-selector__list" hidden role="listbox" aria-label="Available lenses"></ul>
    <!-- Lens CRUD controls (PIG LENS_UI.CTRLPANEL.{2,3,4}). -->
    <button id="lens-create-btn" type="button" class="lens-selector__action" title="New lens" aria-label="New lens">+</button>
    <button id="lens-rename-btn" type="button" class="lens-selector__action" title="Rename active lens" aria-label="Rename active lens" disabled>&#9998;</button>
    <button id="lens-delete-btn" type="button" class="lens-selector__action" title="Delete active lens" aria-label="Delete active lens" disabled>&#128465;</button>
    <button id="lens-relayout-btn" type="button" class="lens-selector__action" title="Re-run layout" aria-label="Re-run layout">&#10227;</button>
    <!-- Bug 3 fix: inline input row replaces window.prompt (unsupported in webviews). -->
    <div id="lens-input-row" class="lens-selector__input-row" hidden>
      <input id="lens-input" class="lens-selector__input" type="text" maxlength="64" spellcheck="false" autocomplete="off" />
      <button id="lens-input-confirm" type="button" class="lens-selector__action" title="Confirm" aria-label="Confirm">&#10003;</button>
      <button id="lens-input-cancel" type="button" class="lens-selector__action" title="Cancel" aria-label="Cancel">&#10005;</button>
    </div>
    <div id="lens-msg" class="lens-selector__msg" hidden role="status" aria-live="polite"></div>
  </div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
}
