// Client-side translation of a SerialisedLensConfig to LensApplyPayload.
// Mirrors src/host/lensApply.ts but runs in the webview without vscode.* imports.
// Kept in webview to avoid importing host code across the layer boundary.

import type { SerialisedLensConfig } from '../../shared/graphTypes';
import type { LensApplyPayload, LensDiagnostic } from '../../messaging/messageTypes';

export function lensConfigToPayloadClient(
  lensConfig: SerialisedLensConfig,
  availableNodeUids: Set<string>,
  availableLinkUids: Set<string>
): LensApplyPayload {
  const diagnostics: LensDiagnostic[] = [];
  const filteredNodes: Record<string, 'skeleton' | 'lean' | 'full'> = {};
  const filteredPositions: Record<string, { x: number; y: number }> = {};

  for (const [uid, entry] of Object.entries(lensConfig.nodes)) {
    if (availableNodeUids.has(uid)) {
      // Entry is now LensNodeEntry {lod, position?}; extract lod.
      const lod = typeof entry === 'object' && entry !== null
        ? (entry as any).lod
        : (entry as unknown as string);  // Fallback for type safety.
      if (lod === 'skeleton' || lod === 'lean' || lod === 'full') {
        filteredNodes[uid] = lod;
      }
      // Coord-frame fix: propagate stored parent-relative position.
      const pos = typeof entry === 'object' && entry !== null ? (entry as any).position : undefined;
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

  const filteredLinks: string[] = [];
  for (const linkUid of (lensConfig.intentlinks ?? [])) {
    if (availableLinkUids.size === 0 || availableLinkUids.has(linkUid)) {
      filteredLinks.push(linkUid);
    } else {
      diagnostics.push({
        level: 'warn',
        uid: linkUid,
        message: `link '${linkUid}' not found in graph (stale UID)`
      });
    }
  }

  return { name: lensConfig.name, nodes: filteredNodes, positions: filteredPositions, intentlinks: filteredLinks, diagnostics };
}
