// Webview-side state container. Tracks the current model, viewport snapshot,
// collapse set, per-node LOD, and a simple uiPhase enum.
// Covers reload/error phases, per-node LOD, and snapshot/restore.
// currentFileHash tracks the SHA-256 of the file at last load
//   or last successful edit; used in EditFieldRequest.fileHash.

import type cytoscape from 'cytoscape';

import type { IntentGraphModel, NodeLOD, Uid } from '../shared/graphTypes';

export type UiPhase = 'loading' | 'ready' | 'error' | 'empty' | 'stale';

export interface ViewportSnapshot {
  zoom: number;
  pan: { x: number; y: number };
}

export interface DiffResult {
  kind: 'structural' | 'metadata';
}

export class WebviewState {
  model: IntentGraphModel | null = null;
  viewport: ViewportSnapshot | null = null;
  collapseSet: Set<Uid> = new Set();
  /** Per-node LOD state. Default `lean` (absent entry); `full` entries created on tap. */
  nodeLOD: Map<Uid, NodeLOD> = new Map();
  uiPhase: UiPhase = 'loading';

  // Race protection: coalesce reload requests that arrive while one is in flight.
  reloadInFlight = false;
  pending = false;

  /** SHA-256 hex of the file as of the last LoadGraphResponse or successful EditFieldResponse.
   *  Sent with every EditFieldRequest so the host can detect external changes. */
  currentFileHash: string | null = null;

  setModel(model: IntentGraphModel): void {
    this.model = model;
  }

  snapshotViewport(cy: cytoscape.Core): void {
    this.viewport = { zoom: cy.zoom(), pan: { ...cy.pan() } };
  }

  restoreViewport(cy: cytoscape.Core): void {
    if (!this.viewport) return;
    cy.zoom(this.viewport.zoom);
    cy.pan(this.viewport.pan);
  }

  /** Snapshot UIDs currently in `full` LOD; used before structural reload. */
  snapshotLODSet(): Uid[] {
    const out: Uid[] = [];
    for (const [uid, lod] of this.nodeLOD) {
      if (lod === 'full') out.push(uid);
    }
    return out;
  }

  /** Restore after structural reload — only retain entries whose UIDs survived. */
  restoreLODSet(uids: Uid[], surviving: Set<Uid>): void {
    this.nodeLOD.clear();
    for (const uid of uids) {
      if (surviving.has(uid)) this.nodeLOD.set(uid, 'full');
    }
  }

  /**
   * Compare current model with `next`. Decide if change is structural
   * (nodes/treearcs/intentlinks) or metadata-only (intent/epistemic/constraints/name).
   */
  diff(next: IntentGraphModel): DiffResult {
    const cur = this.model;
    if (!cur) return { kind: 'structural' };

    if (cur.nodes.size !== next.nodes.size) return { kind: 'structural' };
    for (const uid of cur.nodes.keys()) {
      if (!next.nodes.has(uid)) return { kind: 'structural' };
    }

    if (cur.tree.length !== next.tree.length) return { kind: 'structural' };
    const treeKeys = new Set(cur.tree.map((a) => `${a.parent}->${a.child}`));
    for (const a of next.tree) {
      if (!treeKeys.has(`${a.parent}->${a.child}`)) return { kind: 'structural' };
    }

    if (cur.links.length !== next.links.length) return { kind: 'structural' };
    const linkKeys = new Set(cur.links.map((l) => `${l.src}->${l.dst}`));
    for (const l of next.links) {
      if (!linkKeys.has(`${l.src}->${l.dst}`)) return { kind: 'structural' };
    }
    return { kind: 'metadata' };
  }
}
