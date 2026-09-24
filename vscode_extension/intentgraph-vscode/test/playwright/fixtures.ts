// Fixture loader for Playwright specs.
//
// Reads .ig.json|.ig.yaml from disk and produces a SerialisedIntentGraphModel
// that matches what src/graph/loadGraph.ts returns. The host-side loadGraph
// imports `vscode`, so we can't reuse it directly from Node; this is a
// minimal mirror of the build-indices path. Keep in sync if loadGraph
// changes its model contract.

import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parse as yamlParse } from 'yaml';

const HERE = __dirname;
const EXTENSION_ROOT = join(HERE, '..', '..');

export interface SerialisedIntentGraphModel {
  graphName: string;
  rootUid: string;
  nodes: Record<string, IntentNode>;
  links: IntentLink[];
  tree: Treearc[];
  childrenOf: Record<string, string[]>;
  parentOf: Record<string, string | null>;
  depthOf: Record<string, number>;
  warnings?: string[];
}

export interface IntentNode {
  uid: string;
  name: string;
  intent?: string;
  epistemic_state?: string;
  constraints?: string[];
}

export interface IntentLink {
  uid: string;
  src: string;
  dst: string;
  intent?: string;
  edgeType: 'dataflow' | 'requires' | 'conflicts' | 'refines' | 'unspecified';
}

export interface Treearc {
  parent: string;
  child: string;
}

const DATAFLOW = ['produces', 'provides', 'feeds', 'consumed by', 'dataflow'];
const REQUIRES = ['requires', 'depends on', 'must exist', 'prerequisite'];
const CONFLICTS = ['conflicts', 'mutually exclusive', 'alternative to'];
const REFINES = ['refines', 'specialises', 'specializes'];

function inferEdgeType(intent: string | undefined): IntentLink['edgeType'] {
  if (!intent) return 'unspecified';
  const lower = intent.toLowerCase();
  if (DATAFLOW.some((kw) => lower.includes(kw))) return 'dataflow';
  if (REQUIRES.some((kw) => lower.includes(kw))) return 'requires';
  if (CONFLICTS.some((kw) => lower.includes(kw))) return 'conflicts';
  if (REFINES.some((kw) => lower.includes(kw))) return 'refines';
  return 'unspecified';
}

function resolvePath(fixturePath: string): string {
  // Accept absolute paths, otherwise resolve relative to extension root.
  if (fixturePath.startsWith('/')) return fixturePath;
  return join(EXTENSION_ROOT, fixturePath);
}

/**
 * Load a fixture .ig.json|.ig.yaml and produce the same SerialisedIntentGraphModel
 * that the host emits in LoadGraphResponse.model.
 *
 * Path is resolved relative to the extension root (intentgraph-vscode/).
 */
export async function loadFixture(fixturePath: string): Promise<SerialisedIntentGraphModel> {
  const resolved = resolvePath(fixturePath);
  const text = await readFile(resolved, 'utf8');
  const parsed = yamlParse(text) as {
    meta?: { name?: string };
    nodes?: Array<{ uid: string; name?: string; intent?: string; epistemic_state?: string; constraints?: string[] }>;
    treearcs?: Array<{ parent: string; child: string }>;
    intentlinks?: Array<{ uid?: string; src: string; dst: string; intent?: string }>;
  };

  if (!parsed || typeof parsed !== 'object') {
    throw new Error(`Fixture ${resolved} is empty or not an object`);
  }

  const nodesArr = parsed.nodes ?? [];
  const treeArr = parsed.treearcs ?? [];
  const linksArr = parsed.intentlinks ?? [];

  const nodes: Record<string, IntentNode> = {};
  for (const n of nodesArr) {
    if (!n || typeof n.uid !== 'string') continue;
    nodes[n.uid] = {
      uid: n.uid,
      name: n.name ?? n.uid,
      intent: n.intent,
      epistemic_state: n.epistemic_state,
      constraints: n.constraints
    };
  }

  const tree: Treearc[] = treeArr
    .filter((a): a is Treearc => !!a && typeof a.parent === 'string' && typeof a.child === 'string')
    .map((a) => ({ parent: a.parent, child: a.child }));

  // childrenOf / parentOf
  const childrenOf: Record<string, string[]> = {};
  const parentOf: Record<string, string | null> = {};
  for (const uid of Object.keys(nodes)) {
    childrenOf[uid] = [];
    parentOf[uid] = null;
  }
  for (const arc of tree) {
    if (!nodes[arc.parent] || !nodes[arc.child]) continue;
    childrenOf[arc.parent].push(arc.child);
    parentOf[arc.child] = arc.parent;
  }

  // Root: prefer "ROOT", else first parentless node, else first node.
  let rootUid = 'ROOT';
  if (!nodes[rootUid]) {
    rootUid =
      Object.entries(parentOf).find(([, p]) => p === null)?.[0] ??
      Object.keys(nodes)[0] ??
      'ROOT';
  }

  // BFS depth from root.
  const depthOf: Record<string, number> = {};
  const queue: Array<{ uid: string; depth: number }> = [{ uid: rootUid, depth: 0 }];
  while (queue.length > 0) {
    const { uid, depth } = queue.shift()!;
    if (depthOf[uid] !== undefined) continue;
    depthOf[uid] = depth;
    for (const child of childrenOf[uid] ?? []) {
      queue.push({ uid: child, depth: depth + 1 });
    }
  }
  for (const uid of Object.keys(nodes)) {
    if (depthOf[uid] === undefined) depthOf[uid] = 0;
  }

  // Intentlinks with auto-uid de-collision (mirrors host loader §3.6 M1).
  const seenAutoUid = new Map<string, number>();
  const links: IntentLink[] = linksArr
    .filter((l): l is { src: string; dst: string; uid?: string; intent?: string } =>
      !!l && typeof l.src === 'string' && typeof l.dst === 'string'
    )
    .map((l) => {
      if (l.uid) {
        return { uid: l.uid, src: l.src, dst: l.dst, intent: l.intent, edgeType: inferEdgeType(l.intent) };
      }
      const base = `${l.src}_${l.dst}`;
      const n = (seenAutoUid.get(base) ?? 0) + 1;
      seenAutoUid.set(base, n);
      const uid = n === 1 ? base : `${base}#${n}`;
      return { uid, src: l.src, dst: l.dst, intent: l.intent, edgeType: inferEdgeType(l.intent) };
    });

  const graphName = parsed.meta?.name ?? resolved.split('/').pop()!;

  return {
    graphName,
    rootUid,
    nodes,
    links,
    tree,
    childrenOf,
    parentOf,
    depthOf
  };
}
