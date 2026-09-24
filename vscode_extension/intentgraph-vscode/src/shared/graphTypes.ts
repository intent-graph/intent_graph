// Type contracts shared by extension host and webview.
// Imported by both bundles; esbuild emits a copy into each.
// SerialisedLensConfig mirrors Python LensConfig shape.

/** Opaque UID. PRIMER_01 §UID Format. */
export type Uid = string;

/**
 * 2D position in Cytoscape node-center coordinates (parent-relative frame).
 * Mirrors Python Position type (Lens Positions MVP).
 * Spec: LENS_REDESIGN_SPEC.md §4.1 (Position Semantics).
 */
export interface Position {
  x: number;
  y: number;
}

/**
 * Lens entry for a single node: LOD + optional position.
 * Extends LOD-only model to include position persistence.
 * Spec: LENS_REDESIGN_SPEC.md §4 (LensNodeEntry).
 * Constraint: position is optional; omitted in YAML when undefined.
 */
export interface LensNodeEntry {
  lod: 'skeleton' | 'lean' | 'full';
  position?: Position;
}

/**
 * Wire-safe mirror of the Python LensConfig shape (models/lens_config.py).
 * Serialised as a top-level `lenses:` dict entry in every IG file.
 * nodes map updated to LensNodeEntry (includes optional position).
 */
export interface SerialisedLensConfig {
  /** Display name; matches the dict key it lives under (kept for self-documentation). */
  name: string;
  description?: string;
  /** UIDs that were the "focus" when this lens was created. Optional, informational. */
  target_uids?: string[];
  /** Map from UID to LensNodeEntry (lod + optional position). */
  nodes: Record<Uid, LensNodeEntry>;
  /** Intentlink UIDs explicitly included in this lens view. */
  intentlinks?: string[];
}

export type EdgeType = 'dataflow' | 'requires' | 'conflicts' | 'refines' | 'unspecified';

/** Per-node level-of-detail. `lean` = name only; `full` = name + intent + epistemic + 3 constraints. */
export type NodeLOD = 'lean' | 'full';

export interface IntentNode {
  uid: Uid;
  name: string;
  /** Full intent prose. Populated by loadGraph for every node (no lazy fetch). */
  intent?: string;
  epistemic_state?: string;
  constraints?: string[];
  /** Free-form badge (e.g. "intent:218 constraints:4"). */
  badge?: string;
}

export interface IntentLink {
  uid: Uid;
  src: Uid;
  dst: Uid;
  intent?: string;
  edgeType: EdgeType;
}

export interface Treearc {
  parent: Uid;
  child: Uid;
}

/** In-memory graph model. Maps for indices; serialise as POJOs across the messenger boundary. */
export interface IntentGraphModel {
  graphName: string;
  rootUid: Uid;
  nodes: Map<Uid, IntentNode>;
  links: IntentLink[];
  tree: Treearc[];
  childrenOf: Map<Uid, Uid[]>;
  parentOf: Map<Uid, Uid | null>;
  depthOf: Map<Uid, number>;
  /** Non-fatal warnings surfaced to the webview banner (§3.6 M2). */
  warnings?: string[];
}

/**
 * Wire-format mirror of IntentGraphModel: arrays/POJOs in place of Maps so it
 * round-trips through structured-clone without surprises.
 */
export interface SerialisedIntentGraphModel {
  graphName: string;
  rootUid: Uid;
  nodes: Record<Uid, IntentNode>;
  links: IntentLink[];
  tree: Treearc[];
  childrenOf: Record<Uid, Uid[]>;
  parentOf: Record<Uid, Uid | null>;
  depthOf: Record<Uid, number>;
  warnings?: string[];
}

export function rehydrateModel(serial: SerialisedIntentGraphModel): IntentGraphModel {
  return {
    graphName: serial.graphName,
    rootUid: serial.rootUid,
    nodes: new Map(Object.entries(serial.nodes)),
    links: serial.links,
    tree: serial.tree,
    childrenOf: new Map(Object.entries(serial.childrenOf)),
    parentOf: new Map(Object.entries(serial.parentOf)),
    depthOf: new Map(Object.entries(serial.depthOf)),
    warnings: serial.warnings
  };
}

export function serialiseModel(model: IntentGraphModel): SerialisedIntentGraphModel {
  const obj = <V,>(m: Map<string, V>): Record<string, V> => {
    const out: Record<string, V> = {};
    for (const [k, v] of m) out[k] = v;
    return out;
  };
  return {
    graphName: model.graphName,
    rootUid: model.rootUid,
    nodes: obj(model.nodes),
    links: model.links,
    tree: model.tree,
    childrenOf: obj(model.childrenOf),
    parentOf: obj(model.parentOf),
    depthOf: obj(model.depthOf),
    warnings: model.warnings
  };
}

/**
 * Compose the multi-line label string for a node's `full` LOD view.
 * Cytoscape renders one label per node — we encode lines as `\n` and rely on
 * `text-wrap: 'wrap'` to honour hard breaks AND wrap long lines.
 *
 * @deprecated Full-LOD rendering moved to DOM overlays
 * (htmlOverlayLayer.ts). This function is no longer used for canvas labels
 * (the `node[lod = "full"]` selector now sets `label: ''`). Retained because
 * the metadata-reload branch in main.ts still calls it; will be removed once
 * that branch is fully updated to use overlayLayer.refreshContent().
 */
export function composeFullLabel(node: IntentNode): string {
  const lines: string[] = [node.name];
  if (node.intent) {
    lines.push('', node.intent);
  }
  if (node.epistemic_state) {
    lines.push('', `[${node.epistemic_state}]`);
  }
  if (node.constraints && node.constraints.length > 0) {
    lines.push('');
    for (const c of node.constraints.slice(0, 3)) {
      lines.push(`• ${c}`);
    }
    if (node.constraints.length > 3) {
      lines.push(`… +${node.constraints.length - 3} more`);
    }
  }
  return lines.join('\n');
}
