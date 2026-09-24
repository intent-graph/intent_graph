// Host-side graph loader: read the .ig.json|.ig.yaml file, parse via yaml@2.8
// (which handles JSON as a YAML superset), build the IntentGraphModel with
// indices, classify intentlinks, and return a serialisable POJO model.
// Host-side parse/load; see module header above for the decision rationale.
// Returns fileHash alongside the model (SHA-256 of raw content,
//   CRLF-normalised) so webview can use it in EditFieldRequest.
// Returns lenses dict and default_lens from parsed IG.

import { readFile } from 'fs/promises';
import * as path from 'path';
import { parse as yamlParse } from 'yaml';
import * as vscode from 'vscode';

import { computeFileHash } from '../host/fileHash';

import type {
  EdgeType,
  IntentGraphModel,
  IntentLink,
  IntentNode,
  SerialisedIntentGraphModel,
  SerialisedLensConfig,
  Treearc,
  Uid
} from '../shared/graphTypes';
import { serialiseModel } from '../shared/graphTypes';

interface RawNode {
  uid: string;
  name?: string;
  intent?: string;
  epistemic_state?: string;
  constraints?: string[];
}

interface RawTreearc {
  parent: string;
  child: string;
}

interface RawIntentLink {
  uid?: string;
  src: string;
  dst: string;
  intent?: string;
}

interface RawGraph {
  meta?: { name?: string; description?: string; default_lens?: string };
  nodes?: RawNode[];
  treearcs?: RawTreearc[];
  intentlinks?: RawIntentLink[];
  /** Internal lenses: map from name → LensConfig. */
  lenses?: Record<string, unknown>;
}

const DATAFLOW = ['produces', 'provides', 'feeds', 'consumed by', 'dataflow'];
const REQUIRES = ['requires', 'depends on', 'must exist', 'prerequisite'];
const CONFLICTS = ['conflicts', 'mutually exclusive', 'alternative to'];
const REFINES = ['refines', 'specialises', 'specializes'];

function inferEdgeType(intent: string | undefined): EdgeType {
  if (!intent) return 'unspecified';
  const lower = intent.toLowerCase();
  if (DATAFLOW.some((kw) => lower.includes(kw))) return 'dataflow';
  if (REQUIRES.some((kw) => lower.includes(kw))) return 'requires';
  if (CONFLICTS.some((kw) => lower.includes(kw))) return 'conflicts';
  if (REFINES.some((kw) => lower.includes(kw))) return 'refines';
  return 'unspecified';
}

function buildIndices(
  rootUid: Uid,
  nodes: Map<Uid, IntentNode>,
  tree: Treearc[]
): { childrenOf: Map<Uid, Uid[]>; parentOf: Map<Uid, Uid | null>; depthOf: Map<Uid, number> } {
  const childrenOf = new Map<Uid, Uid[]>();
  const parentOf = new Map<Uid, Uid | null>();
  for (const uid of nodes.keys()) {
    childrenOf.set(uid, []);
    parentOf.set(uid, null);
  }
  for (const arc of tree) {
    if (!nodes.has(arc.parent) || !nodes.has(arc.child)) continue;
    childrenOf.get(arc.parent)!.push(arc.child);
    parentOf.set(arc.child, arc.parent);
  }

  const depthOf = new Map<Uid, number>();
  // BFS from root; orphans (unreachable) get depth = Infinity-equivalent — skip.
  const queue: Array<{ uid: Uid; depth: number }> = [{ uid: rootUid, depth: 0 }];
  while (queue.length > 0) {
    const { uid, depth } = queue.shift()!;
    if (depthOf.has(uid)) continue;
    depthOf.set(uid, depth);
    for (const child of childrenOf.get(uid) ?? []) {
      queue.push({ uid: child, depth: depth + 1 });
    }
  }
  // Orphans default to depth 0 so they still render at root layer.
  for (const uid of nodes.keys()) {
    if (!depthOf.has(uid)) depthOf.set(uid, 0);
  }
  return { childrenOf, parentOf, depthOf };
}

function findRoot(nodes: Map<Uid, IntentNode>, parentOf: Map<Uid, Uid | null>): Uid {
  // Prefer "ROOT" if present.
  if (nodes.has('ROOT')) return 'ROOT';
  for (const [uid, parent] of parentOf) {
    if (parent === null) return uid;
  }
  // Fallback: first node.
  const first = nodes.keys().next();
  if (first.done) throw new Error('Graph has no nodes.');
  return first.value;
}

export interface LoadGraphResult {
  model: SerialisedIntentGraphModel;
  /** SHA-256 hex of raw file content (CRLF-normalised). */
  fileHash: string;
  /** Internal lenses parsed from the IG file. Empty object if absent. */
  lenses: Record<string, SerialisedLensConfig>;
  /** Resolved default lens name from meta.default_lens, or null if absent/unresolved. */
  default_lens: string | null;
}

export async function loadGraph(uri: vscode.Uri): Promise<LoadGraphResult> {
  const text = await readFile(uri.fsPath, 'utf8');
  // Compute hash before parsing (same normalisation as computeFileHash).
  const fileHash = computeFileHash(text);
  let parsed: RawGraph;
  try {
    parsed = yamlParse(text) as RawGraph;
  } catch (err) {
    throw new Error(`Failed to parse graph file: ${(err as Error).message}`);
  }
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Graph file is empty or not an object.');
  }

  const rawNodes = parsed.nodes ?? [];
  const rawTree = parsed.treearcs ?? [];
  const rawLinks = parsed.intentlinks ?? [];

  const nodes = new Map<Uid, IntentNode>();
  for (const n of rawNodes) {
    if (!n || typeof n.uid !== 'string') continue;
    nodes.set(n.uid, {
      uid: n.uid,
      name: n.name ?? n.uid,
      intent: n.intent,
      epistemic_state: n.epistemic_state,
      constraints: n.constraints
    });
  }

  const tree: Treearc[] = [];
  for (const arc of rawTree) {
    if (!arc || typeof arc.parent !== 'string' || typeof arc.child !== 'string') continue;
    tree.push({ parent: arc.parent, child: arc.child });
  }

  // First pass: parentOf for root detection.
  const tmpParentOf = new Map<Uid, Uid | null>();
  for (const uid of nodes.keys()) tmpParentOf.set(uid, null);
  for (const arc of tree) {
    if (nodes.has(arc.child)) tmpParentOf.set(arc.child, arc.parent);
  }
  const rootUid = nodes.size > 0 ? findRoot(nodes, tmpParentOf) : 'ROOT';

  const { childrenOf, parentOf, depthOf } = buildIndices(rootUid, nodes, tree);

  // M1 (§3.6): de-collide auto-generated link UIDs for multi-edges.
  const seenAutoUid = new Map<string, number>();
  const links: IntentLink[] = rawLinks
    .filter((l): l is RawIntentLink => !!l && typeof l.src === 'string' && typeof l.dst === 'string')
    .map((l) => {
      if (l.uid) {
        return {
          uid: l.uid,
          src: l.src,
          dst: l.dst,
          intent: l.intent,
          edgeType: inferEdgeType(l.intent)
        };
      }
      const base = `${l.src}_${l.dst}`;
      const n = (seenAutoUid.get(base) ?? 0) + 1;
      seenAutoUid.set(base, n);
      const uid = n === 1 ? base : `${base}#${n}`;
      return {
        uid,
        src: l.src,
        dst: l.dst,
        intent: l.intent,
        edgeType: inferEdgeType(l.intent)
      };
    });

  // M2 (§3.6): surface orphan-node count as a non-fatal warning.
  // An orphan is any node !== rootUid with parentOf === null.
  const warnings: string[] = [];
  let orphanCount = 0;
  for (const uid of nodes.keys()) {
    if (uid === rootUid) continue;
    if (parentOf.get(uid) === null) orphanCount += 1;
  }
  if (orphanCount > 0) {
    warnings.push(`${orphanCount} orphan node${orphanCount === 1 ? '' : 's'} attached at root`);
  }

  const graphName = parsed.meta?.name ?? path.basename(uri.fsPath);

  // Parse internal lenses from top-level `lenses` key.
  // Each entry is coerced to SerialisedLensConfig; absent or malformed entries
  // are skipped defensively so old IG files without lenses load without error.
  // nodes map now contains LensNodeEntry (lod + optional position), not bare strings.
  const rawLenses = parsed.lenses ?? {};
  const lenses: Record<string, SerialisedLensConfig> = {};
  for (const [lensName, rawConfig] of Object.entries(rawLenses)) {
    if (!rawConfig || typeof rawConfig !== 'object') continue;
    const cfg = rawConfig as Record<string, unknown>;
    const cfgNodes = (cfg['nodes'] ?? {}) as Record<string, unknown>;
    const nodesMap: Record<string, any> = {};
    for (const [uid, entry] of Object.entries(cfgNodes)) {
      // Entry can be a LensNodeEntry {lod, position?} or old bare string.
      // Detect old shape and error with migration message.
      if (typeof entry === 'string') {
        // Old bare-string shape detected.
        throw new Error(
          'LensConfig schema migration required. Run (from the repo root):\n' +
          '  python3 src/scripts/migrate_lens_config_v2.py <your-ig-file>'
        );
      }

      // New shape: entry is LensNodeEntry {lod: string, position?: {x, y}}.
      if (typeof entry === 'object' && entry !== null) {
        const lod = (entry as any).lod;
        if (lod === 'skeleton' || lod === 'lean' || lod === 'full') {
          nodesMap[uid] = { lod, position: (entry as any).position };
        }
      }
    }
    const cfgLinks = cfg['intentlinks'];
    const intentlinks: string[] = Array.isArray(cfgLinks)
      ? cfgLinks.filter((v): v is string => typeof v === 'string')
      : [];
    lenses[lensName] = {
      name: typeof cfg['name'] === 'string' ? cfg['name'] : lensName,
      description: typeof cfg['description'] === 'string' ? cfg['description'] : undefined,
      target_uids: Array.isArray(cfg['target_uids'])
        ? (cfg['target_uids'] as unknown[]).filter((v): v is string => typeof v === 'string')
        : undefined,
      nodes: nodesMap,
      intentlinks
    };
  }

  // Resolve default_lens: must reference an existing key in lenses.
  const rawDefaultLens = parsed.meta?.default_lens;
  const default_lens: string | null =
    typeof rawDefaultLens === 'string' && rawDefaultLens in lenses
      ? rawDefaultLens
      : null;

  const model: IntentGraphModel = {
    graphName,
    rootUid,
    nodes,
    links,
    tree,
    childrenOf,
    parentOf,
    depthOf,
    warnings: warnings.length > 0 ? warnings : undefined
  };
  return { model: serialiseModel(model), fileHash, lenses, default_lens };
}
