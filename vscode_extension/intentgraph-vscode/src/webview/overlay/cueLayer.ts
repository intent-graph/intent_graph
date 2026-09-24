// Cue layer — owns one DOM <button> per compound node (lean OR full), positioned
// at the bottom-left of the node's rendered bounding box on every render frame.
//
// PIG LAYOUT.CUES:
//   - A single neutral cue (one icon, no separate +/-) is present at bottom-left
//     of every compound node.
//   - The cue is visible in lean LOD and full LOD (independent of overlay layer).
//   - The cue is hidden only while the node is in edit mode (state.editingUid === uid).
//   - Cue visibility does not depend on selection, hover, drag state, or focus.
//   - Clicking the cue is the only event that toggles the compound's collapsed/expanded
//     state. Wired through the gesture router so all compound transitions go through
//     a single dispatch path (PIG INTERACTION.ROUTER, INVARIANTS INV-9).
//
// Why a separate layer (not part of htmlOverlayLayer)?
//   The overlay layer renders full-LOD cards only — it has no business creating DOM
//   per compound, and its `tickCue` was only firing for compounds that happened to
//   be tracked by the overlay map. The user-reported "no +/- in sight" complaint was
//   exactly this: lean compounds had no cue rendered. Splitting concerns guarantees
//   the cue is rendered for every compound regardless of LOD.
//
// Why a separate render listener?
//   We attach our own cy.on('render') so that cue position updates are decoupled
//   from overlay tickAll. Both fire on the same render frame; ordering is irrelevant
//   because each writes to its own set of DOM elements.

import type cytoscape from 'cytoscape';

import type { Uid } from '../../shared/graphTypes';
import type { GestureState } from '../interaction/state';
import { trace, corr as makeCorr } from '../trace';
import { ecExpand, ecCollapse } from './ecWrap';

/**
 * Neutral toggle cue SVG (single icon, no +/- distinction per PIG LAYOUT.CUES).
 * Outer circle + intersecting horizontal+vertical lines. URL-encoded data URI;
 * SVG renders white-on-dark and is readable at 20×20 px on both light/dark themes.
 * Single quotes are %27-encoded to keep the data URL parseable in CSS contexts.
 */
const NEUTRAL_CUE_SVG =
  'data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 20 20%27%3E' +
  '%3Ccircle cx=%2710%27 cy=%2710%27 r=%279%27 fill=%27%23333%27 stroke=%27%23aaa%27 stroke-width=%271.5%27/%3E' +
  '%3Cline x1=%275%27 y1=%2710%27 x2=%2715%27 y2=%2710%27 stroke=%27%23eee%27 stroke-width=%272%27 stroke-linecap=%27round%27/%3E' +
  '%3Cline x1=%2710%27 y1=%275%27 x2=%2710%27 y2=%2715%27 stroke=%27%23eee%27 stroke-width=%272%27 stroke-linecap=%27round%27/%3E' +
  '%3C/svg%3E';

/** Pixel size of the cue button (matches .ig-compound-cue in styles.css). */
const CUE_SIZE = 20;
/** Pixel inset from the node edge so the cue doesn't sit on the border. */
const CUE_MARGIN = 4;
/**
 * Minimum screen-space height of a node before the cue hides. Below this, the
 * node is too small for the cue to be a usable click target. Mirrors
 * MIN_READABLE_HEIGHT in htmlOverlayLayer.
 */
const MIN_READABLE_HEIGHT = 50;

/**
 * Pure-logic predicate: should the cue be hidden for a given node state?
 * Exported for unit testing — no DOM dependencies.
 */
export function shouldHideCue(state: {
  /** Node still exists in cy and is visible. */
  nonempty: boolean;
  visible: boolean;
  /** Any ancestor has the collapsed class. */
  ancestorCollapsed: boolean;
  /** This uid is the currently-editing node. */
  editing: boolean;
  /** Node is partially or fully off the visible viewport. */
  offScreen: boolean;
  /** Node's screen-space height is below the minimum readable threshold. */
  belowMinHeight: boolean;
}): boolean {
  if (!state.nonempty) return true;
  if (!state.visible) return true;
  if (state.ancestorCollapsed) return true;
  if (state.editing) return true;
  if (state.offScreen) return true;
  if (state.belowMinHeight) return true;
  return false;
}

/**
 * Click action decided from the current compound state (collapsible vs expandable).
 * Returns null if the node is in neither state (shouldn't happen for a real cue,
 * but be defensive).
 */
export type CompoundAction = 'collapse' | 'expand' | null;

/**
 * Pure decision function for the cue's click action. Mirrors the runtime check
 * against the cytoscape-expand-collapse API. Exported for unit testing.
 */
export function decideCompoundAction(args: {
  isCollapsible: boolean;
  isExpandable: boolean;
}): CompoundAction {
  if (args.isCollapsible) return 'collapse';
  if (args.isExpandable) return 'expand';
  return null;
}

/**
 * Callback fired by the cue layer when the user clicks a cue. The layer has
 * already invoked the expand/collapse API; this callback exists for the App
 * to update its compound-state tracking (collapseSet add/remove).
 */
export type CueClickCallback = (uid: Uid, isNowCollapsed: boolean) => void;

/**
 * Minimal expand-collapse API shape we need. Matches `ExpandCollapseApi` in
 * cyMount.ts (the cytoscape-expand-collapse plugin's collapse/expand take a
 * Collection — we wrap a single node in cy.collection() at the call site).
 */
interface ExpandCollapseLike {
  isCollapsible(node: cytoscape.NodeSingular): boolean;
  isExpandable(node: cytoscape.NodeSingular): boolean;
  collapse(eles: cytoscape.Collection): void;
  expand(eles: cytoscape.Collection): void;
}

/**
 * Manages the lifecycle of cue buttons for every compound node in the graph.
 * One instance per Cytoscape mount; replaced on structural reload.
 */
export class CueLayer {
  private readonly cy: cytoscape.Core;
  private readonly root: HTMLElement;
  private readonly state: GestureState;
  private readonly ec: ExpandCollapseLike;
  private readonly onCueClick: CueClickCallback | null;
  private readonly cueMap = new Map<Uid, HTMLElement>();
  private readonly onRender: () => void;

  constructor(
    cy: cytoscape.Core,
    root: HTMLElement,
    state: GestureState,
    ec: ExpandCollapseLike,
    onCueClick?: CueClickCallback
  ) {
    this.cy = cy;
    this.root = root;
    this.state = state;
    this.ec = ec;
    this.onCueClick = onCueClick ?? null;

    this.onRender = (): void => {
      this.tickAll();
    };
    cy.on('render', this.onRender);
  }

  /**
   * Build cue buttons for every current compound node. Call once after the cy
   * elements have been added; call again on structural reload to re-sync with
   * the new compound topology.
   *
   * Idempotent: removes any prior buttons before recreating.
   */
  initCues(): void {
    for (const btn of this.cueMap.values()) {
      if (btn.parentNode) btn.parentNode.removeChild(btn);
    }
    this.cueMap.clear();

    // A "compound" for cue purposes is any node that EITHER currently has
    // children (`isParent()`) OR carries the collapsed-compound class (the
    // library's stand-in for a collapsed compound). Iterating once at init
    // catches every case the user can act on.
    this.cy.nodes().forEach((node) => {
      if (this.isCompound(node)) {
        const uid = node.id();
        const btn = this.createCueButton(uid);
        this.cueMap.set(uid, btn);
        this.root.appendChild(btn);
      }
    });

    // PIG OBSERVABILITY constraint #4: lifecycle marker with cardinality.
    trace({ src: 'cue', kind: 'cueLayerMounted', data: { compoundCount: this.cueMap.size } });
  }

  /** Detach the render listener and remove all DOM. Call from cyMount.dispose. */
  teardown(): void {
    try {
      this.cy.off('render', this.onRender);
    } catch {
      /* ignore — cy may already be destroyed */
    }
    for (const btn of this.cueMap.values()) {
      if (btn.parentNode) btn.parentNode.removeChild(btn);
    }
    this.cueMap.clear();
  }

  // ── Private helpers ────────────────────────────────────────────────────────

  private isCompound(node: cytoscape.NodeSingular): boolean {
    return node.isParent() || node.hasClass('cy-expand-collapse-collapsed-node');
  }

  private createCueButton(uid: Uid): HTMLElement {
    const btn = document.createElement('button');
    btn.className = 'ig-compound-cue';
    btn.setAttribute('aria-label', 'Toggle expand/collapse');
    btn.setAttribute('data-ig-compound-cue', uid);
    btn.type = 'button';

    const img = document.createElement('img');
    img.src = NEUTRAL_CUE_SVG;
    img.alt = '';
    img.setAttribute('aria-hidden', 'true');
    img.style.width = '100%';
    img.style.height = '100%';
    btn.appendChild(img);

    btn.addEventListener('click', (event: Event) => {
      // INV-9: stop the click from reaching Cytoscape's tap handlers.
      event.stopPropagation();
      this.handleClick(uid);
    });

    return btn;
  }

  /**
   * Handle a cue click: read the compound's current state from the API,
   * decide the action, fire it, and notify the App of the new collapse state.
   */
  private handleClick(uid: Uid): void {
    const node = this.cy.getElementById(uid);
    if (!node.nonempty()) return;

    const isCollapsible = this.ec.isCollapsible(node);
    const isExpandable = this.ec.isExpandable(node);

    const action = decideCompoundAction({ isCollapsible, isExpandable });

    // Generate a correlation id for this cue click so the resulting ecCall
    // entry references the same corr.
    const c = makeCorr();
    trace({ src: 'cue', kind: 'cueClick', corr: c, data: { uid, action, isCollapsible, isExpandable } });

    // The expand-collapse API takes a Collection; wrap the single node.
    const target = this.cy.collection().union(node) as unknown as cytoscape.Collection;
    if (action === 'collapse') {
      ecCollapse(this.ec, target, 'cueClick', 'cue', c);
      this.state.collapseSet.add(uid);
      this.onCueClick?.(uid, /*isNowCollapsed*/ true);
    } else if (action === 'expand') {
      ecExpand(this.ec, target, 'cueClick', 'cue', c);
      this.state.collapseSet.delete(uid);
      this.onCueClick?.(uid, /*isNowCollapsed*/ false);
    }
    // null action → no-op (defensive; not expected in practice).
  }

  private tickAll(): void {
    for (const [uid, btn] of this.cueMap) {
      this.tickOne(uid, btn);
    }
  }

  private tickOne(uid: Uid, btn: HTMLElement): void {
    const node = this.cy.getElementById(uid);

    const nonempty = node.nonempty();
    const visible = nonempty && node.visible();

    let ancestorCollapsed = false;
    if (nonempty) {
      for (const ancestor of node.ancestors().nodes()) {
        if (ancestor.hasClass('cy-expand-collapse-collapsed-node')) {
          ancestorCollapsed = true;
          break;
        }
      }
    }

    const editing = this.state.editingUid === uid;

    let offScreen = false;
    let belowMinHeight = false;
    let leftPx = 0;
    let topPx = 0;

    if (nonempty) {
      const rect = node.renderedBoundingBox({});
      const vpW = this.root.clientWidth;
      const vpH = this.root.clientHeight;
      offScreen = rect.x2 < 0 || rect.x1 > vpW || rect.y2 < 0 || rect.y1 > vpH;
      belowMinHeight = rect.h < MIN_READABLE_HEIGHT;
      leftPx = rect.x1 + CUE_MARGIN;
      topPx = rect.y2 - CUE_SIZE - CUE_MARGIN;
    }

    const hide = shouldHideCue({
      nonempty,
      visible,
      ancestorCollapsed,
      editing,
      offScreen,
      belowMinHeight
    });

    if (hide) {
      btn.style.display = 'none';
      return;
    }

    btn.style.display = 'flex';
    btn.style.left = `${leftPx}px`;
    btn.style.top = `${topPx}px`;
  }
}
