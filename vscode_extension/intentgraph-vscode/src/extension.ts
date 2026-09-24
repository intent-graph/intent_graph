// Extension host entry point. Activation registers the read-only custom
// editor, creates the status-bar item, and registers commands.
// `intentgraph.fit` — recentre the cytoscape view.
// `intentgraph.openLens` (reimplemented — QuickPick over
//   internal lenses in IG file), `intentgraph.clearLens` — reset viewer to default LOD.
//   Removed: `intentgraph.saveLensAs`, `intentgraph.clearLastLens` (v1 lens machinery).

import * as vscode from 'vscode';

import { IntentGraphEditorProvider } from './editor/IntentGraphEditorProvider';
import { IgToolClient } from './igtool/igToolClient';

export function activate(context: vscode.ExtensionContext): void {
  const igToolClient = new IgToolClient();

  // PIG DIAGNOSTICS.LOGGING constraint #4: create the output channel once at activation.
  const outputChannel = vscode.window.createOutputChannel('IntentGraph');
  context.subscriptions.push(outputChannel);

  // Status-bar item — text set by the editor provider on each successful load.
  // Priority 100: rendered toward the leftmost end of the right cluster.
  const statusItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusItem.hide();
  context.subscriptions.push(statusItem);

  const provider = new IntentGraphEditorProvider(
    context.extensionUri,
    igToolClient,
    statusItem,
    context,
    outputChannel
  );

  context.subscriptions.push(
    vscode.window.registerCustomEditorProvider(
      IntentGraphEditorProvider.viewType,
      provider,
      {
        // retainContextWhenHidden: locked decision (keeps webview state when hidden).
        webviewOptions: { retainContextWhenHidden: true },
        supportsMultipleEditorsPerDocument: false
      }
    )
  );

  // `intentgraph.fit` — re-centre the cytoscape view in the active webview.
  context.subscriptions.push(
    vscode.commands.registerCommand('intentgraph.fit', () => {
      provider.fitActive();
    })
  );

  // `intentgraph.openLens` — QuickPick over internal lenses in the loaded IG.
  context.subscriptions.push(
    vscode.commands.registerCommand('intentgraph.openLens', () => {
      void provider.openLens();
    })
  );

  // `intentgraph.clearLens` — reset viewer to default LOD (no overlays, all expanded).
  context.subscriptions.push(
    vscode.commands.registerCommand('intentgraph.clearLens', () => {
      provider.clearLens();
    })
  );

  // `intentgraph.trace.toggle` — flip intentgraph.trace.enabled for the workspace.
  // PIG OBSERVABILITY constraint #6.
  context.subscriptions.push(
    vscode.commands.registerCommand('intentgraph.trace.toggle', () => {
      const config = vscode.workspace.getConfiguration('intentgraph');
      const current = config.get<boolean>('trace.enabled', true);
      const next = !current;
      void config.update('trace.enabled', next, vscode.ConfigurationTarget.Workspace).then(() => {
        void vscode.window.showInformationMessage(
          `IntentGraph trace ${next ? 'enabled' : 'disabled'} for this workspace.`
        );
      });
    })
  );

  // `intentgraph.trace.mark` — prompt for a label and write a mark entry to the active panel's trace.
  // PIG OBSERVABILITY — manual marker via command palette.
  context.subscriptions.push(
    vscode.commands.registerCommand('intentgraph.trace.mark', () => {
      void vscode.window.showInputBox({
        prompt: 'Mark label',
        placeHolder: 'e.g. before-repro, after-fix …'
      }).then((label) => {
        if (label === undefined) return; // cancelled
        const entry = provider.getActiveEntry();
        if (!entry) {
          void vscode.window.showWarningMessage('IntentGraph: no active panel to mark.');
          return;
        }
        void (entry as { trace: { mark(label: string): Promise<void> } }).trace.mark(label);
      });
    })
  );
}

export function deactivate(): void {
  // no-op
}
