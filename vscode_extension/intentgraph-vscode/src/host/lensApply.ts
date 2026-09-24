// Host-only module: translate a SerialisedLensConfig into the LensApplyPayload
// wire format sent to the webview.
// Replaces lensState.ts + lensFileIO.ts.
// No file I/O, no YAML serialisation, no workspaceState access for lens content.
// New-architecture lens-apply flow (see design history), with diagnostics.
// LensNodeEntry now includes optional position; migration detection for old bare-string shape.

import type { SerialisedLensConfig, Uid } from '../shared/graphTypes';
import type { LensApplyPayload, LensDiagnostic } from '../messaging/messageTypes';

/** Error thrown when old lens schema (bare LOD strings) is detected. */
export class LensSchemaMigrationRequired extends Error {
  constructor() {
    super(
      'LensConfig schema migration required. Run (from the repo root):\n' +
      '  python3 src/scripts/migrate_lens_config_v2.py <your-ig-file>'
    );
    this.name = 'LensSchemaMigrationRequired';
  }
}

/**
 * Translate a SerialisedLensConfig into the LensApplyPayload wire format.
 * Computes diagnostics for any UIDs referenced in the config that are absent
 * from the current graph model.
 *
 * Detects old bare-string LOD shape and throws LensSchemaMigrationRequired
 * with migration guidance.
 *
 * @param lensConfig  The LensConfig parsed from the IG file.
 * @param availableNodes  Set of all node UIDs currently present in the model.
 * @param availableLinks  Set of all intentlink UIDs currently present in the model.
 *   Pass empty set if link diagnostics are not needed (stale-link check is
 *   informational only — viewer never refuses to render).
 * @returns  LensApplyPayload ready to send via ApplyLensNotification.
 * @throws  LensSchemaMigrationRequired if old bare-string LOD entries detected.
 */
export function lensConfigToPayload(
  lensConfig: SerialisedLensConfig,
  availableNodes: Set<Uid>,
  availableLinks: Set<string> = new Set()
): LensApplyPayload {
  const diagnostics: LensDiagnostic[] = [];

  // Compute filtered node map: only include UIDs actually present in the model.
  // Detect old bare-string shape and throw migration error.
  // Coord-frame fix: also propagate the parent-relative `position` field so
  // the webview can restore positions on apply.
  const filteredNodes: Record<Uid, 'skeleton' | 'lean' | 'full'> = {};
  const filteredPositions: Record<Uid, { x: number; y: number }> = {};
  for (const [uid, entry] of Object.entries(lensConfig.nodes)) {
    // Detect old bare-string shape: if entry is a string, migration is required.
    if (typeof entry === 'string') {
      throw new LensSchemaMigrationRequired();
    }

    // New shape: entry is LensNodeEntry with { lod, position? }.
    const lod = (entry as any).lod;
    if (typeof lod !== 'string') {
      throw new LensSchemaMigrationRequired();
    }

    if (availableNodes.has(uid)) {
      filteredNodes[uid] = lod as 'skeleton' | 'lean' | 'full';
      const pos = (entry as any).position;
      if (pos && typeof pos.x === 'number' && typeof pos.y === 'number') {
        filteredPositions[uid] = { x: pos.x, y: pos.y };
      }
    } else {
      diagnostics.push({
        level: 'warn',
        uid,
        message: `node '${uid}' not found in graph (stale UID — node may have been deleted)`
      });
    }
  }

  // Compute filtered intentlinks: include all listed; flag missing ones.
  const filteredLinks: string[] = [];
  for (const linkUid of (lensConfig.intentlinks ?? [])) {
    if (availableLinks.size === 0 || availableLinks.has(linkUid)) {
      filteredLinks.push(linkUid);
    } else {
      diagnostics.push({
        level: 'warn',
        uid: linkUid,
        message: `link '${linkUid}' not found in graph (stale UID)`
      });
    }
  }

  return {
    name: lensConfig.name,
    nodes: filteredNodes,
    positions: filteredPositions,
    intentlinks: filteredLinks,
    diagnostics
  };
}
