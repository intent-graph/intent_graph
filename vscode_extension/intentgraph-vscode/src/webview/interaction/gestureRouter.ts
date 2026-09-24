// GestureRouter — single owner of all five user gestures defined in PIG
// INTERACTION.GESTURES. Replaces the scattered wireTapLOD / wireDblTapEdit /
// wireDragPersist functions and the orphaned document-level click-outside
// handler comment in main.ts:20.
//
// Five gestures:
//   1. tap on node body          → LOD machine transition
//   2. dbltap on node body       → Mode machine transition (enter edit)
//   3. cue click                 → Compound machine transition
//   4. drag (grab → free)        → position persist
//   5. lens-menu interactions    → routed through DOM listeners on the
//                                  LensSelector + lens CRUD buttons
//
// PIG INTERACTION.MODES enforces three orthogonal state machines. The router
// is the single place those machines transition; every transition is gated by
// explicit state checks against `GestureState` rather than timing windows.
//
// Responsibilities:
//   - Owns tap and dbltap. 350ms window replaced by state.editingUid
//     check. Dbltap on lean now promotes+edits.
//   - Owns document-level pointerdown (outside-click → commit) and
//     keydown Escape (cancel). Tab navigation between fields inside
//     the editing card does not exit because containment, not blur,
//     is the trigger.
//   - Owns grab + free (drag persistence). Edit-mode suppression now
//     reads state.editingUid (any node editing → suppress all drags).

import type cytoscape from 'cytoscape';

import type { IntentNode, NodeLOD, Position, Uid } from '../../shared/graphTypes';
import { buildOverlayContent, type HtmlOverlayLayer } from '../overlay/htmlOverlayLayer';
import type { GestureState } from './state';
import { trace, corr as makeCorr } from '../trace';

/**
 * Construction options. Kept narrow on purpose — the router does not own
 * Cytoscape / overlay / cue / messaging instances; those are passed at wire
 * time as callbacks so the router stays composable and unit-testable.
 */
export interface GestureRouterOptions {
  /** Authoritative state for all suppression and transition checks. */
  state: GestureState;
}

/**
 * Dependencies for the cy-side gesture wiring (tap, dbltap).
 * Drag (grab/free) is wired separately in a later step.
 */
export interface CytoscapeGestureDeps {
  /** Cytoscape core instance. */
  cy: cytoscape.Core;
  /** Overlay layer — owns the full-LOD DOM cards and edit-mode state. */
  overlayLayer: HtmlOverlayLayer;
  /** Look up a node's IntentNode payload by uid (for overlay content). */
  lookupNode: (uid: Uid) => IntentNode | null;
  /**
   * Notify the host/state of an LOD transition. The router has already
   * mutated state.nodeLOD and called overlayLayer.show/hide; this callback
   * exists for any side effects the app needs (none today, but keeps the
   * router decoupled from main.ts internals).
   */
  onLodChange?: (uid: Uid, next: NodeLOD) => void;
}

/**
 * Dependencies for document-level gesture wiring (pointerdown for outside-click
 * commit, keydown for Escape cancel).
 */
export interface DocumentGestureDeps {
  /** Overlay layer — exposes editing uid + the editing card DOM for containment checks. */
  overlayLayer: HtmlOverlayLayer;
  /**
   * Predicate: does this DOM target belong to the lens selector / its dropdown
   * (or any other UI surface that should NOT trigger an edit-mode exit)? The
   * router treats targets inside this region as part of the chrome rather than
   * as an outside-click against the editing card.
   */
  isLensSelectorTarget?: (target: EventTarget | null) => boolean;
}

/**
 * Dependencies for drag-persistence wiring (grab → free).
 *
 * `getActiveLens` returns the lens to write into; null triggers PERSISTENCE.AUTOCREATE
 * on the host side. `sendPersistPosition` is the messaging shim — the router does
 * not own the messaging instance.
 */
export interface DragGestureDeps {
  cy: cytoscape.Core;
  getActiveLens: () => string | null;
  sendPersistPosition: (uid: Uid, position: Position, lensName: string | null) => void;
}

/**
 * Pure-logic helper: determine if a grab→free sequence represents an actual
 * drag (movement above the threshold). Mirrors cyMount.ts::wasActualDrag.
 */
export function wasActualDrag(
  startPos: Position | undefined,
  endPos: Position,
  threshold = 1
): boolean {
  if (!startPos) return false;
  return (
    Math.abs(startPos.x - endPos.x) >= threshold ||
    Math.abs(startPos.y - endPos.y) >= threshold
  );
}

/**
 * Pure decision function for whether a pointerdown event should commit the
 * current edit. Exported for unit testing (no DOM dependency beyond the inputs).
 *
 * Returns true iff:
 *   - a node is currently editing (editingCard is non-null), AND
 *   - the event target is NOT inside the editing card, AND
 *   - the event target is NOT inside any chrome region the caller wants to
 *     exempt (lens selector dropdown, etc.).
 *
 * Tab navigation between fields inside the card does not generate a pointerdown
 * on the document, so this function is naturally robust to that case.
 */
export function shouldCommitOnPointerDown(args: {
  editingCard: HTMLElement | null;
  target: EventTarget | null;
  isChromeTarget?: (target: EventTarget | null) => boolean;
}): boolean {
  const { editingCard, target, isChromeTarget } = args;
  if (!editingCard) return false;
  // Target inside the editing card → keep editing.
  if (target instanceof Node && editingCard.contains(target)) return false;
  // Target inside any caller-defined chrome region → keep editing.
  if (isChromeTarget?.(target)) return false;
  return true;
}

/**
 * The router. One instance per panel mount. `dispose()` detaches every
 * listener it attached.
 */
export class GestureRouter {
  private readonly state: GestureState;
  private readonly disposers: Array<() => void> = [];

  constructor(opts: GestureRouterOptions) {
    this.state = opts.state;
  }

  /**
   * Wire the Cytoscape-side gestures (tap → LOD; dbltap → enter edit).
   *
   * Behavior contract (PIG INTERACTION.GESTURES):
   *   - Tap on a leaf or collapsed-compound stand-in toggles LOD lean ⇆ full.
   *   - Tap on an uncollapsed compound parent is ignored (cue handles compound state).
   *   - Tap on a node currently in edit mode is ignored.
   *   - Dbltap on any node body enters edit mode for that node. If the node is
   *     lean, LOD is promoted to full first; edit mode entry is deferred to the
   *     next render frame so the overlay card has time to mount.
   *
   * The 350ms tap-suppression window from prior waves is removed. Cytoscape
   * fires `dbltap` BEFORE the trailing synthetic `tap` events, so we set
   * `state.editingUid` in dbltap and the tap handler checks it explicitly.
   */
  wireCytoscapeGestures(deps: CytoscapeGestureDeps): void {
    const { cy, overlayLayer, lookupNode, onLodChange } = deps;
    const state = this.state;

    const onTap = (evt: cytoscape.EventObject): void => {
      const node = evt.target as cytoscape.NodeSingular;
      const uid = node.id();

      // Suppress if this node is in edit mode (dbltap fires first and stamps
      // state.editingUid before the synthetic taps arrive).
      if (state.editingUid === uid) {
        trace({ src: 'router', kind: 'tap', data: { uid, suppressed: true, suppressionReason: 'editingThisNode' } });
        return;
      }

      // Belt-and-suspenders: also check if the overlay layer thinks any node
      // is editing (covers the case where state and overlay disagree mid-tear-down).
      if (overlayLayer.isEditingNode(uid)) {
        trace({ src: 'router', kind: 'tap', data: { uid, suppressed: true, suppressionReason: 'editingThisNode' } });
        return;
      }

      // Ignore taps that originate from contenteditable / .ig-editing DOM —
      // those are field-internal and must not bubble to LOD toggle.
      const originalEvent = evt.originalEvent as MouseEvent | undefined;
      if (originalEvent) {
        const target = originalEvent.target as Element | null;
        if (target?.classList.contains('ig-editing')) {
          trace({ src: 'router', kind: 'tap', data: { uid, suppressed: true, suppressionReason: 'igEditingClass' } });
          return;
        }
      }

      // Skip uncollapsed compound parents — they're containers; the cue handles
      // expand/collapse. Collapsed compounds (the library's stand-in nodes after
      // collapse) ARE tappable as the user-visible node, so we fall through.
      if (node.isParent() && !node.hasClass('cy-expand-collapse-collapsed-node')) {
        trace({ src: 'router', kind: 'tap', data: { uid, suppressed: true, suppressionReason: 'uncollapsedCompound' } });
        return;
      }

      const cur = (node.data('lod') as NodeLOD | undefined) ?? 'lean';
      const next: NodeLOD = cur === 'lean' ? 'full' : 'lean';

      // Trace the tap (not suppressed).
      trace({ src: 'router', kind: 'tap', data: { uid, suppressed: false, suppressionReason: null } });

      cy.batch(() => {
        node.data('lod', next);
      });

      // Update authoritative state and overlay.
      const intentNode = lookupNode(uid);
      if (next === 'full') {
        state.nodeLOD.set(uid, 'full');
        if (intentNode) {
          // Bug 2 instrumentation: capture the name lookupNode returned, so the
          // trace shows whether re-promoting to full reads stale or fresh state.
          trace({
            src: 'router',
            kind: 'lodPromoteContent',
            data: {
              uid,
              lookupName: intentNode.name,
              cyName: node.data('name')
            }
          });
          overlayLayer.show(uid, buildOverlayContent(intentNode));
        }
      } else {
        state.nodeLOD.delete(uid);
        overlayLayer.hide(uid);
      }

      // Trace the LOD transition.
      trace({ src: 'router', kind: 'lodToggle', data: { uid, from: cur, to: next } });

      onLodChange?.(uid, next);
    };

    const onDbltap = (evt: cytoscape.EventObject): void => {
      const node = evt.target as cytoscape.NodeSingular;
      const uid = node.id();

      // Skip uncollapsed compound parents (consistent with tap behavior).
      if (node.isParent() && !node.hasClass('cy-expand-collapse-collapsed-node')) return;

      const cur = (node.data('lod') as NodeLOD | undefined) ?? 'lean';
      const action = cur === 'full' ? 'enterEditFull' : 'promoteThenEdit';

      // Generate a correlation id that ties dbltap → editEnter → pointerdown together.
      const c = makeCorr();
      trace({ src: 'router', kind: 'dbltap', corr: c, data: { uid, currentLod: cur, action } });

      // Mark editing uid IMMEDIATELY so the trailing synthetic tap events
      // skip the LOD toggle for this node. (Cytoscape fires dbltap before
      // those taps, so this is race-safe.)
      state.editingUid = uid;

      const enterEdit = (): void => {
        const ok = overlayLayer.enterNodeEditMode(uid, c);
        if (!ok) {
          // Overlay rejected entry (no card, no callback, etc.) — clear the
          // edit flag so future taps work.
          state.editingUid = null;
          return;
        }

        // Animate camera to centre the node (250 ms, no relayout).
        try {
          (cy as unknown as { animate: (opts: unknown) => void }).animate({
            fit: { eles: node, padding: 80 },
            duration: 250,
            easing: 'ease-in-out-quad'
          });
        } catch {
          try {
            cy.center(node);
          } catch {
            /* ignore */
          }
        }
      };

      if (cur === 'full') {
        // Already full → enter edit immediately.
        enterEdit();
      } else {
        // Lean → promote to full first, then enter edit on the next frame so
        // the overlay card has been mounted by tickAll.
        const intentNode = lookupNode(uid);
        cy.batch(() => {
          node.data('lod', 'full');
        });
        state.nodeLOD.set(uid, 'full');
        if (intentNode) {
          overlayLayer.show(uid, buildOverlayContent(intentNode));
        }
        onLodChange?.(uid, 'full');

        // Defer edit entry one animation frame so the overlay tick can
        // attach contenteditable handlers.
        requestAnimationFrame(enterEdit);
      }
    };

    cy.on('tap', 'node', onTap);
    cy.on('dbltap', 'node', onDbltap);
    this.disposers.push(() => cy.off('tap', 'node', onTap));
    this.disposers.push(() => cy.off('dbltap', 'node', onDbltap));
  }

  /**
   * Wire the document-level edit-mode exit handlers (PIG EDITING.EXIT).
   * One pointerdown listener for outside-click commit; one keydown
   * listener for Escape cancel.
   *
   * Idempotent within a single router lifetime: calling twice attaches twice.
   * Callers should call this exactly once per router instance (after the
   * first cy mount).
   */
  wireDocumentGestures(deps: DocumentGestureDeps): void {
    const { overlayLayer, isLensSelectorTarget } = deps;
    const state = this.state;

    const onPointerDown = (event: PointerEvent): void => {
      if (state.editingUid === null) return;
      const editingCard = overlayLayer.getEditingCard();
      const targetInCard = editingCard !== null &&
        event.target instanceof Node && editingCard.contains(event.target);
      const targetInChrome = isLensSelectorTarget?.(event.target) ?? false;
      const shouldCommit = shouldCommitOnPointerDown({
        editingCard,
        target: event.target,
        isChromeTarget: isLensSelectorTarget
      });
      const commitDecision = shouldCommit ? 'commit' : 'keepEditing';

      // CRITICAL diagnostic: pointerdown with commitDecision='commit' immediately
      // after a dbltap is the signature of bug-2 (edit mode randomly closes).
      trace({
        src: 'router',
        kind: 'pointerdown',
        data: {
          editingUid: state.editingUid,
          targetInCard,
          targetInChrome,
          commitDecision
        }
      });

      if (!shouldCommit) return;

      const uid = state.editingUid;
      // Reset router-side state immediately so trailing taps on the canvas
      // do not double-fire the LOD toggle suppression.
      state.editingUid = null;
      // Fire the commit; overlay layer manages pendingEdits + DOM rollback.
      void overlayLayer.commitNodeEdit(uid);
    };

    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key !== 'Escape') return;
      if (state.editingUid === null) return;
      const uid = state.editingUid;
      trace({ src: 'router', kind: 'escape', data: { editingUid: uid } });
      state.editingUid = null;
      overlayLayer.cancelNodeEdit(uid);
    };

    document.addEventListener('pointerdown', onPointerDown, /* capture */ true);
    document.addEventListener('keydown', onKeyDown);
    this.disposers.push(() =>
      document.removeEventListener('pointerdown', onPointerDown, /* capture */ true)
    );
    this.disposers.push(() => document.removeEventListener('keydown', onKeyDown));
  }

  /**
   * Wire drag-persistence (PIG INTERACTION.DRAG).
   *
   * Behavior contract:
   *   - Drag is suppressed while ANY node is in edit mode (state.editingUid !== null).
   *   - On grab: capture the node's center position so wasActualDrag can
   *     distinguish a click-without-move from a real drag (Bug B fix).
   *   - On free: skip if not an actual drag (movement < 1 px).
   *   - Snap-back if release position is outside the parent compound's bbox
   *     (with a 20 px margin); do not persist out-of-bounds positions.
   *   - Otherwise call sendPersistPosition with the active lens; the host
   *     handles debounce + autocreate.
   */
  wireDragGestures(deps: DragGestureDeps): void {
    const { cy, getActiveLens, sendPersistPosition } = deps;
    const state = this.state;

    const onGrab = (evt: cytoscape.EventObject): void => {
      const node = evt.target as cytoscape.NodeSingular;
      const pos = node.position();
      const uid = node.id();
      state.grabPosition.set(uid, { x: pos.x, y: pos.y });
      trace({
        src: 'router',
        kind: 'grab',
        data: { uid, pos: { x: pos.x, y: pos.y }, suppressedByEdit: state.editingUid !== null }
      });
    };

    const onFree = (evt: cytoscape.EventObject): void => {
      const node = evt.target as cytoscape.NodeSingular;
      const uid = node.id();

      // Edit-mode suppression: ANY node editing → no drag-persist anywhere.
      // (Stronger than the prior heuristic because the router knows globally.)
      if (state.editingUid !== null) {
        // Still clear any captured grab position so it doesn't linger.
        state.grabPosition.delete(uid);
        return;
      }

      const startPos = state.grabPosition.get(uid);
      state.grabPosition.delete(uid);

      const pos = node.position();
      const position: Position = { x: pos.x, y: pos.y };

      // Click-without-move guard (sub-pixel jitter tolerance: 1 px).
      const isDrag = wasActualDrag(startPos, position);
      if (!isDrag) {
        trace({ src: 'router', kind: 'free', data: { uid, startPos, endPos: position, wasActualDrag: false, snappedBack: false, persisted: false } });
        return;
      }

      // Snap-back if outside parent compound rect.
      const parent = node.parent();
      if (parent && parent.nonempty()) {
        const bbox = parent.boundingBox();
        const margin = 20;
        const clipped: Position = {
          x: Math.max(bbox.x1 + margin, Math.min(bbox.x2 - margin, position.x)),
          y: Math.max(bbox.y1 + margin, Math.min(bbox.y2 - margin, position.y))
        };
        if (clipped.x !== position.x || clipped.y !== position.y) {
          cy.batch(() => {
            node.position(clipped);
          });
          trace({ src: 'router', kind: 'free', data: { uid, startPos, endPos: position, wasActualDrag: true, snappedBack: true, persisted: false } });
          return;
        }
      }

      // PIG LENSSCHEMA.NODESHAPE (Path Y, 2026-05-01): positions are stored
      // ABSOLUTE in cytoscape's global frame. Parent-following behaviour is
      // realised by cytoscape's compound auto-fit, not by a relative coord
      // frame. See PIG node design notes for the full rationale.
      const lensName = getActiveLens();
      trace({
        src: 'router',
        kind: 'free',
        data: {
          uid,
          startPos,
          endPos: position,
          wasActualDrag: true,
          snappedBack: false,
          persisted: true
        }
      });
      sendPersistPosition(uid, position, lensName);
    };

    cy.on('grab', 'node', onGrab);
    cy.on('free', 'node', onFree);
    this.disposers.push(() => cy.off('grab', 'node', onGrab));
    this.disposers.push(() => cy.off('free', 'node', onFree));
  }

  /** Detach every listener. Idempotent. */
  dispose(): void {
    while (this.disposers.length > 0) {
      const fn = this.disposers.pop();
      if (fn) {
        try {
          fn();
        } catch {
          /* ignore */
        }
      }
    }
  }

  /**
   * Read-only view of the current gesture state.
   * Exposed for the cue layer + overlay layer + tests.
   */
  getState(): Readonly<GestureState> {
    return this.state;
  }

  /**
   * Programmatic mode-exit hook used when a reload tears down the overlay
   * (the panel must reset editingUid so the next mount starts clean).
   */
  resetEditingUid(): void {
    this.state.editingUid = null;
  }
}

