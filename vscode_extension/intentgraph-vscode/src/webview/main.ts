// Webview entry point (IIFE bundled by esbuild for browser target).
// Responsibilities:
//   1. acquireVsCodeApi() exactly once via messaging.getVsCodeApi().
//   2. Load graph from host, run ELK layout, mount Cytoscape via cyMount.
//   3. Wire tap-to-LOD-toggle — no popovers; LOD lives inside the node.
//   4. Subscribe to GraphChanged notifications and reload (diff-and-apply),
//      preserving viewport + collapse-set + LOD-set across structural reload.
//   5. Drive a uiPhase state machine (loading/ready/error/empty/stale).
//   6. Log per-phase timings (buildElkMs/layoutMs/mountMs/total).
//   7. Honour FitNotification from the host status-bar click.
//   8. Handle ApplyLensNotification: apply named lens (LOD + collapse) or clear.
//   9. Show diagnostics banner for stale UIDs in applied lens.
//  10. BootCompleteNotification retained: signals structural mount to host for
//      default-lens delivery.
//  11. Cache fileHash from LoadGraphResponse; update on successful EditNodeResponse.
//  12. Pass onNodeEditCommit callback to HtmlOverlayLayer for whole-node edit mode.
//  13. Handle EditConflictNotification: show conflict banner with Reload button.
//  14. Document-level click-outside handler: exit edit mode and commit on outside-click.
//  15. In-viewer lens selector (Issue 3): always-visible floating dropdown.

import type cytoscape from 'cytoscape';

import {
  rehydrateModel,
  type IntentGraphModel,
  type IntentNode,
  type NodeLOD,
  type Position,
  type Uid
} from '../shared/graphTypes';
import { buildElkJson, runLayout, flattenAbsolutePositions } from './elkBridge';
import { mount, isRiskState, type CyHandle, type ExpandCollapseApi } from './cyMount';
import { buildOverlayContent, type NodeEditCommitCallback } from './overlay/htmlOverlayLayer';
import { GestureRouter } from './interaction/gestureRouter';
import { createGestureStateFrom, type GestureState } from './interaction/state';
import { CueLayer } from './overlay/cueLayer';
import { getVsCodeApi, WebviewMessaging } from './messaging';
import { WebviewState, type UiPhase } from './state';
import type { LensApplyPayload, EditNodeFields } from '../messaging/messageTypes';
import type { SerialisedLensConfig } from '../shared/graphTypes';
import { deriveLensVisibility } from '../shared/lensVisibility';
import { initTrace, trace } from './trace';
import { ecExpandRecursively, ecCollapseRecursively } from './overlay/ecWrap';
import { createBannerManager, type BannerManager } from './ui/bannerManager';
import { LensSelector } from './lens/lensSelector';
import { lensConfigToPayloadClient } from './lens/lensApply';

// ---------- DOM helpers ----------

function $(id: string): HTMLElement | null {
  return document.getElementById(id);
}

function setStatus(text: string): void {
  const el = $('status');
  if (el) el.textContent = text;
}

function setApp(text: string): void {
  const el = $('app');
  if (el) el.textContent = text;
}

function showSpinner(visible: boolean): void {
  const el = $('spinner');
  if (el) el.hidden = !visible;
}



function showTransientStatus(text: string, durationMs: number): void {
  setStatus(text);
  setTimeout(() => {
    setStatus('');
  }, durationMs);
}

function setEmptyPlaceholder(empty: boolean): void {
  const el = $('cy');
  if (!el) return;
  if (empty) el.classList.add('ig-empty');
  else el.classList.remove('ig-empty');
}

// ---------- App ----------

interface PhaseTimings {
  buildElkMs: number;
  layoutMs: number;
  mountMs: number;
  total: number;
}

/**
 * Return UIDs of currently-collapsed compound nodes. cytoscape-expand-collapse
 * strips children from a node when it collapses, so the node is no longer a
 * `:parent` match — it's only tagged with the collapsed class.
 */
function collectCollapsedUids(cy: cytoscape.Core): Uid[] {
  const out: Uid[] = [];
  cy.nodes('.cy-expand-collapse-collapsed-node').forEach((n) => {
    out.push(n.id());
  });
  return out;
}

class App {
  private readonly state = new WebviewState();
  private readonly messaging: WebviewMessaging;
  private readonly banner: BannerManager;
  private handle: CyHandle | null = null;
  /** Guard: BootCompleteNotification is fired exactly once per editor lifetime. */
  private bootSignalled = false;
  /** In-viewer lens selector widget. */
  private readonly lensSelector: LensSelector;
  /** Cached lenses from last LoadGraphResponse. Used by in-viewer selector. */
  private cachedLenses: Record<string, SerialisedLensConfig> = {};
  /** Name of currently-active lens (client-side tracking). */
  private activeLensName: string | null = null;
  /**
   * Gesture state shared with the router. Maps reference the SAME instances on
   * `this.state` (WebviewState) so reload snapshot/restore continues to work.
   * Introduces `editingUid` and `grabPosition`.
   */
  private readonly gestureState: GestureState;
  /**
   * Single owner of all five user gestures (PIG INTERACTION.ROUTER). Recreated
   * on every structural mount because Cytoscape listeners reset; the underlying
   * GestureState persists.
   */
  private gestureRouter: GestureRouter | null = null;
  /**
   * Cue layer for compound nodes (PIG LAYOUT.CUES). Recreated
   * on every structural mount; renders one DOM button per compound regardless
   * of LOD.
   */
  private cueLayer: CueLayer | null = null;

  constructor() {
    this.messaging = new WebviewMessaging(getVsCodeApi());
    this.banner = createBannerManager();
    // Initialise the trace emitter BEFORE LensSelector is
    // constructed, so the `lensSelectorMounted` entry the constructor emits
    // is captured. Was previously called in run() — too late.
    initTrace(this.messaging, /*initialEnabled*/ true);
    this.lensSelector = new LensSelector();
    this.gestureState = createGestureStateFrom({
      nodeLOD: this.state.nodeLOD,
      collapseSet: this.state.collapseSet
    });
    // Pick goes through the host (SelectLensRequest) so
    // entry.activeLensName stays in sync and survives reload. The host replies
    // by sending ApplyLensNotification which the webview's existing handler
    // applies — no client-side applyLensByName fork.
    this.lensSelector.setPickHandler((name) => {
      void this.messaging.sendSelectLens({ name }).then((res) => {
        if (!res.ok) {
          showTransientStatus(`Lens select failed: ${res.error ?? 'unknown'}`, 4000);
        } else {
          this.activeLensName = res.activeLensName ?? null;
          this.lensSelector.setActiveLens(this.activeLensName);
        }
      });
    });

    // CRUD button handlers.
    this.lensSelector.setCrudHandlers({
      onCreate: () => void this.handleCreateLens(),
      onRename: () => void this.handleRenameLens(),
      onDelete: () => void this.handleDeleteLens()
    });

    // Re-layout: re-run ELK on current model, apply positions, persist each
    // moved leaf to the active lens. Suppressed while any node is in edit mode.
    this.lensSelector.setRelayoutHandler(() => void this.handleRelayout());
  }

  // ---------- Lens CRUD orchestration ----------

  private handleCreateLens(): void {
    const fileHash = this.state.currentFileHash;
    if (!fileHash) {
      showTransientStatus('Cannot create lens: file not loaded', 3000);
      return;
    }
    this.lensSelector.openInputRequest({
      action: 'create',
      mode: 'text',
      onSubmit: async (value) => {
        const res = await this.messaging.sendCreateLens({ name: value, fileHash });
        if (res.ok) {
          showTransientStatus(`Created lens '${value}'`, 2000);
          // File watcher → reload → cachedLenses + selector update.
          this.activeLensName = value;
        }
        return { ok: res.ok, error: res.error };
      }
    });
  }

  private handleRenameLens(): void {
    if (!this.activeLensName) return;
    const oldName = this.activeLensName;
    const fileHash = this.state.currentFileHash;
    if (!fileHash) {
      showTransientStatus('Cannot rename lens: file not loaded', 3000);
      return;
    }
    this.lensSelector.openInputRequest({
      action: 'rename',
      mode: 'text',
      prefill: oldName,
      onSubmit: async (value) => {
        if (value === oldName) {
          // No-op rename: treat as cancel.
          return { ok: true };
        }
        const res = await this.messaging.sendRenameLens({ oldName, newName: value, fileHash });
        if (res.ok) {
          showTransientStatus(`Renamed '${oldName}' → '${value}'`, 2000);
          this.activeLensName = value;
        }
        return { ok: res.ok, error: res.error };
      }
    });
  }

  private handleDeleteLens(): void {
    if (!this.activeLensName) return;
    const name = this.activeLensName;
    const fileHash = this.state.currentFileHash;
    if (!fileHash) {
      showTransientStatus('Cannot delete lens: file not loaded', 3000);
      return;
    }
    this.lensSelector.openInputRequest({
      action: 'delete',
      mode: 'confirm',
      message: `Delete lens '${name}'? This cannot be undone.`,
      onSubmit: async () => {
        const res = await this.messaging.sendDeleteLens({ name, fileHash });
        if (res.ok) {
          showTransientStatus(`Deleted lens '${name}'`, 2000);
          this.activeLensName = null;
        }
        return { ok: res.ok, error: res.error };
      }
    });
  }

  /**
   * Re-run ELK layout on the current model, apply the new positions to leaves,
   * persist each moved position to the active lens, and refit the viewport.
   *
   * Edit-mode suppression: if any node is in edit mode, no-op (matches the
   * drag-persist rule — see gestureRouter.wireDragGestures).
   *
   * Persistence: the host accepts PersistPositionRequest with a null
   * activeLensName and auto-creates a lens on first persist, so re-layout
   * works whether or not a lens is currently active.
   */
  private async handleRelayout(): Promise<void> {
    if (!this.handle || !this.state.model) return;
    if (this.gestureState.editingUid !== null) {
      showTransientStatus('Re-layout suppressed while editing', 2000);
      return;
    }

    const model = this.state.model;
    showTransientStatus('Re-running layout…', 1500);

    let positions: Map<Uid, Position>;
    try {
      const elkJson = buildElkJson(model);
      const positioned = await runLayout(elkJson);
      positions = flattenAbsolutePositions(positioned);
    } catch (err) {
      showTransientStatus(`Re-layout failed: ${String(err)}`, 4000);
      return;
    }

    const cy = this.handle.cy;
    const moved: Array<{ uid: Uid; position: Position }> = [];
    cy.batch(() => {
      for (const [uid, pos] of positions) {
        const ele = cy.getElementById(uid);
        if (!ele.nonempty()) continue;
        // Persist only leaf positions — cytoscape's compound auto-fit re-derives
        // parent positions from their children.
        if (ele.isParent()) continue;
        ele.position({ x: pos.x, y: pos.y });
        moved.push({ uid, position: { x: pos.x, y: pos.y } });
      }
    });

    // Refit the viewport so the new layout is centred.
    try {
      cy.fit(undefined, 40);
    } catch {
      /* ignore */
    }

    // Persist each leaf position to the active lens. The host serialises these
    // — autosave coalescing happens server-side.
    const activeLensName = this.activeLensName;
    for (const { uid, position } of moved) {
      void this.messaging.sendPersistPosition({ uid, position, activeLensName });
    }

    trace({
      src: 'lens',
      kind: 'relayout',
      data: { count: moved.length, activeLensName }
    });
  }

  /**
   * Bug 2 fix: after a successful EditNode write, mirror the edit into
   * state.model and cy node.data() so future re-renders show the new value.
   * Companion to the in-card DOM write in HtmlOverlayLayer (which only
   * patches the currently-open card).
   *
   * Invariant: only fields actually changed (non-undefined in the request)
   * are written — preserves the message contract that undefined = unchanged.
   */
  private applyLocalEditSync(
    nodeUid: Uid,
    fields: EditNodeFields
  ): void {
    if (!this.handle || !this.state.model) return;
    const stateNode = this.state.model.nodes.get(nodeUid);
    if (!stateNode) return;
    const cy = this.handle.cy;
    const node = cy.getElementById(nodeUid);
    if (!node.nonempty()) return;

    const before = {
      stateName: stateNode.name,
      cyName: node.data('name') as string | undefined,
      stateIntent: stateNode.intent,
      stateConstraintsLen: stateNode.constraints?.length ?? 0
    };

    let changed = false;
    if (fields.name !== undefined && stateNode.name !== fields.name) {
      stateNode.name = fields.name;
      node.data('name', fields.name);
      changed = true;
    }
    if (fields.intent !== undefined && stateNode.intent !== fields.intent) {
      stateNode.intent = fields.intent;
      changed = true;
    }
    if (fields.epistemic_state !== undefined && stateNode.epistemic_state !== fields.epistemic_state) {
      stateNode.epistemic_state = fields.epistemic_state;
      // Restyle coupling: epistemic_state drives the orange risk border via the
      // epistemicRisk node-data flag (see cyStyle.ts node[?epistemicRisk]). Recompute
      // it live so the border updates without waiting for a full reload.
      node.data('epistemicRisk', isRiskState(fields.epistemic_state) ? 1 : 0);
      changed = true;
    }
    if (fields.constraints !== undefined) {
      stateNode.constraints = fields.constraints;
      changed = true;
    }

    if (changed && this.state.nodeLOD.get(nodeUid) === 'full') {
      this.handle.overlayLayer.refreshContent(nodeUid, stateNode);
    }

    const after = {
      stateName: stateNode.name,
      cyName: node.data('name') as string | undefined,
      stateIntent: stateNode.intent,
      stateConstraintsLen: stateNode.constraints?.length ?? 0,
      // Re-fetch from state.model.nodes to confirm the mutation landed in the
      // canonical Map, not just on a local copy.
      reFetchedName: this.state.model.nodes.get(nodeUid)?.name
    };

    trace({
      src: 'app',
      kind: 'editLocalSync',
      data: {
        uid: nodeUid,
        nameChanged: fields.name !== undefined,
        intentChanged: fields.intent !== undefined,
        epistemicChanged: fields.epistemic_state !== undefined,
        constraintsChanged: fields.constraints !== undefined,
        applied: changed,
        before,
        after,
        // Show the values being applied so we can confirm they were what user typed.
        appliedFields: {
          name: fields.name,
          intent: fields.intent !== undefined ? `<len=${fields.intent.length}>` : undefined,
          epistemic_state: fields.epistemic_state,
          constraintsLen: fields.constraints?.length
        }
      }
    });
  }

  /**
   * Bug 1 fix: persist a cue-driven visibility change to the active lens.
   * Source of truth for the rule: PIG node `LENSSCHEMA.VISIBILITY`.
   *
   *  - Collapse: host removes all descendants of `uid` from the lens. Compound
   *    stays in lens with no children → renders collapsed on next applyLens.
   *  - Expand:   host adds direct children to the lens with current positions.
   *    Compound has children in lens → renders expanded on next applyLens.
   *
   * No-op if no active lens (compound visibility has no destination).
   */
  private async persistCueVisibility(uid: Uid, isNowCollapsed: boolean): Promise<void> {
    if (!this.state.currentFileHash) return;
    if (!this.activeLensName) {
      trace({
        src: 'app',
        kind: 'persistVisibilitySkipped',
        data: { uid, op: isNowCollapsed ? 'collapse' : 'expand', reason: 'noActiveLens' }
      });
      return;
    }
    if (!this.handle || !this.state.model) return;

    const op: 'collapse' | 'expand' = isNowCollapsed ? 'collapse' : 'expand';

    // For 'expand', gather direct children's current cytoscape positions so the
    // host can write them into the new lens entries. PIG LENSSCHEMA.NODESHAPE
    // (Path Y): positions are absolute, no conversion needed.
    let childPositions: Record<Uid, { x: number; y: number }> | undefined;
    if (op === 'expand') {
      const directChildren = this.state.model.childrenOf.get(uid) ?? [];
      childPositions = {};
      const cy = this.handle.cy;
      for (const childUid of directChildren) {
        const node = cy.getElementById(childUid);
        if (!node.nonempty()) continue;
        const p = node.position();
        childPositions[childUid] = { x: p.x, y: p.y };
      }
    }

    trace({
      src: 'app',
      kind: 'persistVisibility',
      data: { uid, op, lensName: this.activeLensName, childCount: childPositions ? Object.keys(childPositions).length : 0 }
    });

    try {
      const res = await this.messaging.sendPersistLensVisibility({
        uid,
        op,
        childPositions,
        fileHash: this.state.currentFileHash
      });
      if (res.ok && res.newFileHash) {
        this.state.currentFileHash = res.newFileHash;
      } else if (!res.ok) {
        trace({
          src: 'app',
          kind: 'persistVisibilityError',
          data: { uid, op, error: res.error ?? 'unknown' }
        });
      }
    } catch (err) {
      trace({
        src: 'app',
        kind: 'persistVisibilityError',
        data: { uid, op, error: err instanceof Error ? err.message : String(err) }
      });
    }
  }

  /**
   * Persist a leaf's LOD change (lean ↔ full) to the active lens, so the
   * detail-mode state survives close+reopen. PIG LENSSCHEMA.NODESHAPE: lod
   * is part of the LensNodeEntry shape. Compound LOD has no effect on
   * visibility (PIG LENSSCHEMA.VISIBILITY #5) so we don't persist it.
   */
  private async persistLeafLod(uid: Uid, lod: NodeLOD): Promise<void> {
    if (!this.state.currentFileHash) return;
    if (!this.activeLensName) {
      trace({
        src: 'app',
        kind: 'persistLodSkipped',
        data: { uid, lod, reason: 'noActiveLens' }
      });
      return;
    }
    if (!this.handle) return;

    // Gate to leaves: compound LOD is not visibility-meaningful.
    const ele = this.handle.cy.getElementById(uid);
    if (!ele.nonempty()) return;
    if (ele.isParent()) {
      trace({ src: 'app', kind: 'persistLodSkipped', data: { uid, lod, reason: 'compound' } });
      return;
    }

    trace({
      src: 'app',
      kind: 'persistLod',
      data: { uid, lod, lensName: this.activeLensName }
    });

    try {
      const res = await this.messaging.sendPersistLensLod({
        uid,
        lod,
        fileHash: this.state.currentFileHash
      });
      if (res.ok && res.newFileHash) {
        this.state.currentFileHash = res.newFileHash;
      } else if (!res.ok) {
        trace({
          src: 'app',
          kind: 'persistLodError',
          data: { uid, lod, error: res.error ?? 'unknown' }
        });
      }
    } catch (err) {
      trace({
        src: 'app',
        kind: 'persistLodError',
        data: { uid, lod, error: err instanceof Error ? err.message : String(err) }
      });
    }
  }

  async run(): Promise<void> {
    setApp('IntentGraph');
    this.setUiPhase('loading');

    // initTrace was moved to App constructor (above) so the
    // LensSelector mount trace is captured. The host will push the actual
    // enabled state via TraceStateNotification once messaging is fully wired.

    this.messaging.onGraphChanged(() => {
      void this.handleGraphChanged();
    });

    this.messaging.onFit(() => {
      if (this.handle) {
        try {
          this.handle.cy.fit(undefined, 40);
        } catch {
          /* ignore */
        }
      }
    });

    // Host pushes an internal lens to apply (or null to clear).
    this.messaging.onApplyLens((payload: LensApplyPayload | null) => {
      if (payload === null) {
        this.clearLens();
      } else {
        this.applyLens(payload);
      }
    });

    // Host notifies of edit failure (conflict or validation error).
    // Bug 2: banner is non-dismissable until user clicks Reload.
    // PIG DIAGNOSTICS.EDIT_CONFLICT constraints #1–2.
    this.messaging.onEditConflict((message) => {
      this.banner.showEditConflict(
        `Edit failed: ${message} Click Reload to try again.`,
        () => {
          this.setUiPhase('loading');
          void this.handleGraphChanged();
        }
      );
    });

    await this.loadAndRender(/*isReload*/ false);
  }

  // ---------- Lens application ----------

  /**
   * Apply a LensApplyPayload: translate nodes → nodeLOD, collapse skeleton compounds,
   * rebuild overlays, show diagnostics banner if stale UIDs present.
   * Must be called AFTER structural mount.
   */
  private applyLens(payload: LensApplyPayload): void {
    // Clear any existing diagnostics banner before applying.
    this.banner.hide();

    if (!this.handle) return;
    const { cy, ec, overlayLayer } = this.handle;
    const surviving = new Set(this.state.model?.nodes.keys() ?? []);
    const modelNodes = this.state.model?.nodes;

    // Step 1: Reset existing nodeLOD state (lean all nodes, hide all overlays).
    for (const [uid] of this.state.nodeLOD) {
      try {
        cy.getElementById(uid).data('lod', 'lean');
        overlayLayer.hide(uid);
      } catch {
        /* ignore */
      }
    }
    this.state.nodeLOD.clear();

    // Step 2: Expand all collapsed nodes before re-collapsing per lens.
    try {
      const collapsed = cy.nodes('.cy-expand-collapse-collapsed-node');
      if (collapsed.nonempty()) {
        let targets = cy.collection() as cytoscape.Collection;
        collapsed.forEach((n) => { targets = targets.union(n); });
        ecExpandRecursively(ec, targets, 'applyLens.expandAll', 'app');
      }
    } catch {
      /* ignore */
    }

    // Steps 4+5 (unified): consult the canonical visibility rule and collapse
    // every compound that should render collapsed.
    //
    // Source of truth: PIG node `LENSSCHEMA.VISIBILITY` (constraints #3 + #4).
    // Implementation: src/shared/lensVisibility.ts::deriveLensVisibility.
    //
    // Renderer pragmatic (PIG constraint: "Renderer pragmatic ..."): cytoscape
    // always mounts the full tree, so "absent" nodes cannot be truly hidden.
    // The closest analogue is collapse, so the SET of compounds we collapse is
    // the union of:
    //   (a) collapsedCompoundUids from deriveLensVisibility (in-lens compounds
    //       with no children in lens), AND
    //   (b) compounds that are absent from the lens entirely.
    // The pure rule stays clean; this union is renderer-side only.
    //
    // ORDER NOTE: collapse MUST happen BEFORE position restoration. Collapsing
    // removes descendants from the visible scene and triggers cytoscape's
    // auto-relayout, which would otherwise clobber any positions we'd already
    // applied. Collapsed-ancestor descendants are not visible, so their
    // position-restore is skipped (re-applied later when the user expands).
    const lensNodeUids = new Set(Object.keys(payload.nodes));
    let collapsedAncestorUids: Set<Uid> = new Set();
    if (this.state.model) {
      const visibility = deriveLensVisibility(lensNodeUids, this.state.model.childrenOf);
      let targets = cy.collection() as cytoscape.Collection;

      // (a) compounds in lens with no children in lens.
      for (const uid of visibility.collapsedCompoundUids) {
        const ele = cy.getElementById(uid);
        if (ele.nonempty() && ele.isParent()) targets = targets.union(ele);
      }

      // (b) compounds absent from the lens entirely.
      const absentCompounds = cy.nodes().filter((n) =>
        n.isParent() && !lensNodeUids.has(n.id())
      );
      if (absentCompounds.nonempty()) {
        targets = targets.union(absentCompounds);
      }

      if (targets.nonempty()) {
        // Track which compounds will be collapsed; their descendants are
        // hidden and skipped in position restoration below.
        targets.forEach((n) => {
          collapsedAncestorUids.add(n.id());
        });
        try {
          ecCollapseRecursively(ec, targets, 'applyLens.collapseByVisibilityRule', 'app');
        } catch {
          /* ignore */
        }
      }
    }

    // Step 5.25 (Bug fix 2026-05-04): apply `lod:'full'` AFTER the collapse
    // step. Why "after": when a compound C is in the lens with `lod:'full'`
    // (the user tapped its stand-in to promote it), C is also visible-collapsed
    // (its children are absent → collapse step ran). After collapse, C is no
    // longer `isParent()` in cytoscape — it's a stand-in node — so
    // `overlayLayer.show()` accepts it. Running this step BEFORE collapse
    // would hit `show()`'s isParent guard and produce an empty full-size box.
    // For pure leaves, isParent() is always false, so order doesn't matter.
    let fullLodApplied = 0;
    let fullLodSkippedCompound = 0;
    for (const [uid, lod] of Object.entries(payload.nodes)) {
      if (!surviving.has(uid)) continue;
      if (lod !== 'full') continue;
      const ele = cy.getElementById(uid);
      if (!ele.nonempty()) continue;
      // After the collapse step above, a collapsed compound is a stand-in
      // (not isParent). The remaining isParent()=true cases are EXPANDED
      // compounds — they shouldn't have lod:'full' per the save-time guard,
      // but defend here anyway: full-LOD style on an expanded compound
      // produces an empty rectangle.
      if (ele.isParent()) {
        fullLodSkippedCompound++;
        continue;
      }
      this.state.nodeLOD.set(uid, 'full');
      try { ele.data('lod', 'full'); } catch { /* ignore */ }
      const intentNode = modelNodes?.get(uid) ?? null;
      if (intentNode) {
        overlayLayer.show(uid, buildOverlayContent(intentNode));
        fullLodApplied++;
      }
    }
    trace({
      src: 'app',
      kind: 'applyLensFullLodApplied',
      data: { count: fullLodApplied, skippedExpandedCompound: fullLodSkippedCompound, lensName: payload.name }
    });

    // Step 5.5 (Path Y, 2026-05-01): restore stored absolute positions AFTER
    // collapse so cytoscape's auto-relayout doesn't clobber them.
    //
    // PIG LENSSCHEMA.NODESHAPE: positions are stored absolute (cytoscape's
    // global frame). Cytoscape pointer §6.3: never call .position() on a
    // compound parent — they auto-fit to their children. So we restore only
    // leaves; parents auto-fit around the restored leaves.
    //
    // Skip nodes whose ancestor is collapsed: they're not in the visible
    // scene. Their positions will be restored when the user expands the
    // ancestor.
    if (this.state.model && payload.positions) {
      const parentOf = this.state.model.parentOf;
      const hasCollapsedAncestor = (uid: Uid): boolean => {
        let cur = parentOf.get(uid);
        while (cur !== undefined && cur !== null) {
          if (collapsedAncestorUids.has(cur)) return true;
          cur = parentOf.get(cur);
        }
        return false;
      };

      // INSTRUMENTATION 1: log the payload BEFORE we touch anything. If this
      // entry's `count` is 0 the bug is upstream (host translator stripped them
      // out, or the user dragged but the host never wrote). Sample shows the
      // first 3 entries so we can sanity-check coords.
      const positionEntries = Object.entries(payload.positions);
      trace({
        src: 'app',
        kind: 'applyLensPayloadPositions',
        data: {
          count: positionEntries.length,
          lensName: payload.name,
          sample: positionEntries.slice(0, 3).map(([uid, p]) => ({ uid, x: p.x, y: p.y }))
        }
      });

      let restoredCount = 0;
      let skippedCollapsed = 0;
      let skippedCompound = 0;
      // Capture INTENDED writes so we can verify post-batch.
      const intended: Array<{ uid: string; x: number; y: number }> = [];
      cy.batch(() => {
        for (const [uid, absPos] of positionEntries) {
          const ele = cy.getElementById(uid);
          if (!ele.nonempty()) continue;
          if (ele.isParent()) { skippedCompound++; continue; }
          if (hasCollapsedAncestor(uid)) { skippedCollapsed++; continue; }
          try {
            ele.position(absPos);
            intended.push({ uid, x: absPos.x, y: absPos.y });
            restoredCount++;
          } catch {
            /* ignore — node may have been removed mid-apply */
          }
        }
      });

      // INSTRUMENTATION 2: read back actual cytoscape positions for every
      // node we just wrote. Any mismatch here means cytoscape rejected the
      // write inside the batch (compound auto-fit, parent constraint, etc).
      let mismatchCount = 0;
      const mismatches: Array<{ uid: string; want: { x: number; y: number }; got: { x: number; y: number } }> = [];
      for (const w of intended) {
        const actual = cy.getElementById(w.uid).position();
        if (Math.abs(actual.x - w.x) > 0.5 || Math.abs(actual.y - w.y) > 0.5) {
          mismatchCount++;
          if (mismatches.length < 5) {
            mismatches.push({ uid: w.uid, want: { x: w.x, y: w.y }, got: { x: actual.x, y: actual.y } });
          }
        }
      }

      trace({
        src: 'app',
        kind: 'applyLensPositionsRestored',
        data: {
          count: restoredCount,
          lensName: payload.name,
          skippedCollapsedAncestor: skippedCollapsed,
          skippedCompound,
          mismatchCount,
          mismatches
        }
      });
    }

    // Step 6: Show diagnostics banner for stale UIDs (computed at host translation time).
    if (payload.diagnostics.length > 0) {
      this.banner.showDiagnostics(payload.diagnostics);
    }

    showTransientStatus(`Lens applied: ${payload.name}`, 2000);
    this.state.snapshotViewport(cy);
    // Update the in-viewer selector label.
    this.activeLensName = payload.name;
    this.lensSelector.setActiveLens(payload.name);
  }

  /**
   * Apply a named lens from the cached lens dict (in-viewer selector path).
   * Computes the payload client-side and calls applyLens().
   */
  private applyLensByName(name: string): void {
    const cfg = this.cachedLenses[name];
    if (!cfg) return;

    const model = this.state.model;
    const availableNodeUids = model ? new Set(model.nodes.keys()) : new Set<string>();
    const availableLinkUids = model ? new Set(model.links.map((l) => l.uid)) : new Set<string>();

    const payload = lensConfigToPayloadClient(cfg, availableNodeUids, availableLinkUids);
    this.applyLens(payload);
  }

  /**
   * Clear the active lens: reset nodeLOD to empty, expand all compounds, hide all overlays.
   */
  private clearLens(): void {
    // Clear diagnostics banner first.
    this.banner.hide();

    if (!this.handle) return;
    const { cy, ec, overlayLayer } = this.handle;

    // Expand all collapsed nodes.
    try {
      const collapsed = cy.nodes('.cy-expand-collapse-collapsed-node');
      if (collapsed.nonempty()) {
        let targets = cy.collection() as cytoscape.Collection;
        collapsed.forEach((n) => { targets = targets.union(n); });
        ecExpandRecursively(ec, targets, 'clearLens', 'app');
      }
    } catch {
      /* ignore */
    }

    // Reset all full-LOD nodes to lean.
    for (const [uid] of this.state.nodeLOD) {
      try {
        cy.getElementById(uid).data('lod', 'lean');
        overlayLayer.hide(uid);
      } catch {
        /* ignore */
      }
    }
    this.state.nodeLOD.clear();

    // Fit to screen.
    try {
      cy.fit(undefined, 40);
    } catch {
      /* ignore */
    }

    this.state.snapshotViewport(cy);
    showTransientStatus('Lens cleared', 2000);
    // Update the in-viewer selector label.
    this.activeLensName = null;
    this.lensSelector.setActiveLens(null);
  }

  // ---------- UI phase ----------

  private setUiPhase(phase: UiPhase, statusText?: string): void {
    this.state.uiPhase = phase;
    switch (phase) {
      case 'loading':
        showSpinner(true);
        setEmptyPlaceholder(false);
        if (statusText) setStatus(statusText);
        else setStatus('Loading graph…');
        break;
      case 'ready':
        showSpinner(false);
        setEmptyPlaceholder(false);
        if (statusText) setStatus(statusText);
        // PIG DIAGNOSTICS.EDIT_CONFLICT: clear conflict banner when load succeeds.
        this.banner.clearEditConflict();
        break;
      case 'empty':
        showSpinner(false);
        this.banner.hide();
        setEmptyPlaceholder(true);
        setStatus(statusText ?? 'Empty graph — 0 nodes.');
        break;
      case 'error':
        showSpinner(false);
        if (statusText) setStatus(statusText);
        break;
      case 'stale':
        showSpinner(false);
        if (statusText) setStatus(statusText);
        break;
    }
  }

  private async loadAndRender(isReload: boolean): Promise<void> {
    const t0 = performance.now();
    let resp;
    try {
      resp = await this.messaging.loadGraph();
    } catch (err) {
      this.handleError(`load failed: ${String(err)}`, isReload);
      return;
    }
    if (!resp.ok || !resp.model) {
      this.handleError(resp.error ?? 'unknown load error', isReload);
      return;
    }

    // Cache the file hash for use in EditFieldRequest.
    if (resp.fileHash) {
      this.state.currentFileHash = resp.fileHash;
    }

    // Cache lenses and update the in-viewer selector.
    if (resp.lenses) {
      this.cachedLenses = resp.lenses;
      this.lensSelector.update(resp.lenses, this.activeLensName);
    }

    const next = rehydrateModel(resp.model);

    if (next.nodes.size === 0) {
      this.disposeHandle();
      this.state.setModel(next);
      this.setUiPhase('empty');
      return;
    }

    if (isReload && this.state.model && this.handle) {
      const diff = this.state.diff(next);
      if (diff.kind === 'metadata') {
        const cy = this.handle.cy;
        this.state.setModel(next);
        cy.batch(() => {
          for (const [uid, data] of next.nodes) {
            const node = cy.getElementById(uid);
            if (!node.nonempty()) continue;
            if (node.data('name') !== data.name) {
              node.data('name', data.name);
            }
          }
          for (const link of next.links) {
            const edge = cy.getElementById(link.uid);
            if (edge.nonempty() && edge.data('edgeType') !== link.edgeType) {
              edge.data('edgeType', link.edgeType);
            }
          }
        });
        for (const [uid, data] of next.nodes) {
          if (this.state.nodeLOD.get(uid) === 'full') {
            this.handle.overlayLayer.refreshContent(uid, data);
          }
        }
        this.applyWarnings(next);
        this.setUiPhase('ready', this.makeStatus(next, null, 'metadata only'));
        return;
      }
    }

    // Structural / first load: rebuild layout + mount.
    try {
      const tBuild0 = performance.now();
      const elkJson = buildElkJson(next);
      const tBuild1 = performance.now();

      const positioned = await runLayout(elkJson);
      const tLayout1 = performance.now();

      const positions = flattenAbsolutePositions(positioned);

      let prevViewport = this.state.viewport;
      let prevCollapseSet: Uid[] = [];
      let prevLODSet: Uid[] = [];
      if (isReload && this.handle) {
        prevViewport = { zoom: this.handle.cy.zoom(), pan: { ...this.handle.cy.pan() } };
        // PIG LAYOUT.CUES, INV-9: collect current collapse state from cy, then update collapseSet
        // to ensure it stays in sync across reloads. User manual collapses are reflected in
        // this.state.collapseSet via the onCompoundStateChange callback.
        const cyCollapsed = collectCollapsedUids(this.handle.cy);
        this.state.collapseSet = new Set(cyCollapsed);
        prevCollapseSet = cyCollapsed;
        prevLODSet = this.state.snapshotLODSet();
        this.handle.overlayLayer.teardown();
        this.disposeHandle();
      }

      const cyEl = $('cy');
      const navEl = $('cy-navigator');
      const overlayEl = $('ig-overlay-root');
      if (!cyEl || !navEl || !overlayEl) {
        this.handleError('webview DOM not ready (#cy, #cy-navigator, or #ig-overlay-root missing)', isReload);
        return;
      }

      const surviving = new Set(next.nodes.keys());
      this.state.restoreLODSet(prevLODSet, surviving);

      // Build the onNodeEditCommit callback (whole-node edit).
      const onEditCommit: NodeEditCommitCallback = async (nodeUid, fields) => {
        if (!this.state.currentFileHash) {
          return { ok: false, error: 'No file hash available — reload first.' };
        }
        if (this.state.reloadInFlight) {
          return { ok: false, error: 'Reload in progress — try again.' };
        }
        const result = await this.messaging.sendEditNode({
          nodeUid,
          fields,
          fileHash: this.state.currentFileHash
        });
        if (result.ok && result.newFileHash) {
          this.state.currentFileHash = result.newFileHash;
          // Bug 2 fix: post-edit reload is suppressed (hash-sync), so the
          // metadata-reload sync path at handleGraphChanged() never runs for this
          // edit. Mirror its work here: update state.model + cytoscape node data
          // for the edited fields. The overlay's open card was already patched
          // in htmlOverlayLayer.ts (post-commit DOM write), but state.model and
          // cy.data() must also be refreshed so any future re-render of this
          // node (LOD toggle, applyLens, re-open) reads the new value.
          this.applyLocalEditSync(nodeUid, fields);
          showTransientStatus('Saved — use Revert File to undo', 3000);
        }
        return result;
      };

      const tMount0 = performance.now();
      this.handle = mount(next, positions, cyEl, navEl, overlayEl, this.state.nodeLOD, onEditCommit);
      const tMount1 = performance.now();

      // Test hook: when the Playwright harness has installed __igTestBus,
      // expose the cytoscape instance so specs can emit synthetic gesture
      // events (tap/dbltap) against named nodes without depending on
      // canvas hit-testing. No-op in production (no __igTestBus present).
      if ((globalThis as unknown as { __igTestBus?: unknown }).__igTestBus) {
        (globalThis as unknown as { __igTestCy?: unknown }).__igTestCy = this.handle.cy;
      }

      // Dedicated CueLayer renders the cue button for every
      // compound node, regardless of LOD. Replaces the lean-mode-cue gap that
      // caused the "no +/- in sight" complaint when the overlay map was the
      // only thing rendering cues.
      if (this.cueLayer) {
        this.cueLayer.teardown();
      }
      this.cueLayer = new CueLayer(
        this.handle.cy,
        overlayEl,
        this.gestureState,
        this.handle.ec,
        // Bug 1 fix: cue click → persist visibility change to the active lens.
        // CueLayer already mutated cytoscape and state.collapseSet; we now mirror
        // the change to the on-disk lens so close/reopen restores the same view.
        // PIG LENSSCHEMA.VISIBILITY governs how membership encodes visibility.
        (uid, isNowCollapsed) => {
          void this.persistCueVisibility(uid, isNowCollapsed);
        }
      );
      this.cueLayer.initCues();

      this.state.setModel(next);

      // PIG INTERACTION.ROUTER: single owner of tap + dbltap.
      // Tear down any prior router instance — Cytoscape listeners are bound to
      // the destroyed cy instance and will not fire, but the disposers are
      // idempotent and clearing the reference avoids a leak.
      if (this.gestureRouter) {
        this.gestureRouter.dispose();
      }
      // Reset edit state on every structural mount: if a node was editing when
      // the file changed externally, the overlay was torn down and the
      // editingUid is stale.
      this.gestureState.editingUid = null;
      this.gestureRouter = new GestureRouter({ state: this.gestureState });
      this.gestureRouter.wireCytoscapeGestures({
        cy: this.handle.cy,
        overlayLayer: this.handle.overlayLayer,
        lookupNode: (uid: Uid): IntentNode | null => next.nodes.get(uid) ?? null,
        // LOD persistence: every tap-toggle (lean ↔ full) writes to the active
        // lens so the leaf's LOD survives close+reopen.
        onLodChange: (uid: Uid, lod: NodeLOD) => {
          void this.persistLeafLod(uid, lod);
        }
      });
      // Document-level edit-mode exit handlers (PIG EDITING.EXIT).
      // Outside-click → commit; Escape → cancel. Tab navigation between fields
      // inside the editing card does not exit because containment, not blur, is
      // the trigger. Lens selector is exempted so clicking the dropdown does
      // not commit an in-progress edit.
      const lensRoot = this.lensSelector.getRoot();
      this.gestureRouter.wireDocumentGestures({
        overlayLayer: this.handle.overlayLayer,
        isLensSelectorTarget: (target: EventTarget | null): boolean => {
          return target instanceof Node && lensRoot.contains(target);
        }
      });

      // Drag persistence (INTERACTION.DRAG → PERSISTENCE.AUTOSAVE)
      // moves into the router. Edit-mode suppression now reads state.editingUid
      // (any node editing → all drags suppressed) instead of the prior uiPhase
      // heuristic.
      this.gestureRouter.wireDragGestures({
        cy: this.handle.cy,
        getActiveLens: () => this.activeLensName,
        sendPersistPosition: (uid, position, lensName) => {
          void this.messaging.sendPersistPosition({
            uid,
            position,
            activeLensName: lensName
          });
        }
      });

      // Rebuild DOM overlays for full-LOD survivors.
      this.handle.overlayLayer.rebuild(this.state.nodeLOD, next.nodes);

      // Restore collapse-set on structural reload (from prior session state, not lens).
      // Lens re-apply is handled by the host via
      // LoadGraphRequestType handler (activeLensName) — no double-apply here.
      if (isReload && prevCollapseSet.length > 0) {
        const stillCollapsible = prevCollapseSet.filter((uid) => surviving.has(uid));
        if (stillCollapsible.length > 0) {
          try {
            const ec: ExpandCollapseApi = this.handle.ec;
            const cy = this.handle.cy;
            let targets = cy.collection() as cytoscape.Collection;
            for (const uid of stillCollapsible) {
              const ele = cy.getElementById(uid);
              if (ele.nonempty()) targets = targets.union(ele);
            }
            ecCollapseRecursively(ec, targets, 'reloadRestore', 'app');
          } catch {
            /* ignore */
          }
        }
      }

      // Default view: when no lens is active AND there is no prior collapse
      // state to honour, collapse every compound at depth ≥ 2 so only L0+L1
      // are visible. Keeps the initial render readable on large graphs.
      // Lens-driven loads are exempt: the host's ApplyLensNotification will
      // resolve the collapse set per the lens spec.
      const noPriorCollapseState = !isReload || prevCollapseSet.length === 0;
      if (!this.activeLensName && noPriorCollapseState) {
        try {
          const ec: ExpandCollapseApi = this.handle.ec;
          const cy = this.handle.cy;
          let deepCompounds = cy.collection() as cytoscape.Collection;
          for (const [uid, depth] of next.depthOf) {
            if (depth < 2) continue;
            const ele = cy.getElementById(uid);
            if (ele.nonempty() && ele.isParent()) {
              deepCompounds = deepCompounds.union(ele);
              this.state.collapseSet.add(uid);
            }
          }
          if (deepCompounds.nonempty()) {
            ecCollapseRecursively(ec, deepCompounds, 'defaultViewL1', 'app');
          }
        } catch {
          /* ignore */
        }
      }

      // Restore viewport on reload; otherwise fit().
      if (isReload && prevViewport) {
        try {
          this.handle.cy.zoom(prevViewport.zoom);
          this.handle.cy.pan(prevViewport.pan);
        } catch {
          /* ignore */
        }
      }
      this.state.snapshotViewport(this.handle.cy);

      const timings: PhaseTimings = {
        buildElkMs: +(tBuild1 - tBuild0).toFixed(1),
        layoutMs: +(tLayout1 - tBuild1).toFixed(1),
        mountMs: +(tMount1 - tMount0).toFixed(1),
        total: +(tMount1 - t0).toFixed(1)
      };
      // eslint-disable-next-line no-console
      console.info('[intentgraph] phase timings', timings);

      this.applyWarnings(next);

      const suffix = isReload ? 'reloaded' : null;
      this.setUiPhase('ready', this.makeStatus(next, timings.layoutMs, suffix));

      // Signal structural-mount complete.
      // Host responds with ApplyLensNotification(default_lens) if set.
      // Fired exactly once per editor lifetime on the initial mount only.
      if (!isReload && !this.bootSignalled) {
        this.bootSignalled = true;
        this.messaging.sendBootComplete();
      }
    } catch (err) {
      this.handleError(`render failed: ${String(err)}`, isReload);
    }
  }

  /** Show a yellow warning banner if the model has non-fatal warnings; else hide. */
  private applyWarnings(model: IntentGraphModel): void {
    const warnings = model.warnings ?? [];
    if (warnings.length === 0) {
      // Only clear warning banners; preserve diagnostics banner from an active lens.
      const el = document.getElementById('banner');
      if (el && el.classList.contains('banner-warn')) this.banner.hide();
      return;
    }
    this.banner.showWarning(warnings.join(' · '));
  }

  private makeStatus(model: IntentGraphModel, layoutMs: number | null, suffix: string | null): string {
    const n = model.nodes.size;
    const l = model.links.length;
    const parts = [`${n} nodes`, `${l} links`];
    if (layoutMs !== null) parts.push(`layout ${layoutMs}ms`);
    if (suffix) parts.push(suffix);
    return `Ready · ${parts.join(' · ')}`;
  }

  private handleError(message: string, isReload: boolean): void {
    // eslint-disable-next-line no-console
    console.warn('[intentgraph] error', message);
    this.setUiPhase('error', `Error: ${message}`);
    this.banner.show(`IntentGraph: ${message}`, {
      withRetry: true,
      onRetry: () => {
        this.banner.hide();
        this.setUiPhase('loading');
        void this.loadAndRender(isReload);
      }
    });
  }

  private async handleGraphChanged(): Promise<void> {
    if (this.state.reloadInFlight) {
      this.state.pending = true;
      return;
    }
    this.state.reloadInFlight = true;
    try {
      this.setUiPhase('loading', 'Reloading graph…');
      await this.loadAndRender(/*isReload*/ true);
    } finally {
      this.state.reloadInFlight = false;
      if (this.state.pending) {
        this.state.pending = false;
        void this.handleGraphChanged();
      }
    }
  }

  private disposeHandle(): void {
    // Tear down CueLayer alongside cy. Order matters — CueLayer
    // detaches cy listeners, so it must run BEFORE cy.destroy.
    if (this.cueLayer) {
      try {
        this.cueLayer.teardown();
      } catch {
        /* ignore */
      }
      this.cueLayer = null;
    }
    if (this.handle) {
      try {
        this.handle.dispose();
      } catch {
        /* ignore */
      }
      this.handle = null;
    }
  }
}

// ---------- Bootstrap ----------

async function main(): Promise<void> {
  const app = new App();
  await app.run();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    void main();
  });
} else {
  void main();
}
