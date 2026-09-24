// Read-only custom editor provider for IntentGraph files.
// Serves graph data; broadcasts file-change notifications so the
// webview can reload while preserving viewport.
// Drops the lazy FetchNode RPC; node content is sent in full via
// LoadGraphResponse. Maintains a status-bar item with per-graph metrics
// (nodes · links) and a registry for the `intentgraph.fit` command.
// Watcher anchored to the document URI (avoids duplicate events; Fix 1+2).
// Internal lens model: reads lenses from IG file,
// applies default lens after boot, provides openLens/clearLens commands.
// Bidirectional field edits via EditFieldRequestType; selfWritePath
// suppression flag prevents double-reload after own writes.

import * as vscode from 'vscode';
import * as path from 'path';

import { Messenger } from 'vscode-messenger';
import { BROADCAST, type WebviewIdMessageParticipant } from 'vscode-messenger-common';

import { IgToolClient } from '../igtool/igToolClient';
import { loadGraph } from '../graph/loadGraph';
import {
  ApplyLensNotification,
  BootCompleteNotification,
  CreateLensRequestType,
  DeleteLensRequestType,
  EditConflictNotification,
  EditFieldRequestType,
  EditNodeRequestType,
  FitNotification,
  GraphChangedNotification,
  LoadGraphRequestType,
  PersistLensLodRequestType,
  PersistLensVisibilityRequestType,
  PersistPositionRequestType,
  PingRequestType,
  RenameLensRequestType,
  SelectLensRequestType,
  TraceEntryNotification,
  TraceStateNotification,
  type CreateLensPayload,
  type DeleteLensPayload,
  type LensMutationResponse,
  type PersistLensLodRequest,
  type PersistLensLodResponse,
  type PersistLensVisibilityRequest,
  type PersistLensVisibilityResponse,
  type PersistPositionRequest,
  type PersistPositionResponse,
  type RenameLensPayload,
  type SelectLensPayload,
  type TraceEntry
} from '../messaging/messageTypes';
import { TraceSink } from '../host/trace';
import { registerTraceSink } from '../host/diskWrite';
import { readFile } from 'node:fs/promises';
import { computeFileHash } from '../host/fileHash';
import { createEditConflictDetector, type EditConflictDetector } from '../host/editConflictDetector';
import { applyFieldEdit, applyNodeEdit } from '../host/yamlEdit';
import { renderHtml } from '../webview/index.html';
import { lensConfigToPayload } from '../host/lensApply';
import { createLensStorage, type LensStorage } from '../host/lensStorage';
import type { SerialisedIntentGraphModel, SerialisedLensConfig, Uid, Position } from '../shared/graphTypes';

interface IntentGraphDocument extends vscode.CustomDocument {
  // Host stays stateless per request; parsed model lives in the webview.
}

const FILE_WATCHER_DEBOUNCE_MS = 300;

/** Tracks the currently-active webview panel so external commands can address it. */
interface PanelEntry {
  panel: vscode.WebviewPanel;
  messenger: Messenger;
  participant: WebviewIdMessageParticipant;
  documentUri: vscode.Uri;
  /** Lenses loaded from the last successful LoadGraphResponse. */
  loadedLenses: Record<string, SerialisedLensConfig>;
  /** Default lens name from meta.default_lens (null if absent/unresolved). */
  defaultLensName: string | null;
  /** Last loaded model (for resolving available node/link UIDs). */
  lastLoadedModel: SerialisedIntentGraphModel | null;
  /** Active lens name (in-memory only; not persisted to workspaceState).
   *  Used to re-apply after structural reload if the lens still exists. */
  activeLensName: string | null;
  /** Self-write suppression: fsPath of the file this panel just wrote via EditFieldRequest.
   *  Cleared on the next watcher firing for that path so only one reload is suppressed.
   *  Prevents double-apply after out-of-band writeFile. */
  selfWritePath: string | null;
  /** Debounce timer for autosave (position persistence). */
  autosaveTimer: NodeJS.Timeout | undefined;
  /** Queued autosave request (replaced on each drag within debounce window). */
  queuedAutosave: {
    uid: Uid;
    position: Position;
    lensName: string | null;
  } | null;
  /** Host-side trace sink for this panel session. */
  trace: TraceSink;
  /** Monotonic sequence for host-side trace entries. */
  hostSeq: number;
  /**
   * File-hash conflict detector. Tracks the SHA-256 of the file
   * at the last successful LoadGraph. Used by `scheduleReload` to suppress
   * watcher fires when content hasn't actually changed (macOS FSEvents /
   * VS Code watcher can fire on metadata-only events; without this gate, every
   * fire triggers a full re-render which itself may write the file → loop).
   */
  conflictDetector: EditConflictDetector;
  /** Lens persistence facade (read-doc + mutate + write cycle, framework-agnostic). */
  lensStorage: LensStorage;
  /**
   * Correlation id set by `scheduleReload` when it triggers
   * a reload via GraphChangedNotification, then read by the LoadGraph handler
   * to link `kind:'applyLensReinstate'` back to the originating reload. Lets
   * a trace reader grep one corr and see the full watcher-fire → reload →
   * load → applyLens chain.
   */
  pendingReloadCorr: string | null;
}

export class IntentGraphEditorProvider implements vscode.CustomReadonlyEditorProvider<IntentGraphDocument> {
  public static readonly viewType = 'intentgraph.graphViewer';

  /** Active panel registry — entry exists per resolved editor. */
  private readonly panels = new Set<PanelEntry>();

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly igToolClient: IgToolClient,
    private readonly statusItem: vscode.StatusBarItem,
    private readonly context: vscode.ExtensionContext,
    private readonly outputChannel: vscode.OutputChannel
  ) {}

  /** Log an edit failure to the IntentGraph output channel (PIG DIAGNOSTICS.LOGGING). */
  private logEditFailure(nodeUid: string, field: string, error: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] edit ok=false | uid=${nodeUid} field=${field} error=${error}`);
  }

  /** Resolve the active entry (panel currently focused), or null. */
  getActiveEntry(): PanelEntry | null {
    for (const entry of this.panels) {
      if (entry.panel.active) return entry;
    }
    return null;
  }

  /** Send `intentgraph.fit` to the active webview, if any. */
  fitActive(): void {
    const entry = this.getActiveEntry();
    if (!entry) return;
    try {
      entry.messenger.sendNotification(FitNotification, entry.participant);
    } catch {
      /* ignore */
    }
  }

  // ---------- Command implementations ----------

  /** intentgraph.openLens — QuickPick over internal lenses in the loaded IG. */
  async openLens(): Promise<void> {
    const entry = this.getActiveEntry();
    if (!entry) {
      void vscode.window.showWarningMessage('IntentGraph: no active editor.');
      return;
    }

    const lenses = entry.loadedLenses;
    const lensKeys = Object.keys(lenses);

    if (lensKeys.length === 0) {
      void vscode.window.showInformationMessage(
        'IntentGraph: No lenses defined in this IG file. Use ig-tool lens create to add one.'
      );
      return;
    }

    const items = lensKeys.map((name) => {
      const cfg = lenses[name];
      const nodeCount = Object.keys(cfg.nodes).length;
      const detail = [
        cfg.description ? cfg.description : '',
        `${nodeCount} node${nodeCount !== 1 ? 's' : ''}`
      ].filter(Boolean).join(' · ');
      return { label: name, detail };
    });

    const picked = await vscode.window.showQuickPick(items, {
      placeHolder: 'Select a lens to apply'
    });
    if (!picked) return;

    const pickedConfig = lenses[picked.label];
    if (!pickedConfig) return;

    const availableNodes = this.collectAvailableNodes(entry);
    const availableLinks = this.collectAvailableLinks(entry);
    const payload = lensConfigToPayload(pickedConfig, availableNodes, availableLinks);

    this.sendApplyLens(entry, payload);
    entry.activeLensName = picked.label;
  }

  /** intentgraph.clearLens — reset viewer to default LOD state. */
  clearLens(): void {
    const entry = this.getActiveEntry();
    if (!entry) {
      void vscode.window.showWarningMessage('IntentGraph: no active editor.');
      return;
    }
    this.sendApplyLens(entry, null);
    entry.activeLensName = null;
    void vscode.window.showInformationMessage('IntentGraph: Lens cleared.');
  }

  // ---------- Private helpers ----------

  /** Collect the set of node UIDs available in the last loaded model. */
  private collectAvailableNodes(entry: PanelEntry): Set<Uid> {
    if (!entry.lastLoadedModel) return new Set();
    return new Set(Object.keys(entry.lastLoadedModel.nodes));
  }

  /** Collect the set of intentlink UIDs available in the last loaded model. */
  private collectAvailableLinks(entry: PanelEntry): Set<string> {
    if (!entry.lastLoadedModel) return new Set();
    return new Set(entry.lastLoadedModel.links.map((l) => l.uid));
  }

  private sendApplyLens(entry: PanelEntry, payload: import('../messaging/messageTypes').LensApplyPayload | null): void {
    // INSTRUMENTATION: log what the host is sending. If payload.positions is
    // empty here but the lens YAML on disk had positions, the bug is in the
    // host translator (lensApply.ts::lensConfigToPayload).
    try {
      void entry.trace.write({
        ts: new Date().toISOString(),
        seq: entry.hostSeq++,
        src: 'host',
        kind: 'sendApplyLens',
        data: payload === null
          ? { lensName: null, nodeCount: 0, positionCount: 0 }
          : {
              lensName: payload.name,
              nodeCount: Object.keys(payload.nodes).length,
              positionCount: Object.keys(payload.positions ?? {}).length,
              positionSample: Object.entries(payload.positions ?? {}).slice(0, 3).map(([uid, p]) => ({ uid, x: p.x, y: p.y }))
            }
      });
    } catch {
      /* trace failures must not break apply */
    }
    try {
      entry.messenger.sendNotification(ApplyLensNotification, entry.participant, payload);
    } catch {
      /* ignore — panel may have been disposed */
    }
  }

  // Autosave handler for position persistence.
  // Constraint: PERSISTENCE.AUTOSAVE + PERSISTENCE.AUTOCREATE precedence (DRAG §6).
  private async autosavePersistPosition(
    entry: PanelEntry,
    document: IntentGraphDocument,
    uid: Uid,
    position: Position,
    lensName: string | null
  ): Promise<void> {
    const fsPath = document.uri.fsPath;

    // PIG PERSISTENCE.AUTOSAVE constraint #4: selfWritePath must be set BEFORE any
    // await on writeFile, otherwise the file-watcher fires before the flag is in place
    // and triggers a spurious reload loop.
    entry.selfWritePath = fsPath;

    try {
      let targetLensName = lensName;

      // If no active lens, auto-create 'default' lens first (PERSISTENCE.AUTOCREATE).
      if (!targetLensName) {
        const created = await entry.lensStorage.ensureDefaultLens();
        if (!created.ok) {
          entry.selfWritePath = null;
          void vscode.window.showErrorMessage(`IntentGraph autosave failed: ${created.error}`);
          return;
        }
        targetLensName = 'default';
      }

      // Persist position to the target lens.
      const result = await entry.lensStorage.persistPosition(targetLensName, uid, position);
      if (!result.ok) {
        entry.selfWritePath = null;
        void vscode.window.showErrorMessage(`IntentGraph autosave failed: ${result.error}`);
        return;
      }

      // Post-trace fix: macOS FSEvents fires the watcher TWICE
      // per write. selfWritePath is cleared after the first fire, so the second
      // fire falls through to the content-hash gate. Update the conflict
      // detector immediately so the second-fire gate matches and
      // suppresses with cause:'contentUnchanged'.
      if (result.newFileHash) {
        entry.conflictDetector.updateFileHash(result.newFileHash);
      }

      // Success: show transient status.
      void vscode.window.setStatusBarMessage(
        `Layout saved to lens ${targetLensName}`,
        3000
      );
    } catch (err) {
      entry.selfWritePath = null;
      const msg = err instanceof Error ? err.message : String(err);
      void vscode.window.showErrorMessage(`IntentGraph autosave error: ${msg}`);
    }
  }

  // ---------- Provider interface ----------

  async openCustomDocument(
    uri: vscode.Uri,
    _openContext: vscode.CustomDocumentOpenContext,
    _token: vscode.CancellationToken
  ): Promise<IntentGraphDocument> {
    return {
      uri,
      dispose: () => {
        /* no-op */
      }
    };
  }

  async resolveCustomEditor(
    document: IntentGraphDocument,
    panel: vscode.WebviewPanel,
    _token: vscode.CancellationToken
  ): Promise<void> {
    const distRoot = vscode.Uri.joinPath(this.extensionUri, 'dist');
    const webviewRoot = vscode.Uri.joinPath(this.extensionUri, 'dist', 'webview');

    panel.webview.options = {
      enableScripts: true,
      localResourceRoots: [distRoot, webviewRoot]
    };

    panel.webview.html = renderHtml(panel.webview, this.extensionUri);

    const disposables: vscode.Disposable[] = [];

    const messenger = new Messenger();
    // broadcastMethods: list all host→webview notification methods to avoid silent drops.
    // RestoreLensNotification removed; ApplyLensNotification added.
    // EditConflictNotification added.
    const participant = messenger.registerWebviewPanel(panel, {
      broadcastMethods: [
        GraphChangedNotification.method,
        FitNotification.method,
        ApplyLensNotification.method,
        EditConflictNotification.method,
        TraceStateNotification.method
      ]
    });

    // Construct the TraceSink for this panel session.
    const traceEnabled = vscode.workspace
      .getConfiguration('intentgraph')
      .get<boolean>('trace.enabled', true);
    const tracePath = vscode.workspace
      .getConfiguration('intentgraph')
      .get<string>('trace.path', '');
    const traceSink = new TraceSink({
      workspaceFolder: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
      extensionDir: this.extensionUri.fsPath,
      configuredPath: tracePath || undefined,
      enabled: traceEnabled,
      outputChannel: this.outputChannel,
      vscodeVersion: vscode.version
    });

    // Register the host-side trace writer so writeIgFile can
    // emit `kind:'fileWrite'` entries for every disk write. Without this, all
    // file writes are invisible in the trace and reload-loop investigations
    // are flying blind.
    registerTraceSink((entry) => { void traceSink.write(entry); });

    const entry: PanelEntry = {
      panel,
      messenger,
      participant,
      documentUri: document.uri,
      loadedLenses: {},
      defaultLensName: null,
      lastLoadedModel: null,
      activeLensName: null,
      selfWritePath: null,
      autosaveTimer: undefined,
      queuedAutosave: null,
      trace: traceSink,
      hostSeq: 0,
      conflictDetector: createEditConflictDetector(),
      lensStorage: createLensStorage(document.uri.fsPath),
      pendingReloadCorr: null
    };
    this.panels.add(entry);

    // Push trace-enabled state to the webview so it knows to emit.
    // Registered after panel is created; broadcastMethods needs to include this.
    messenger.sendNotification(TraceStateNotification, participant, { enabled: traceEnabled });

    messenger.onRequest(PingRequestType, async () => {
      return this.igToolClient.ping();
    }, { sender: participant });

    // Forward webview trace entries to the host sink.
    messenger.onNotification(TraceEntryNotification, (payload: TraceEntry) => {
      void entry.trace.write(payload);
    }, { sender: participant });

    const updateStatus = (model: { nodes: Record<string, unknown>; links: unknown[] }): void => {
      const n = Object.keys(model.nodes).length;
      const m = model.links.length;
      this.statusItem.text = `IntentGraph: ${n} nodes · ${m} links`;
      this.statusItem.tooltip = 'Click to recentre';
      this.statusItem.command = 'intentgraph.fit';
      this.statusItem.show();
    };

    messenger.onRequest(LoadGraphRequestType, async () => {
      try {
        const { model, fileHash, lenses, default_lens } = await loadGraph(document.uri);

        // Cache for command use and re-apply-on-reload.
        entry.lastLoadedModel = model;
        entry.loadedLenses = lenses;
        entry.defaultLensName = default_lens;
        // Cache the file hash so the watcher can gate on
        // "content actually changed" before triggering a reload.
        if (fileHash) entry.conflictDetector.recordFileHash(fileHash);

        if (panel.active) updateStatus(model);

        // If a lens was active before a structural reload,
        // re-apply it if it still exists in the new lenses dict.
        // (Default lens is delivered separately via BootCompleteNotification.)
        // This path handles reloads AFTER first mount.
        if (entry.activeLensName && entry.activeLensName in lenses) {
          const cfg = lenses[entry.activeLensName];
          const availableNodes = new Set(Object.keys(model.nodes));
          const availableLinks = new Set(model.links.map((l) => l.uid));
          const payload = lensConfigToPayload(cfg, availableNodes, availableLinks);
          this.sendApplyLens(entry, payload);
          // Emit applyLensReinstate trace entry. The corr field
          // is set by `scheduleReload` when the reload originates from a
          // watcher; it links the watcher fire → load → applyLens chain so a
          // reader can grep one corr and see the full ripple.
          void entry.trace.write({
            ts: new Date().toISOString(),
            seq: entry.hostSeq++,
            src: 'host',
            kind: 'applyLensReinstate',
            corr: entry.pendingReloadCorr ?? undefined,
            data: { lensName: entry.activeLensName }
          });
        } else if (entry.activeLensName && !(entry.activeLensName in lenses)) {
          // Active lens was removed externally: fall back to default LOD, show diagnostic.
          entry.activeLensName = null;
          // No toast — the webview diagnostics banner (if any) surfaces this.
        }

        return { ok: true as const, model, fileHash, lenses, default_lens };
      } catch (err) {
        return { ok: false as const, error: (err as Error).message };
      }
    }, { sender: participant });

    // Handle BootCompleteNotification.
    // The webview sends this exactly once, after ELK layout + mount + tap handlers +
    // overlay layer are all fully wired and the UI phase has flipped to ready.
    // On receipt, deliver the default lens if meta.default_lens is set.
    // This is silent — no toast message.
    messenger.onNotification(BootCompleteNotification, () => {
      const defaultName = entry.defaultLensName;
      if (!defaultName || !(defaultName in entry.loadedLenses)) return;
      const cfg = entry.loadedLenses[defaultName];
      const availableNodes = this.collectAvailableNodes(entry);
      const availableLinks = this.collectAvailableLinks(entry);
      const payload = lensConfigToPayload(cfg, availableNodes, availableLinks);
      this.sendApplyLens(entry, payload);
      entry.activeLensName = defaultName;
    }, { sender: participant });

    // Handle EditFieldRequest (webview → host).
    // The webview proposes a field edit; host validates, writes, returns new hash.
    // Bug 2: log ALL ok=false responses and fire conflict banner on all failures.
    messenger.onRequest(EditFieldRequestType, async (req) => {
      const validateOnWrite = vscode.workspace
        .getConfiguration('intentgraph')
        .get<boolean>('validateOnWrite', false);
      const igToolPath = vscode.workspace
        .getConfiguration('intentgraph')
        .get<string>('igToolPath', '');

      // Set self-write flag BEFORE the async write so the watcher sees it.
      entry.selfWritePath = document.uri.fsPath;

      const result = await applyFieldEdit(document.uri.fsPath, req, {
        validateOnWrite,
        igToolPath: igToolPath || undefined
      });

      if (!result.ok) {
        // Clear our premature self-write flag since no write occurred.
        entry.selfWritePath = null;

        // PIG EDITING.PERSISTENCE constraint #5 + DIAGNOSTICS.LOGGING constraint #1:
        // Log every ok=false response with nodeUid, field, and error text.
        this.logEditFailure(req.nodeUid, req.field, result.error || '(no error message)');

        // PIG DIAGNOSTICS.EDIT_CONFLICT constraint #1: Fire conflict banner on ALL ok=false,
        // not just hash mismatch. The webview will display a non-dismissable banner.
        try {
          messenger.sendNotification(
            EditConflictNotification,
            entry.participant,
            { message: result.error || 'Edit failed — reload to retry' }
          );
        } catch {
          /* ignore */
        }
      } else if (result.newFileHash) {
        // Cache the post-write hash so the second watcher fire
        // (macOS double-fire pattern) hits the content-hash gate and is
        // suppressed cleanly.
        entry.conflictDetector.updateFileHash(result.newFileHash);
      }

      return { ok: result.ok, error: result.error, newFileHash: result.newFileHash };
    }, { sender: participant });

    // Handle EditNodeRequest (whole-node multi-field edit).
    // Bug 2: log ALL ok=false responses and fire conflict banner on all failures.
    messenger.onRequest(EditNodeRequestType, async (req) => {
      const validateOnWrite = vscode.workspace
        .getConfiguration('intentgraph')
        .get<boolean>('validateOnWrite', false);
      const igToolPath = vscode.workspace
        .getConfiguration('intentgraph')
        .get<string>('igToolPath', '');

      entry.selfWritePath = document.uri.fsPath;

      const result = await applyNodeEdit(document.uri.fsPath, req, {
        validateOnWrite,
        igToolPath: igToolPath || undefined
      });

      if (!result.ok) {
        entry.selfWritePath = null;

        // PIG EDITING.PERSISTENCE constraint #5 + DIAGNOSTICS.LOGGING constraint #1:
        // Log every ok=false response. For whole-node edit, log all changed fields.
        const fields = Object.keys(req.fields || {}).join(', ');
        this.logEditFailure(req.nodeUid, fields || '(all fields)', result.error || '(no error message)');

        // PIG DIAGNOSTICS.EDIT_CONFLICT constraint #1: Fire conflict banner on ALL ok=false.
        try {
          messenger.sendNotification(
            EditConflictNotification,
            entry.participant,
            { message: result.error || 'Edit failed — reload to retry' }
          );
        } catch {
          /* ignore */
        }
      } else if (result.newFileHash) {
        // Cache the post-write hash so the second watcher fire
        // (macOS double-fire pattern) hits the content-hash gate and is
        // suppressed cleanly.
        entry.conflictDetector.updateFileHash(result.newFileHash);
      }

      return { ok: result.ok, error: result.error, newFileHash: result.newFileHash };
    }, { sender: participant });

    // Handle PersistPositionRequest (drag-release position persistence).
    // PIG INTERACTION.DRAG → PERSISTENCE.AUTOSAVE + PERSISTENCE.AUTOCREATE.
    messenger.onRequest(PersistPositionRequestType, async (req: PersistPositionRequest): Promise<PersistPositionResponse | any> => {
      // Queue the autosave request. If another arrives within the debounce window,
      // it replaces the queued request (single-flight constraint).
      entry.queuedAutosave = {
        uid: req.uid,
        position: req.position,
        lensName: req.activeLensName
      };

      // Clear any pending timer and reschedule the debounce.
      if (entry.autosaveTimer) clearTimeout(entry.autosaveTimer);

      const AUTOSAVE_DEBOUNCE_MS = 500;
      entry.autosaveTimer = setTimeout(async () => {
        const queued = entry.queuedAutosave;
        if (!queued) return;
        entry.queuedAutosave = null;
        entry.autosaveTimer = undefined;

        await this.autosavePersistPosition(entry, document, queued.uid, queued.position, queued.lensName);
      }, AUTOSAVE_DEBOUNCE_MS);

      // Return immediate success; actual persistence is async.
      return { ok: true as const, lensName: req.activeLensName ?? 'default', autoCreated: false };
    }, { sender: participant });

    // Bug 1 fix — handle PersistLensVisibilityRequest (cue collapse/expand).
    // PIG LENSSCHEMA.VISIBILITY: lens membership encodes visibility; cue gestures
    // must update the on-disk lens so close/reopen restores the same visible tree.
    messenger.onRequest(PersistLensVisibilityRequestType, async (req: PersistLensVisibilityRequest): Promise<PersistLensVisibilityResponse> => {
      const fsPath = document.uri.fsPath;

      // Reject if no active lens (mirrors PERSISTENCE.AUTOCREATE precedence:
      // visibility persistence requires an active lens to write into).
      const lensName = entry.activeLensName;
      if (!lensName) {
        return { ok: false, error: 'No active lens — cannot persist visibility.' };
      }

      // Reject if no model has been loaded yet (we need childrenOf for the walk).
      if (!entry.lastLoadedModel) {
        return { ok: false, error: 'No model loaded yet.' };
      }

      // selfWritePath set BEFORE any await on the file system, mirroring
      // autosavePersistPosition (PERSISTENCE.AUTOSAVE constraint #4).
      entry.selfWritePath = fsPath;

      try {
        // Build childrenOf Map from the cached SerialisedIntentGraphModel.
        // The model was loaded via `loadGraph(...)` and stored on `entry.lastLoadedModel`.
        const childrenOfRaw = entry.lastLoadedModel.childrenOf;
        const childrenOf = new Map<Uid, Uid[]>(Object.entries(childrenOfRaw));

        const result = await entry.lensStorage.persistVisibility(
          lensName,
          req.op,
          req.uid,
          childrenOf,
          req.childPositions
        );

        if (!result.ok) {
          entry.selfWritePath = null;
          return { ok: false, error: result.error };
        }

        // No-op path: helper accepted the request but nothing on disk changed
        // (e.g. collapse of a compound whose children were already absent).
        // Emit a host trace marker so the chain stays visible to a reader.
        if (result.noop) {
          entry.selfWritePath = null;
          void entry.trace.write({
            ts: new Date().toISOString(),
            seq: entry.hostSeq++,
            src: 'host',
            kind: 'lensVisibilityNoop',
            data: { uri: fsPath, lensName, op: req.op, uid: req.uid }
          });
          return { ok: true };
        }

        // Hash sync: post-write update so the second watcher fire
        // hits cause:'contentUnchanged' and doesn't trigger a structural reload
        // (which would clobber the user's open compound state with applyLens).
        if (result.newFileHash) {
          entry.conflictDetector.updateFileHash(result.newFileHash);
        }

        return { ok: true, newFileHash: result.newFileHash };
      } catch (err) {
        entry.selfWritePath = null;
        return { ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }, { sender: participant });

    // LOD persistence — handle PersistLensLodRequest (leaf lean ↔ full).
    // Mirrors the visibility handler but only mutates the `lod` field. PIG
    // LENSSCHEMA.VISIBILITY constraint #5: compound LOD has no effect on
    // visibility, so this path is gated to leaves on the webview side.
    messenger.onRequest(PersistLensLodRequestType, async (req: PersistLensLodRequest): Promise<PersistLensLodResponse> => {
      const fsPath = document.uri.fsPath;
      const lensName = entry.activeLensName;
      if (!lensName) {
        return { ok: false, error: 'No active lens — cannot persist lod.' };
      }
      entry.selfWritePath = fsPath;
      try {
        const result = await entry.lensStorage.persistLod(lensName, req.uid, req.lod);
        if (!result.ok) {
          entry.selfWritePath = null;
          return { ok: false, error: result.error };
        }
        if (result.noop) {
          entry.selfWritePath = null;
          void entry.trace.write({
            ts: new Date().toISOString(),
            seq: entry.hostSeq++,
            src: 'host',
            kind: 'lensLodNoop',
            data: { uri: fsPath, lensName, uid: req.uid, lod: req.lod }
          });
          return { ok: true };
        }
        if (result.newFileHash) {
          entry.conflictDetector.updateFileHash(result.newFileHash);
        }
        return { ok: true, newFileHash: result.newFileHash };
      } catch (err) {
        entry.selfWritePath = null;
        return { ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }, { sender: participant });

    // Lens CRUD + select handlers.
    // PIG LENS_UI.CTRLPANEL.{1,2,3,4}.

    // SelectLens: client-side pick is now host-mediated so entry.activeLensName
    // stays in sync and survives reload. No file write — apply via the existing
    // ApplyLensNotification path.
    messenger.onRequest(SelectLensRequestType, async (req: SelectLensPayload): Promise<LensMutationResponse> => {
      try {
        if (req.name === null) {
          this.sendApplyLens(entry, null);
          entry.activeLensName = null;
          return { ok: true, activeLensName: null };
        }
        const cfg = entry.loadedLenses[req.name];
        if (!cfg) {
          return { ok: false, error: `Lens '${req.name}' not found.` };
        }
        const availableNodes = this.collectAvailableNodes(entry);
        const availableLinks = this.collectAvailableLinks(entry);
        const payload = lensConfigToPayload(cfg, availableNodes, availableLinks);
        this.sendApplyLens(entry, payload);
        entry.activeLensName = req.name;
        return { ok: true, activeLensName: req.name };
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }, { sender: participant });

    // CreateLens / RenameLens / DeleteLens: each reads the current file, parses
    // the YAML doc, runs the host-side mutation, and writes. The file-watcher
    // reload IS desired here (the lens dict topology changed), so selfWritePath
    // is NOT set — this is the deliberate difference from autosavePersistPosition.
    messenger.onRequest(CreateLensRequestType, async (req: CreateLensPayload): Promise<LensMutationResponse> => {
      try {
        if (!entry.lastLoadedModel) {
          return { ok: false, error: 'No model loaded yet — cannot seed new lens.' };
        }
        // PIG LENSSCHEMA.VISIBILITY: new lens defaults to {ROOT, ROOT.children}.
        const rootUid = entry.lastLoadedModel.rootUid;
        const childrenOfRoot = entry.lastLoadedModel.childrenOf[rootUid] ?? [];
        const result = await entry.lensStorage.createLens(req.name, { rootUid, childrenOfRoot });
        if (!result.ok) return { ok: false, error: result.error };
        // Auto-activate the new lens (the user's expected behavior).
        entry.activeLensName = req.name;
        return { ok: true, newFileHash: result.newFileHash, activeLensName: req.name };
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }, { sender: participant });

    messenger.onRequest(RenameLensRequestType, async (req: RenameLensPayload): Promise<LensMutationResponse> => {
      try {
        const result = await entry.lensStorage.renameLens(req.oldName, req.newName);
        if (!result.ok) return { ok: false, error: result.error };
        // If the active lens was renamed, follow the rename.
        if (entry.activeLensName === req.oldName) {
          entry.activeLensName = req.newName;
        }
        return { ok: true, newFileHash: result.newFileHash, activeLensName: entry.activeLensName };
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }, { sender: participant });

    messenger.onRequest(DeleteLensRequestType, async (req: DeleteLensPayload): Promise<LensMutationResponse> => {
      try {
        const result = await entry.lensStorage.deleteLens(req.name);
        if (!result.ok) return { ok: false, error: result.error };
        // If the deleted lens was active, clear active state and apply null.
        if (entry.activeLensName === req.name) {
          entry.activeLensName = null;
          this.sendApplyLens(entry, null);
        }
        return { ok: true, newFileHash: result.newFileHash, activeLensName: entry.activeLensName };
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }, { sender: participant });

    // BROADCAST kept available for future fan-outs.
    void BROADCAST;

    // ---- File watcher (anchored to the document URI to avoid duplicate events).
    const watchPattern = new vscode.RelativePattern(
      path.dirname(document.uri.fsPath),
      path.basename(document.uri.fsPath)
    );

    const watcher = vscode.workspace.createFileSystemWatcher(watchPattern);

    let timer: NodeJS.Timeout | undefined;
    /**
     * scheduleReload performs THREE checks before triggering
     * a reload, in this order:
     *   1. selfWritePath suppression (existing — set by autosave/lensCrud paths).
     *   2. Content-hash gate: read the file, compute SHA-256, compare against
     *      `entry.conflictDetector`'s last-loaded hash. If they match, the
     *      watcher fired but content is unchanged — emit
     *      `kind:'reloadSuppressed'` and return.
     *      This is the fix for the macOS FSEvents / metadata-only watcher loop
     *      that surfaced in the Step 8c idle trace.
     *   3. If both fall through, schedule the debounced reload and emit
     *      `kind:'reload'` with a fresh corr that the LoadGraph handler will
     *      reference in `kind:'applyLensReinstate'`.
     */
    const scheduleReload = async (_sourceTag: string, uri: vscode.Uri): Promise<void> => {
      if (uri.fsPath !== document.uri.fsPath) return;

      // Check 1: selfWritePath suppression.
      const isSelfWrite = entry.selfWritePath === uri.fsPath;
      if (isSelfWrite) {
        entry.selfWritePath = null;
        void entry.trace.write({
          ts: new Date().toISOString(),
          seq: entry.hostSeq++,
          src: 'host',
          kind: 'reloadSuppressed',
          data: { reason: _sourceTag, uri: uri.fsPath, cause: 'selfWritePathMatch' }
        });
        return;
      }

      // Check 2 (NEW): content-hash gate.
      // Read the file and compare its hash to the last loaded one. If equal,
      // the watcher fired on a non-content event (metadata, FSEvents noise,
      // or our own write that didn't bump selfWritePath in time).
      try {
        const raw = await readFile(uri.fsPath, 'utf8');
        const currentHash = computeFileHash(raw);
        const expected = entry.conflictDetector.getLastFileHash();
        if (expected !== null && currentHash === expected) {
          void entry.trace.write({
            ts: new Date().toISOString(),
            seq: entry.hostSeq++,
            src: 'host',
            kind: 'reloadSuppressed',
            data: {
              reason: _sourceTag,
              uri: uri.fsPath,
              cause: 'contentUnchanged',
              hashPrefix: currentHash.slice(0, 12)
            }
          });
          return;
        }
        // Hash differs (or no prior hash) — log with both for diagnosis.
        if (timer) clearTimeout(timer);
        const reloadCorr = `c-${entry.hostSeq}-r${Math.random().toString(36).slice(2, 8)}`;
        entry.pendingReloadCorr = reloadCorr;
        void entry.trace.write({
          ts: new Date().toISOString(),
          seq: entry.hostSeq++,
          src: 'host',
          kind: 'reload',
          corr: reloadCorr,
          data: {
            reason: _sourceTag,
            uri: uri.fsPath,
            selfWritePathMatch: false,
            reloadTriggered: true,
            currentHashPrefix: currentHash.slice(0, 12),
            expectedHashPrefix: expected ? expected.slice(0, 12) : null
          }
        });
        timer = setTimeout(() => {
          messenger.sendNotification(GraphChangedNotification, BROADCAST);
        }, FILE_WATCHER_DEBOUNCE_MS);
      } catch (err) {
        // Read failure: fall back to the legacy unconditional reload, but log it.
        if (timer) clearTimeout(timer);
        const reloadCorr = `c-${entry.hostSeq}-r${Math.random().toString(36).slice(2, 8)}`;
        entry.pendingReloadCorr = reloadCorr;
        void entry.trace.write({
          ts: new Date().toISOString(),
          seq: entry.hostSeq++,
          src: 'host',
          kind: 'reload',
          corr: reloadCorr,
          data: {
            reason: _sourceTag,
            uri: uri.fsPath,
            selfWritePathMatch: false,
            reloadTriggered: true,
            hashGateError: err instanceof Error ? err.message : String(err)
          }
        });
        timer = setTimeout(() => {
          messenger.sendNotification(GraphChangedNotification, BROADCAST);
        }, FILE_WATCHER_DEBOUNCE_MS);
      }
    };
    const onChange = (uri: vscode.Uri): void => { void scheduleReload('watcher', uri); };

    disposables.push(watcher.onDidChange(onChange));
    disposables.push(watcher.onDidCreate(onChange));
    disposables.push(watcher.onDidDelete(onChange));
    disposables.push(watcher);

    disposables.push(
      vscode.workspace.onDidSaveTextDocument((doc) => { void scheduleReload('save', doc.uri); })
    );

    disposables.push({
      dispose: () => {
        if (timer) clearTimeout(timer);
      }
    });

    disposables.push(
      panel.onDidChangeViewState(() => {
        if (panel.active) {
          this.statusItem.show();
        } else {
          if (!this.getActiveEntry()) this.statusItem.hide();
        }
      })
    );

    panel.onDidDispose(() => {
      this.panels.delete(entry);
      if (!this.getActiveEntry()) this.statusItem.hide();
      // Flush and close the trace sink.
      void entry.trace.close();
      for (const d of disposables) {
        try {
          d.dispose();
        } catch {
          /* ignore */
        }
      }
    });
  }
}
