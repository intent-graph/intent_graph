// HTML overlay layer for full-LOD nodes.
// Manages a DOM <div> positioned over each Cytoscape node that is in `full` LOD.
// Design history (see prior architecture/lifecycle/z-order and gesture rules):
//       supersedes §6 pan/zoom, §8, §11 of the original bounds design.
//       Supersedes tick-write block, CSS font-scaling pattern; replaces
//         --ig-scale with transform: scale().
//       Per-field edit affordance: contenteditable lifecycle, Enter/blur/Escape
//         handlers, error-rollback.
//       Gesture-model swap: pencil-icon removed; double-click via
//         cy.on('dbltap') hits enterEditModeAtPoint(); pointer-events
//         toggled per field via .ig-editing class.
//
// Key constraints:
//   - No Cytoscape import at module level (cy instance passed in constructor).
//   - All text set via textContent only; never innerHTML (CSP + XSS safety).
//   - Overlays use pointer-events: none (taps pass through to canvas).
//   - Editable fields default pointer-events: none; gain auto via .ig-editing only
//     while contenteditable='true' (toggled by enterEditModeAtPoint / blur handlers).
//   - Position derived from node.renderedBoundingBox() on every `render` event.
//   - Overlay intrinsic size fixed at FULL_LOD_WIDTH × FULL_LOD_HEIGHT; scaled via transform.
//   - teardown() must be called while cy is still alive (listener detach requires it).

import type cytoscape from 'cytoscape';
import type { IntentNode, NodeLOD, Uid } from '../../shared/graphTypes';
import type { EditableField, EditNodeFields } from '../../messaging/messageTypes';
import { trace } from '../trace';
import { createEditStateMachine, type EditStateMachine } from './editStateMachine';
// FULL_LOD_WIDTH/FULL_LOD_HEIGHT: canonical full-LOD reference dimensions (elkBridge.ts).
// Full-LOD overlays use FULL_LOD_WIDTH (240 px) × FULL_LOD_HEIGHT (180 px) — UX Rework.
// LEAF_WIDTH/LEAF_HEIGHT (lean node sentinels) are NOT used for full-LOD overlays.
// Must stay in sync if elkBridge.ts values ever change.
import { FULL_LOD_WIDTH, FULL_LOD_HEIGHT } from '../elkBridge';

/** Content to render inside a full-LOD overlay card. */
export interface OverlayContent {
  uid: string;
  name: string;
  intent?: string;
  epistemic_state?: string;
  constraints?: string[];  // up to 3 shown; "+N more" line appended if longer
}

/** Callback fired by the overlay layer when the user commits a single-field edit.
 *  (Legacy path — kept for compatibility. Original single-field-edit design.) */
export type EditCommitCallback = (
  nodeUid: Uid,
  field: EditableField,
  oldValue: string,
  newValue: string,
  constraintIndex?: number
) => Promise<{ ok: boolean; error?: string; newFileHash?: string }>;

/** Callback fired by the overlay layer when the user commits a whole-node edit.
 *  All changed fields are submitted together. */
export type NodeEditCommitCallback = (
  nodeUid: Uid,
  fields: EditNodeFields
) => Promise<{ ok: boolean; error?: string; newFileHash?: string }>;

// CompoundStateChangeCallback removed — cue clicks are handled
// by CueLayer (src/webview/overlay/cueLayer.ts), not the overlay layer.

/** Max constraints shown before "+N more" line. */
const MAX_CONSTRAINTS = 3;

/** Log a console warning when active overlay count exceeds this (profiling signal). */
const OVERLAY_COUNT_WARNING = 50;

/**
 * Overlay is hidden and canvas `name` label activated when node height
 * on screen drops below this threshold.
 */
/** Screen-space node height below which the overlay hides and canvas label fallback activates.
 *  Raised from 24 → 50 (Amend 3 Bug 2): at 24 px text was already unreadable mush; 50 px
 *  matches the point where glyph clarity drops off at normal DPR. */
const MIN_READABLE_HEIGHT = 50;
// NOTE: REFERENCE_HEIGHT (was 60) removed in Amendment 2 — superseded by LEAF_HEIGHT then FULL_LOD_HEIGHT.
// Amendment 3 (Bug 3): reference height was FULL_LOD_HEIGHT (120 px).
// Amendment 4: reference box was FULL_LOD_WIDTH (320 px) × FULL_LOD_HEIGHT (360 px).
// UX Rework: reference box is FULL_LOD_WIDTH (240 px) × FULL_LOD_HEIGHT (180 px).
// Scale = rect / reference → uniform. --ig-scale CSS variable removed in Amendment 2; not restored here.

/**
 * Build an OverlayContent from an IntentNode.
 * Exported so main.ts can call buildOverlayContent(node) on LOD toggle.
 */
export function buildOverlayContent(node: IntentNode): OverlayContent {
  return {
    uid: node.uid,
    name: node.name,
    intent: node.intent,
    epistemic_state: node.epistemic_state,
    constraints: node.constraints
  };
}

/**
 * Pure function: decide whether an overlay should be hidden based on node state.
 * Testable without DOM or Cytoscape dependencies.
 * PIG LAYOUT.OVERLAY #4: overlay visibility is coupled to compound collapse state.
 *
 * @param state.nonempty - node still exists in the cy graph
 * @param state.visible - node.visible() returns true (Cytoscape's own visibility)
 * @param state.ancestorCollapsed - any ancestor has 'cy-expand-collapse-collapsed-node' class
 * @returns true if overlay should be hidden; false if it should be visible
 */
export function shouldHideOverlay(state: {
  nonempty: boolean;
  visible: boolean;
  ancestorCollapsed: boolean;
}): boolean {
  // Hide if node was removed from graph.
  if (!state.nonempty) return true;
  // Hide if Cytoscape marked it as not visible.
  if (!state.visible) return true;
  // Hide if any ancestor is a collapsed compound (PIG constraint #4).
  if (state.ancestorCollapsed) return true;
  // Otherwise, let it be visible (subject to off-screen and min-height checks below).
  return false;
}

// NEUTRAL_CUE_SVG and the cue rendering pipeline have moved
// to src/webview/overlay/cueLayer.ts.

/**
 * Manages full lifecycle of DOM overlays for full-LOD Cytoscape nodes.
 * Compound cue rendering is owned by CueLayer (src/webview/overlay/cueLayer.ts);
 * this class no longer tracks per-compound DOM elements.
 * One instance per Cytoscape graph mount; replaced on structural reload.
 */
export class HtmlOverlayLayer {
  private readonly cy: cytoscape.Core;
  private readonly root: HTMLElement;
  /** uid → overlay card element */
  private readonly overlayMap = new Map<string, HTMLElement>();
  // Compound cue rendering moved to a dedicated CueLayer
  // (src/webview/overlay/cueLayer.ts). The cue is now visible for every
  // compound node regardless of overlay/LOD state, fixing the "no +/- in
  // sight" complaint where lean compounds had no cue rendered.
  private readonly onRender: () => void;
  /** Optional callback fired when user commits a whole-node edit. */
  private readonly onNodeEditCommit: NodeEditCommitCallback | null;
  /** Edit-mode state machine: owns the contenteditable lifecycle, focus, and DOM
   *  flip-flops for entering/exiting edit on a card. Public state queries
   *  (`isEditingNode`, `getEditingUid`) delegate to this. */
  private readonly editState: EditStateMachine = createEditStateMachine();
  /** Pending edits awaiting host confirmation. Key: `${uid}|${field}` or `${uid}|constraint|${index}`.
   *  Value: the proposed newValue. INV-6: DOM is not updated until ok=true response. */
  private readonly pendingEdits = new Map<string, string>();

  constructor(
    cy: cytoscape.Core,
    root: HTMLElement,
    onNodeEditCommit?: NodeEditCommitCallback
  ) {
    this.cy = cy;
    this.root = root;
    this.onNodeEditCommit = onNodeEditCommit ?? null;

    // Named reference so we can detach the same function in teardown().
    this.onRender = (): void => {
      const t0 = performance.now();
      this.tickAll();
      const dt = performance.now() - t0;
      if (dt > 16) {
        // eslint-disable-next-line no-console
        console.warn('[intentgraph] overlay tickAll took', dt.toFixed(1), 'ms');
      }
    };

    cy.on('render', this.onRender);
  }

  /**
   * Create and position overlay for one full-LOD node.
   * Idempotent: calling show() for an already-visible uid replaces content.
   * No-op if the node is a compound (parent) — full LOD is leaf-only.
   */
  show(uid: string, content: OverlayContent): void {
    const ele = this.cy.getElementById(uid);
    // Compound guard: full-LOD overlay is forbidden on compound (parent) nodes.
    if (!ele.nonempty() || ele.isParent()) return;

    let card = this.overlayMap.get(uid);
    if (!card) {
      card = this.createCard();
      card.dataset['uid'] = uid;
      this.overlayMap.set(uid, card);
      this.root.appendChild(card);
      if (this.overlayMap.size > OVERLAY_COUNT_WARNING) {
        // eslint-disable-next-line no-console
        console.warn('[intentgraph] overlay count exceeded', OVERLAY_COUNT_WARNING);
      }
    }
    this.populateCard(card, content);
    // Synchronous first tick so the card appears at the correct position on the
    // very first frame — no flash of mis-positioned content.
    this.tickOne(uid, card);
  }

  /**
   * Remove overlay for one node. No-op if absent.
   * If the node was in `lodDisplay = 'small'` state, restore it to avoid
   * leaving the canvas name label active.
   */
  hide(uid: string): void {
    const card = this.overlayMap.get(uid);
    if (!card) return;
    if (card.parentNode) card.parentNode.removeChild(card);
    this.overlayMap.delete(uid);
    // Restore lodDisplay so the canvas label fallback doesn't linger.
    const ele = this.cy.getElementById(uid);
    if (ele.nonempty() && ele.data('lodDisplay') === 'small') {
      ele.data('lodDisplay', 'normal');
    }
  }

  /**
   * Rebuild all overlays after structural reload.
   * Called after the new cy is mounted and wireTapLOD is wired.
   * Iterates lodMap for 'full' entries and calls show() for each.
   */
  rebuild(lodMap: Map<string, NodeLOD>, nodes: Map<string, IntentNode>): void {
    // Teardown existing overlays (should already be gone after teardown(), but
    // rebuild() may also be called on a fresh layer for the first structural load).
    this.teardownOverlays();

    for (const [uid, lod] of lodMap) {
      if (lod !== 'full') continue;
      const node = nodes.get(uid);
      if (!node) continue;
      this.show(uid, buildOverlayContent(node));
    }

    // Cue rendering is now owned by CueLayer (initialised separately
    // by cyMount.ts after the cy elements are added). The overlay layer no longer
    // tracks compound cue buttons — that fixes the "lean compound has no cue"
    // bug where the overlay map was the only thing rendering cues.
  }

  /**
   * Update overlay text content in-place (metadata reload path).
   * No DOM insertion or removal; no position update needed (render listener handles it).
   */
  refreshContent(uid: string, node: IntentNode): void {
    const card = this.overlayMap.get(uid);
    if (!card) return;
    this.populateCard(card, buildOverlayContent(node));
  }

  /**
   * Remove all overlays and detach render listener.
   * MUST be called before cy.destroy() so cy.off() works.
   */
  teardown(): void {
    this.cy.off('render', this.onRender);
    this.teardownOverlays();
  }

  /**
   * Returns whether the given node UID is currently in whole-node edit mode.
   * Used by cyMount.ts to suppress LOD toggle while editing.
   */
  isEditingNode(uid: string): boolean {
    return this.editState.isEditing(uid);
  }

  /**
   * Returns whether ANY node is currently in edit mode.
   */
  isAnyNodeEditing(): boolean {
    return this.editState.getCurrentEditingUid() !== null;
  }

  /**
   * UID of the node currently in edit mode, or null. Exposed
   * for the gesture router's containment-check (outside-click → commit).
   */
  getEditingUid(): string | null {
    return this.editState.getCurrentEditingUid();
  }

  /**
   * Overlay card DOM element for the node currently in edit mode, or null.
   * The gesture router uses this to test containment against
   * `event.target` on document-level pointerdown, deciding commit vs. continue.
   */
  getEditingCard(): HTMLElement | null {
    const uid = this.editState.getCurrentEditingUid();
    if (!uid) return null;
    return this.overlayMap.get(uid) ?? null;
  }

  /**
   * Enter whole-node edit mode for the given UID.
   * All editable fields in the card become contenteditable simultaneously.
   * If another node is already in edit mode, it is committed first.
   *
   * Called from cyMount.ts `dbltap` handler. Returns false if the node has
   * no active overlay card (not in full LOD), or if edit commit is not wired.
   *
   * Replaces enterEditModeAtPoint.
   * Optional `corr` ties this entry to the originating dbltap.
   */
  enterNodeEditMode(uid: string, corr?: string): boolean {
    if (!this.onNodeEditCommit) {
      trace({ src: 'overlay', kind: 'editEnter', corr, data: { uid, ok: false } });
      return false;
    }

    // Commit any in-progress edit on a different node before switching focus.
    const editingUid = this.editState.getCurrentEditingUid();
    if (editingUid !== null && editingUid !== uid) {
      void this.commitNodeEdit(editingUid);
    }

    const card = this.overlayMap.get(uid);
    if (!card) {
      trace({ src: 'overlay', kind: 'editEnter', corr, data: { uid, ok: false } });
      return false;
    }

    return this.editState.enterEditMode(card, uid, corr);
  }

  /**
   * Exit whole-node edit mode for the given UID and collect changed fields.
   * Submits all changes via `onNodeEditCommit`. Updates overlay text on success.
   * Called from the document-level click-outside handler in main.ts.
   */
  async commitNodeEdit(uid: string): Promise<boolean> {
    if (!this.editState.isEditing(uid)) return false;

    const card = this.overlayMap.get(uid);
    if (!card) {
      this.editState.forceClear();
      return false;
    }

    // Collect all changed fields by comparing DOM text to pre-edit value (dataset['igValue']).
    // PIG EDITING.PERSISTENCE #3: stash newValue but DON'T update DOM yet.
    const fields = Array.from(card.querySelectorAll<HTMLElement>('[data-ig-editable="1"]'));
    const changedName: string | undefined = (() => {
      const el = fields.find((f) => f.dataset['igField'] === 'name');
      if (!el) return undefined;
      const newVal = (el.textContent ?? '').trim();
      const origVal = (el.dataset['igValue'] ?? '').trim();
      return newVal !== origVal && newVal.length > 0 ? newVal : undefined;
    })();
    const changedIntent: string | undefined = (() => {
      const el = fields.find((f) => f.dataset['igField'] === 'intent');
      if (!el) return undefined;
      const newVal = (el.textContent ?? '').trim();
      const origVal = (el.dataset['igValue'] ?? '').trim();
      return newVal !== origVal && newVal.length > 0 ? newVal : undefined;
    })();
    const changedEpistemic: string | undefined = (() => {
      const el = fields.find((f) => f.dataset['igField'] === 'epistemic_state');
      if (!el) return undefined;
      const newVal = (el.textContent ?? '').trim();
      const origVal = (el.dataset['igValue'] ?? '').trim();
      return newVal !== origVal && newVal.length > 0 ? newVal : undefined;
    })();
    const changedConstraints: string[] | undefined = (() => {
      const constraintEls = fields.filter((f) => f.dataset['igField'] === 'constraint');
      if (constraintEls.length === 0) return undefined;
      const arr: string[] = [];
      let anyChanged = false;
      for (const el of constraintEls) {
        const ciStr = el.dataset['igConstraintIndex'];
        const ci = ciStr !== undefined ? parseInt(ciStr, 10) : -1;
        if (ci < 0) continue;
        const newVal = (el.textContent ?? '').trim();
        const origVal = (el.dataset['igValue'] ?? '').trim();
        arr[ci] = newVal || origVal;
        if (newVal !== origVal && newVal.length > 0) anyChanged = true;
      }
      return anyChanged ? arr : undefined;
    })();

    // INV-6: Restore DOM to pre-edit state immediately (do NOT show unsaved changes).
    // User's typed text is gone; we stash it in pendingEdits, pending host confirmation.
    this.editState.restorePreEditDOM(card);

    // Nothing changed — no-op.
    if (!changedName && !changedIntent && !changedEpistemic && !changedConstraints) {
      this.editState.exitEditModeDOM(card);
      return true;
    }

    // Stash the proposed values in pendingEdits. Key format: uid|field or uid|constraint|index.
    if (changedName) this.pendingEdits.set(`${uid}|name`, changedName);
    if (changedIntent) this.pendingEdits.set(`${uid}|intent`, changedIntent);
    if (changedEpistemic) this.pendingEdits.set(`${uid}|epistemic_state`, changedEpistemic);
    if (changedConstraints) {
      for (let i = 0; i < changedConstraints.length; i++) {
        if (changedConstraints[i]) {
          this.pendingEdits.set(`${uid}|constraint|${i}`, changedConstraints[i]);
        }
      }
    }

    if (this.onNodeEditCommit) {
      const fieldsChangedCount = (changedName ? 1 : 0) + (changedIntent ? 1 : 0) + (changedEpistemic ? 1 : 0) + (changedConstraints ? changedConstraints.filter(Boolean).length : 0);
      const result = await this.onNodeEditCommit(uid, {
        name: changedName,
        intent: changedIntent,
        epistemic_state: changedEpistemic,
        constraints: changedConstraints
      });

      // Exit edit mode after response (whether ok or not).
      this.editState.exitEditModeDOM(card);

      // Trace after host response so hostOk is known.
      trace({ src: 'overlay', kind: 'editCommit', data: { uid, fieldsChanged: fieldsChangedCount, hostOk: result.ok, error: result.error } });

      if (result.ok) {
        // PIG EDITING.PERSISTENCE #3: write pending newValues to DOM, clear pending entries.
        const freshFields = Array.from(card.querySelectorAll<HTMLElement>('[data-ig-editable="1"]'));
        for (const el of freshFields) {
          const field = el.dataset['igField'] as EditableField;
          const prefix = el.dataset['igPrefix'] ?? '';
          if (field === 'name' && changedName) {
            el.dataset['igValue'] = changedName;
            el.textContent = prefix + changedName;
            this.pendingEdits.delete(`${uid}|name`);
          } else if (field === 'intent' && changedIntent) {
            el.dataset['igValue'] = changedIntent;
            el.textContent = prefix + changedIntent;
            this.pendingEdits.delete(`${uid}|intent`);
          } else if (field === 'epistemic_state' && changedEpistemic) {
            el.dataset['igValue'] = changedEpistemic;
            el.textContent = prefix + changedEpistemic;
            this.pendingEdits.delete(`${uid}|epistemic_state`);
          } else if (field === 'constraint' && changedConstraints) {
            const ciStr = el.dataset['igConstraintIndex'];
            const ci = ciStr !== undefined ? parseInt(ciStr, 10) : -1;
            if (ci >= 0 && changedConstraints[ci] !== undefined) {
              el.dataset['igValue'] = changedConstraints[ci];
              el.textContent = prefix + changedConstraints[ci];
              this.pendingEdits.delete(`${uid}|constraint|${ci}`);
            }
          }
        }
        // Brief "saved" indication.
        card.classList.add('ig-card--saved');
        setTimeout(() => card.classList.remove('ig-card--saved'), 2000);
      } else {
        // PIG DIAGNOSTICS.EDIT_CONFLICT #4: discard pending entries (DOM already correct).
        // Banner fires via separate host path (EditConflictNotification in IntentGraphEditorProvider).
        if (changedName) this.pendingEdits.delete(`${uid}|name`);
        if (changedIntent) this.pendingEdits.delete(`${uid}|intent`);
        if (changedEpistemic) this.pendingEdits.delete(`${uid}|epistemic_state`);
        if (changedConstraints) {
          for (let i = 0; i < changedConstraints.length; i++) {
            this.pendingEdits.delete(`${uid}|constraint|${i}`);
          }
        }
      }
      return result.ok;
    }

    this.editState.exitEditModeDOM(card);
    return true;
  }

  /** Cancel (discard changes) and exit edit mode without committing. */
  cancelNodeEdit(uid: string): void {
    if (!this.editState.isEditing(uid)) return;
    const card = this.overlayMap.get(uid);
    if (!card) { this.editState.forceClear(); return; }
    this.editState.cancelEdit(card);
  }

  // ── Private helpers ──────────────────────────────────────────────────────────

  private teardownOverlays(): void {
    for (const card of this.overlayMap.values()) {
      if (card.parentNode) card.parentNode.removeChild(card);
    }
    this.overlayMap.clear();
    // Cue button removal is now CueLayer.teardown's responsibility.
  }

  /** Create an empty overlay card element. All styling comes from styles.css `.ig-full-overlay`.
   *  Width/height set ONCE here at reference size; tickOne never rewrites them.
   *  UX Rework: uses FULL_LOD_WIDTH × FULL_LOD_HEIGHT (240 × 180 px) — 1.5× wide, 1.5× tall
   *  vs the pre-Amend-4 base (160 × 120). Matches the Cytoscape node rect for full-LOD. */
  private createCard(): HTMLElement {
    const card = document.createElement('div');
    card.className = 'ig-full-overlay';
    // Fix intrinsic size at the full-LOD reference dimensions (Amendment 4).
    // transform: scale(s) in tickOne maps this fixed box onto the rendered node rect.
    card.style.width  = FULL_LOD_WIDTH  + 'px';
    card.style.height = FULL_LOD_HEIGHT + 'px';

    // Removed the obsolete inline `.ig-overlay-cue` div. The cue
    // is now a top-level DOM button positioned by CueLayer for every compound,
    // not a card-internal element.
    return card;
  }

  /**
   * Write content into the named sub-elements of a card via textContent.
   * Never uses innerHTML — all user data is treated as plain text.
   *
   * Card DOM structure (no pencil button; dbltap drives edit entry):
   *   .ig-full-overlay
   *     .ig-edit-row
   *       .ig-fn-name [data-ig-editable='1'] [.ig-edit-field+.ig-editing when active]
   *     .ig-edit-row
   *       .ig-fn-intent [data-ig-editable='1']
   *     .ig-edit-row
   *       .ig-fn-epistemic [data-ig-editable='1'] (free-form, editable)
   *     .ig-fn-constraints
   *       .ig-edit-row (×N — up to MAX_CONSTRAINTS)
   *         .ig-fn-constraint [data-ig-editable='1']
   *       .ig-fn-more           (if N > MAX_CONSTRAINTS — not editable)
   */
  private populateCard(card: HTMLElement, content: OverlayContent): void {
    // Clear and rebuild children.
    while (card.firstChild) card.removeChild(card.firstChild);

    const canEdit = this.onNodeEditCommit !== null;

    // Name (always present, bold).
    const nameRow = this.createEditRow(
      content.uid,
      'name',
      content.name,
      'ig-fn-name',
      canEdit,
      undefined
    );
    card.appendChild(nameRow);

    // Intent (optional).
    if (content.intent !== undefined) {
      const intentRow = this.createEditRow(
        content.uid,
        'intent',
        content.intent,
        'ig-fn-intent',
        canEdit,
        undefined
      );
      card.appendChild(intentRow);
    }

    // Epistemic state (optional, free-form, editable — mirrors the intent field).
    // Rendered via createEditRow so it gains data-ig-editable when canEdit; keeps the
    // .ig-fn-epistemic badge class for styling.
    if (content.epistemic_state !== undefined) {
      const epistRow = this.createEditRow(
        content.uid,
        'epistemic_state',
        content.epistemic_state,
        'ig-fn-epistemic',
        canEdit,
        undefined
      );
      card.appendChild(epistRow);
    }

    // Constraints (optional, up to MAX_CONSTRAINTS shown; each editable).
    if (content.constraints && content.constraints.length > 0) {
      const cBlock = document.createElement('div');
      cBlock.className = 'ig-fn-constraints';
      const shown = content.constraints.slice(0, MAX_CONSTRAINTS);
      for (let ci = 0; ci < shown.length; ci++) {
        const cRow = this.createEditRow(
          content.uid,
          'constraint',
          shown[ci],
          'ig-fn-constraint',
          canEdit,
          ci,
          '• '  // bullet prefix shown in display only, stripped on edit
        );
        cBlock.appendChild(cRow);
      }
      if (content.constraints.length > MAX_CONSTRAINTS) {
        const moreEl = document.createElement('div');
        moreEl.className = 'ig-fn-more';
        moreEl.textContent = `… +${content.constraints.length - MAX_CONSTRAINTS} more`;
        cBlock.appendChild(moreEl);
      }
      card.appendChild(cBlock);
    }
  }

  /**
   * Create a row containing a display element.
   * The row and its children are pointer-events: none by default.
   * The text element gains .ig-editing (pointer-events: auto) only while
   * contenteditable='true' (toggled by enterEditMode / blur handlers).
   *
   * @param uid         Node UID.
   * @param field       'name' | 'intent' | 'constraint'.
   * @param value       Current field value (plain text, no bullet prefix).
   * @param textClass   CSS class for the display span.
   * @param editable    Whether this field participates in double-click edit (stored as data attr).
   * @param constraintIndex  Index within constraints array (only when field==='constraint').
   * @param displayPrefix   Optional prefix prepended to display text only (e.g. '• ').
   */
  private createEditRow(
    uid: Uid,
    field: EditableField,
    value: string,
    textClass: string,
    editable: boolean,
    constraintIndex: number | undefined,
    displayPrefix = ''
  ): HTMLElement {
    const row = document.createElement('div');
    row.className = 'ig-edit-row';

    const textEl = document.createElement('div');
    textEl.className = textClass;
    textEl.textContent = displayPrefix + value;
    // Store edit metadata as data attributes so enterNodeEditMode/commitNodeEdit can recover them.
    if (editable) {
      textEl.dataset['igEditable'] = '1';
      textEl.dataset['igField'] = field;
      textEl.dataset['igUid'] = uid;
      textEl.dataset['igValue'] = value;
      textEl.dataset['igPrefix'] = displayPrefix;
      if (constraintIndex !== undefined) {
        textEl.dataset['igConstraintIndex'] = String(constraintIndex);
      }
    }
    row.appendChild(textEl);

    return row;
  }

  /** Iterate the active overlay map and update position/transform for every card.
   *  Cue ticking moved to CueLayer's own render listener. */
  private tickAll(): void {
    for (const [uid, card] of this.overlayMap) {
      this.tickOne(uid, card);
    }
  }

  /**
   * Position one overlay card using the node's rendered bounding box (screen-space rect).
   * Amendment 2: overlay intrinsic size is fixed once in createCard; per-frame writes are
   * left, top, transform only — no width/height/--ig-scale.
   * UX Rework: reference box is FULL_LOD_WIDTH × FULL_LOD_HEIGHT (240 × 180).
   *
   * Reads `renderedBoundingBox()` once (O(1), no reflow), applies off-screen / threshold
   * checks, then writes exactly 3 style properties (+ at most 1 display flip per transition).
   *
   * Never reads layout properties back from the overlay element itself (no getBoundingClientRect
   * etc.) — write-only after the initial rect read.
   */
  private tickOne(uid: string, el: HTMLElement): void {
    const node = this.cy.getElementById(uid);

    // (a-pre) Removal/visibility check — apply the pure predicate to decide if overlay should be hidden.
    // PIG LAYOUT.OVERLAY constraint #4: overlay visibility is coupled to compound collapse state.
    let ancestorCollapsed = false;
    for (const ancestor of node.ancestors().nodes()) {
      if (ancestor.hasClass('cy-expand-collapse-collapsed-node')) {
        ancestorCollapsed = true;
        break;
      }
    }
    const nodeState = {
      nonempty: node.nonempty(),
      visible: node.visible(),
      ancestorCollapsed
    };
    if (shouldHideOverlay(nodeState)) {
      el.style.display = 'none';
      return;
    }

    // (a) Read rect once — no subsequent layout reads.
    const rect = node.renderedBoundingBox({});
    const vpW = this.root.clientWidth;
    const vpH = this.root.clientHeight;

    // (b) Off-screen check — hide without touching lodDisplay.
    const out = rect.x2 < 0 || rect.x1 > vpW || rect.y2 < 0 || rect.y1 > vpH;
    if (out) {
      el.style.display = 'none';
      return;
    }

    // (c) Below-readable-height threshold — hide and flip canvas label fallback.
    const small = rect.h < MIN_READABLE_HEIGHT;
    if (small) {
      el.style.display = 'none';
      // Guard: only write node data when value changes (avoids Cytoscape re-render loop).
      if (node.data('lodDisplay') !== 'small') {
        node.data('lodDisplay', 'small');
      }
      return;
    }

    // (d) Visible path — restore display and lodDisplay, then write position + transform.
    if (el.style.display === 'none') {
      el.style.display = '';
    }
    if (node.data('lodDisplay') !== 'normal') {
      node.data('lodDisplay', 'normal');
    }

    // Amendment 3 (Bug 1 — deformation fix): uniform scale.
    // Root cause: scale(scaleX, scaleY) is anisotropic when rect aspect ≠ reference aspect.
    // Fix: s = min(scaleX, scaleY) → single-arg scale(s) → always uniform, never deformed.
    // Side effect: when the rendered rect's aspect is wider than 240:180, unused space appears
    // on the right; when taller, on the bottom. Acceptable — empty padding beats deformed text.
    // transform-origin: top left (styles.css) anchors the overlay at rect.x1 / rect.y1.
    // UX Rework: reference box is FULL_LOD_WIDTH × FULL_LOD_HEIGHT (240 × 180).
    const referenceW = FULL_LOD_WIDTH;   // 240 px (UX Rework: 1.5× the pre-Amend-4 width)
    const referenceH = FULL_LOD_HEIGHT;  // 180 px (UX Rework: 1.5× the pre-Amend-4 height)
    const scaleX = rect.w / referenceW;
    const scaleY = rect.h / referenceH;
    const s = Math.min(scaleX, scaleY);  // uniform — glyphs never distorted
    el.style.left      = `${rect.x1}px`;
    el.style.top       = `${rect.y1}px`;
    el.style.transform = `scale(${s})`;
    // NOTE: width, height, --ig-scale are intentionally NOT written here (Amendment 2).
  }
}
