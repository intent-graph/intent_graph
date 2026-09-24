// Cytoscape mount: build elements from the IntentGraphModel + ELK leaf
// positions, register expand-collapse / navigator, set initial collapse set.
// Covers expand-collapse and navigator wiring, plus LOD on node data
// (tippy/popper deleted).

import cytoscape from 'cytoscape';
// No d.ts shipped for these two; cast through `unknown` so we don't @ts-ignore.
import expandCollapse from 'cytoscape-expand-collapse';
import navigator from 'cytoscape-navigator';

import { type IntentGraphModel, type NodeLOD, type Uid } from '../shared/graphTypes';
import { HtmlOverlayLayer, type NodeEditCommitCallback } from './overlay/htmlOverlayLayer';
import { cyStyles } from './styles/cyStyle';

// PIG INTERACTION.GESTURES — wheel-zoom sensitivity and horizontal pan scale.
// From data_registry.timings in the PIG.
const WHEEL_SENSITIVITY = 0.2;
const HORIZONTAL_PAN_SCALE = 1.0;

// Module-init plugin registration. Idempotent — cytoscape.use ignores duplicates.
let pluginsRegistered = false;
function registerPlugins(): void {
  if (pluginsRegistered) return;
  cytoscape.use(expandCollapse as unknown as cytoscape.Ext);
  cytoscape.use(navigator as unknown as cytoscape.Ext);
  pluginsRegistered = true;
}

// expand-collapse API (no d.ts; sketch only the methods we call).
export interface ExpandCollapseApi {
  collapseRecursively(eles: cytoscape.Collection): void;
  expandRecursively(eles: cytoscape.Collection): void;
  collapse(eles: cytoscape.Collection): void;
  expand(eles: cytoscape.Collection): void;
  isCollapsible(node: cytoscape.NodeSingular): boolean;
  isExpandable(node: cytoscape.NodeSingular): boolean;
}

interface CyWithExpandCollapse extends cytoscape.Core {
  expandCollapse(opts: Record<string, unknown>): ExpandCollapseApi;
}

export interface CyHandle {
  cy: cytoscape.Core;
  ec: ExpandCollapseApi;
  nav: { destroy: () => void };
  overlayLayer: HtmlOverlayLayer;
  dispose: () => void;
}

/** Whether an epistemic-state string denotes a "risk" (drives the orange risk border
 *  via the `epistemicRisk` node-data flag; see cyStyle.ts `node[?epistemicRisk]`).
 *  Exported so the post-edit local mirror (main.ts applyLocalEditSync) can recompute
 *  the flag live without duplicating the predicate. */
export function isRiskState(state: string | undefined): boolean {
  if (!state) return false;
  const lower = state.toLowerCase();
  return lower.startsWith('risky') || lower.startsWith('speculative') || lower.startsWith('undecided');
}

function buildElements(
  model: IntentGraphModel,
  positions: Map<Uid, { x: number; y: number }>,
  initialLOD: Map<Uid, NodeLOD>
): cytoscape.ElementDefinition[] {
  const elements: cytoscape.ElementDefinition[] = [];

  for (const [uid, node] of model.nodes) {
    const parent = model.parentOf.get(uid) ?? undefined;
    const lod: NodeLOD = initialLOD.get(uid) ?? 'lean';
    // `fullLabel` no longer set on canvas node data —
    // the DOM overlay (htmlOverlayLayer.ts) is the sole renderer for full-LOD nodes.
    const data: Record<string, unknown> = {
      id: uid,
      name: node.name,
      epistemicRisk: isRiskState(node.epistemic_state) ? 1 : 0,
      lod
    };
    if (parent) data.parent = parent;

    const def: cytoscape.ElementDefinition = { group: 'nodes', data };
    const pos = positions.get(uid);
    if (pos) def.position = { x: pos.x, y: pos.y };
    elements.push(def);
  }

  for (const link of model.links) {
    if (!model.nodes.has(link.src) || !model.nodes.has(link.dst)) continue;
    elements.push({
      group: 'edges',
      data: {
        id: link.uid,
        source: link.src,
        target: link.dst,
        edgeType: link.edgeType
      }
    });
  }
  return elements;
}

export function mount(
  model: IntentGraphModel,
  positions: Map<Uid, { x: number; y: number }>,
  container: HTMLElement,
  navContainer: HTMLElement,
  overlayContainer: HTMLElement,
  initialLOD: Map<Uid, NodeLOD> = new Map(),
  onNodeEditCommit?: NodeEditCommitCallback
): CyHandle {
  registerPlugins();

  const cy = cytoscape({
    container,
    elements: [],
    style: cyStyles,
    // Performance settings.
    // PIG INTERACTION.GESTURES: calm wheel-zoom using WHEEL_SENSITIVITY (0.2).
    // Default Cytoscape wheelSensitivity=1.0 is too aggressive for most hardware.
    wheelSensitivity: WHEEL_SENSITIVITY,
    hideEdgesOnViewport: true,
    textureOnViewport: true,
    pixelRatio: 1.0,
    motionBlur: false,
    layout: { name: 'preset' }
  });

  const elements = buildElements(model, positions, initialLOD);
  cy.batch(() => {
    cy.add(elements);
    // Re-apply leaf positions explicitly (compound parents auto-fit;
    // never call .position() on a parent).
    for (const [uid, pos] of positions) {
      const ele = cy.getElementById(uid);
      if (ele.nonempty() && !ele.isParent()) {
        ele.position(pos);
      }
    }
  });

  // PIG INTERACTION.GESTURES: side-wheel deltaX pans viewport horizontally.
  // Add wheel listener on the container to intercept horizontal scroll events.
  container.addEventListener(
    'wheel',
    (event: WheelEvent) => {
      // Skip if pinch-zoom (Cytoscape's native handler will take it).
      if (event.ctrlKey) return;
      // Skip if no horizontal component.
      if (event.deltaX === 0) return;
      // Pan viewport by negating deltaX (scroll-right pans content left).
      cy.panBy({ x: -event.deltaX * HORIZONTAL_PAN_SCALE, y: 0 });
    },
    { passive: true }
  );

  const ec = (cy as CyWithExpandCollapse).expandCollapse({
    // PIG LAYOUT.CUES + INV-9: library cue disabled; DOM cue buttons tracked by
    // CueLayer (src/webview/overlay/cueLayer.ts) are the EXCLUSIVE affordance
    // for expand/collapse. The library API methods (expand, collapse, isCollapsible,
    // isExpandable) remain usable via `ec`; only the library's canvas-drawn cue
    // and tap handler are off.
    cueEnabled: false,
    expandCollapseCuePosition: 'top-left',
    expandCollapseCueSize: 12,
    expandCollapseCueLineSize: 8,
    layoutBy: null,
    undoable: false,
    animate: 'end',
    fisheye: false,
    edgeTypeInfo: 'edgeType',
    groupEdgesOfSameTypeOnCollapse: true
  });

  // Initial collapse disabled. The depth>=2 heuristic over-collapses
  // for graphs whose meaningful structure lives at L1-L2 (e.g. python_defaults.ig.yaml,
  // 75 nodes / 4 L1 modules) — every visible compound ends up with no visible children
  // and Cytoscape stacks them at one point. Show the full ELK layout; user can
  // collapse manually.
  void ec; // ec retained for click-to-collapse handlers.

  // cytoscape-navigator expects a CSS selector string,
  // not an HTMLElement. Derive from the navContainer's id (set in index.html.ts).
  // `removeCustomContainer: false` keeps the #cy-navigator div in the DOM on
  // destroy() so subsequent reloads can re-mount; default true wipes it and
  // breaks the structural-reload path.
  const navSelector = navContainer.id ? `#${navContainer.id}` : '#cy-navigator';
  const nav = cy.navigator({
    container: navSelector,
    removeCustomContainer: false
  });

  cy.fit(undefined, 40);

  // Create the HTML overlay layer for full-LOD nodes.
  // Pass onNodeEditCommit callback for whole-node edit affordance.
  // Cue rendering moved to a separate CueLayer constructed by main.ts.
  const overlayLayer = new HtmlOverlayLayer(cy, overlayContainer, onNodeEditCommit);

  const dispose = (): void => {
    // teardown() must be called while cy is still alive (viewport listener detach).
    try {
      overlayLayer.teardown();
    } catch {
      /* ignore */
    }
    try {
      nav.destroy();
    } catch {
      /* ignore */
    }
    try {
      cy.destroy();
    } catch {
      /* ignore */
    }
  };

  return { cy, ec, nav, overlayLayer, dispose };
}

/**
 * Pure-logic helper for horizontal pan via deltaX.
 * PIG INTERACTION.GESTURES: "Side-wheel deltaX pans viewport horizontally"
 *
 * @param event Wheel event (or event-like object with deltaX, deltaY, ctrlKey)
 * @returns { x, y } pan spec if action should be taken, null if should be skipped
 */
export function decideHorizontalPan(event: {
  deltaX: number;
  deltaY?: number;
  ctrlKey?: boolean;
}): { x: number; y: number } | null {
  // Skip pinch-zoom (Cytoscape's native handler will manage it).
  if (event.ctrlKey) return null;
  // Skip if no horizontal component.
  if (event.deltaX === 0) return null;
  // Return pan spec: negate deltaX so scroll-right pans content left.
  return { x: -event.deltaX * HORIZONTAL_PAN_SCALE, y: 0 };
}

// Tap (LOD toggle) and dbltap (enter edit) handlers were migrated to
// src/webview/interaction/gestureRouter.ts. The 350ms
// timing-based dbltap suppression window has been replaced by an explicit
// state-based guard (state.editingUid). Dbltap on a lean node now promotes
// to full and enters edit in one coherent action.

// Drag persistence (grab → free) and the wasActualDrag helper
// have moved to src/webview/interaction/gestureRouter.ts. Edit-mode suppression
// now reads state.editingUid (any node editing → all drags suppressed) instead
// of a getMode() heuristic on App's uiPhase.
