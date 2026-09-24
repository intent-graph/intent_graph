// ELK JSON build + layout + flatten to absolute leaf positions.
// Builds the ELK layout options and flattens the result to leaf positions.

import ELK from 'elkjs/lib/elk.bundled.js';

import type { IntentGraphModel, Uid } from '../shared/graphTypes';

// Locked option set — do not change without re-verifying layout stability.
const ROOT_LAYOUT_OPTIONS: Record<string, string> = {
  'elk.algorithm': 'layered',
  'elk.direction': 'DOWN',
  'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
  'elk.edgeRouting': 'ORTHOGONAL',
  'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.layered.layering.strategy': 'NETWORK_SIMPLEX',
  'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
  'elk.spacing.nodeNode': '40',
  'elk.layered.spacing.nodeNodeBetweenLayers': '60',
  'elk.spacing.edgeNode': '20',
  'elk.spacing.edgeEdge': '15',
  'elk.padding': '[top=20,left=20,bottom=20,right=20]'
};

// Per-compound stamp to defeat elkjs#326 spacing default.
const COMPOUND_LAYOUT_OPTIONS: Record<string, string> = {
  'elk.padding': '[top=24,left=20,bottom=20,right=20]',
  'elk.spacing.nodeNode': '40'
};

export const LEAF_WIDTH = 160;
export const LEAF_HEIGHT = 60;
/** Cytoscape node width for full-LOD nodes (1.5× LEAF_WIDTH = 240). Set via style selector;
 *  applied post-layout so neighbouring nodes may overlap — accepted trade-off under
 *  the "no relayout" rule. htmlOverlayLayer.ts uses this as the overlay reference width.
 *  UX Rework: user-requested 1.5× wide relative to the pre-Amend-4 value (160 → 240).
 *  Previously 320 (2× from Amend 4) — reverted down to 240 per user feedback. */
export const FULL_LOD_WIDTH = 240;
/** Cytoscape node height for full-LOD nodes (1.5× LEAF_HEIGHT_BASE = 180). Set via style selector;
 *  applied post-layout so neighbouring nodes may overlap — accepted trade-off under
 *  the "no relayout" rule. htmlOverlayLayer.ts uses this as the overlay reference height.
 *  UX Rework: user-requested 1.5× tall relative to the pre-Amend-4 value (120 → 180).
 *  Previously 360 (3× from Amend 4) — reverted down to 180 per user feedback. */
export const FULL_LOD_HEIGHT = 180;

// Minimal ELK shape — `elkjs` types are loose, so we use local interfaces.
export interface ElkLabel {
  text: string;
  width?: number;
  height?: number;
}
export interface ElkEdge {
  id: string;
  sources: string[];
  targets: string[];
  data?: Record<string, unknown>;
  // ELK populates `sections` with bend points after layout.
  sections?: unknown;
}
export interface ElkNode {
  id: string;
  width?: number;
  height?: number;
  x?: number;
  y?: number;
  labels?: ElkLabel[];
  layoutOptions?: Record<string, string>;
  children?: ElkNode[];
  edges?: ElkEdge[];
  data?: Record<string, unknown>;
}

export interface PositionedGraph extends ElkNode {
  /** Layout phase timings as reported by elkjs when measureExecutionTime is true. */
  measured?: unknown;
}

function buildElkNode(uid: Uid, model: IntentGraphModel): ElkNode {
  const node = model.nodes.get(uid);
  const name = node?.name ?? uid;
  const children = model.childrenOf.get(uid) ?? [];
  const isCompound = children.length > 0;

  const labels: ElkLabel[] = [{ text: name, width: 150, height: 20 }];

  if (isCompound) {
    return {
      id: uid,
      labels,
      layoutOptions: { ...COMPOUND_LAYOUT_OPTIONS },
      children: children.map((c) => buildElkNode(c, model))
    };
  }
  return {
    id: uid,
    width: LEAF_WIDTH,
    height: LEAF_HEIGHT,
    labels
  };
}

export function buildElkJson(model: IntentGraphModel): ElkNode {
  // Root holds intentlinks as edges; ELK reassigns containment by LCA.
  const rootChildren = (model.childrenOf.get(model.rootUid) ?? []).map((c) => buildElkNode(c, model));
  // M2 (§3.6): include orphan nodes as additional root-level children
  // so they actually render. An orphan is a node !== rootUid with parentOf === null.
  const orphanUids = Array.from(model.nodes.keys()).filter(
    (uid) => uid !== model.rootUid && model.parentOf.get(uid) === null
  );
  const orphanChildren = orphanUids.map((uid) => buildElkNode(uid, model));

  const rootNode = model.nodes.get(model.rootUid);
  const rootLabels: ElkLabel[] = rootNode
    ? [{ text: rootNode.name ?? model.rootUid, width: 150, height: 20 }]
    : [];

  const edges: ElkEdge[] = model.links.map((l) => ({
    id: l.uid,
    sources: [l.src],
    targets: [l.dst],
    data: { edgeType: l.edgeType }
  }));

  return {
    id: model.rootUid,
    labels: rootLabels,
    layoutOptions: { ...ROOT_LAYOUT_OPTIONS, ...COMPOUND_LAYOUT_OPTIONS },
    children: [...rootChildren, ...orphanChildren],
    edges
  };
}

const elk = new ELK();

export async function runLayout(elkJson: ElkNode): Promise<PositionedGraph> {
  // measureExecutionTime requested for phase logging.
  // Cast: elkjs's d.ts uses its own ElkNode shape; ours is structurally compatible.
  const positioned = (await elk.layout(elkJson as unknown as never, {
    layoutOptions: { 'elk.measureExecutionTime': 'true' }
  } as unknown as never)) as unknown as PositionedGraph;
  return positioned;
}

/**
 * Recurse the laid-out graph and accumulate absolute leaf positions.
 * ELK returns positions relative to the parent compound; Cytoscape positions
 * its leaves by absolute centre coordinates (compound parents auto-fit).
 * Pointers §2.5 step 4.
 */
export function flattenAbsolutePositions(
  positioned: ElkNode,
  offsetX = 0,
  offsetY = 0,
  out: Map<string, { x: number; y: number }> = new Map()
): Map<string, { x: number; y: number }> {
  for (const child of positioned.children ?? []) {
    const ax = offsetX + (child.x ?? 0);
    const ay = offsetY + (child.y ?? 0);
    const isLeaf = !child.children || child.children.length === 0;
    if (isLeaf) {
      out.set(child.id, {
        x: ax + (child.width ?? LEAF_WIDTH) / 2,
        y: ay + (child.height ?? LEAF_HEIGHT) / 2
      });
    }
    flattenAbsolutePositions(child, ax, ay, out);
  }
  return out;
}
