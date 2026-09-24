// Autosave helpers for position persistence (drag-release → lens write).
// Handles PERSISTENCE.AUTOCREATE (create default lens if none exists) and
// PERSISTENCE.POSITIONS (write position to lens entry).
// Spec: LENS_REDESIGN_SPEC.md §7, §8 (Drag Gesture, Autosave, Autocreate).

import { readFile } from 'node:fs/promises';
import * as YAML from 'yaml';
import { computeFileHash } from './fileHash';
import { writeIgFile } from './diskWrite';
import type { Uid, Position } from '../shared/graphTypes';

export interface OperationResult {
  ok: boolean;
  error?: string;
  newFileHash?: string;
  /**
   * Bug 1 follow-up: signals "request accepted but nothing on disk changed"
   * (e.g. collapse of a compound whose children are already absent from the
   * lens). The provider emits a host-side trace marker on this so the chain
   * webview→host stays visible in the trace even when no fileWrite happens.
   */
  noop?: boolean;
}

/**
 * Create a default lens in the IG file if it doesn't exist.
 * PIG PERSISTENCE.AUTOCREATE Constraints:
 *   - Trigger: first drag-release when no lens active.
 *   - Action: silently create lens named 'default'; auto-activate.
 *   - Sets meta.default_lens: 'default'.
 *   - Visual feedback: toast 'Created lens default'.
 *   - Subsequent drags use the now-active 'default' lens via PERSISTENCE.AUTOSAVE.
 */
export async function createDefaultLens(
  fsPath: string,
  doc: YAML.Document
): Promise<OperationResult> {
  try {
    // Check if 'lenses' exists; if not, create the section.
    // PIG PERSISTENCE.AUTOCREATE — bootstrap missing 'lenses' as a YAMLMap so setIn descends correctly.
    const lenses = doc.get('lenses');
    if (!lenses) {
      doc.set('lenses', new YAML.YAMLMap());
    }

    // Check if 'default' lens already exists.
    // PIG PERSISTENCE.AUTOCREATE — YAMLMap requires .hasIn(), not bracket access.
    if (doc.hasIn(['lenses', 'default'])) {
      // Lens already exists; just set meta.default_lens if not already set.
      // PIG PERSISTENCE.AUTOCREATE — bootstrap missing 'meta' as a YAMLMap so setIn descends correctly.
      const currentDefault = doc.getIn(['meta', 'default_lens']);
      if (currentDefault !== 'default') {
        if (!doc.has('meta')) {
          doc.set('meta', new YAML.YAMLMap());
        }
        doc.setIn(['meta', 'default_lens'], 'default');
      }
      // Write the updated file.
      const newContent = doc.toString();
      const newHash = computeFileHash(newContent);
      await writeIgFile({ fsPath, content: newContent, caller: 'autosave.createDefaultLens.metaOnly' });
      return { ok: true, newFileHash: newHash };
    }

    // Create the 'default' lens with an empty nodes map.
    const defaultLens = {
      name: 'default',
      nodes: {}
    };
    doc.setIn(['lenses', 'default'], defaultLens);

    // Set meta.default_lens = 'default'.
    // PIG PERSISTENCE.AUTOCREATE — bootstrap missing 'meta' as a YAMLMap so setIn descends correctly.
    if (!doc.has('meta')) {
      doc.set('meta', new YAML.YAMLMap());
    }
    doc.setIn(['meta', 'default_lens'], 'default');

    // Write the updated file.
    const newContent = doc.toString();
    const newHash = computeFileHash(newContent);
    await writeIgFile({ fsPath, content: newContent, caller: 'autosave.createDefaultLens.full' });

    return { ok: true, newFileHash: newHash };
  } catch (err) {
    return {
      ok: false,
      error: `Cannot create default lens: ${err instanceof Error ? err.message : String(err)}`
    };
  }
}

/**
 * Parse and mutate a lens entry to add/update a node position.
 * PIG PERSISTENCE.POSITIONS Constraints:
 *   - Coordinate frame: parent-relative (A2). Position stored as Cytoscape node CENTER.
 *   - Storage: lens entry position field -- {x, y} -- as Cytoscape node CENTER.
 *   - On drag-release: position captured and written to active lens via auto-save.
 *   - Self-write suppression: routes through selfWritePath flag (caller sets before/after).
 *
 * Note: Caller is responsible for reading the file and parsing the doc; this function
 * mutates the doc in-place and writes it back.
 */
export async function parseAndMutateLensPosition(
  fsPath: string,
  doc: YAML.Document,
  lensName: string,
  uid: Uid,
  position: Position
): Promise<OperationResult> {
  try {
    // Ensure lenses section exists.
    // PIG PERSISTENCE.AUTOCREATE — bootstrap missing 'lenses' as a YAMLMap so setIn descends correctly.
    if (!doc.has('lenses')) {
      doc.set('lenses', new YAML.YAMLMap());
    }

    // Ensure the lens exists.
    // PIG PERSISTENCE.AUTOSAVE — YAMLMap requires .hasIn(), not bracket access.
    if (!doc.hasIn(['lenses', lensName])) {
      return { ok: false, error: `Lens '${lensName}' not found.` };
    }

    // Ensure the lens has a nodes map.
    // PIG PERSISTENCE.POSITIONS — bootstrap missing 'nodes' as a YAMLMap so setIn descends correctly.
    const lensPath = ['lenses', lensName, 'nodes'] as const;
    let nodes = doc.getIn(lensPath);
    if (!nodes || typeof nodes !== 'object') {
      doc.setIn(lensPath, new YAML.YAMLMap());
      nodes = doc.getIn(lensPath);
    }

    // Ensure the node entry exists (create with 'lean' LOD if absent).
    const nodeEntryPath = [...lensPath, uid] as const;
    let nodeEntry = doc.getIn(nodeEntryPath);
    if (!nodeEntry || typeof nodeEntry !== 'object') {
      // Create a new LensNodeEntry with default lod='lean' and the position.
      const newEntry = {
        lod: 'lean',
        position
      };
      doc.setIn(nodeEntryPath, newEntry);
    } else {
      // Update existing entry: ensure lod exists, set position.
      const lod = (nodeEntry as any).lod ?? 'lean';
      const positionPath = [...nodeEntryPath, 'position'] as const;
      doc.setIn(positionPath, position);
      // Also ensure lod is set if missing.
      if (!(nodeEntry as any).lod) {
        doc.setIn([...nodeEntryPath, 'lod'], lod);
      }
    }

    // Write the updated file.
    const newContent = doc.toString();
    const newHash = computeFileHash(newContent);
    await writeIgFile({ fsPath, content: newContent, caller: 'autosave.parseAndMutateLensPosition' });

    return { ok: true, newFileHash: newHash };
  } catch (err) {
    return {
      ok: false,
      error: `Cannot mutate lens position: ${err instanceof Error ? err.message : String(err)}`
    };
  }
}

/**
 * Bug 1 fix — persist a cue-driven visibility change to the active lens.
 * Source of truth for the rule: PIG node `LENSSCHEMA.VISIBILITY`.
 *
 *  - 'collapse': remove every descendant of `uid` from `lenses[lensName].nodes`.
 *    The compound itself stays. By the visibility rule (no children in lens →
 *    compound renders collapsed), this is sufficient.
 *
 *  - 'expand':   add `uid`'s direct children to `lenses[lensName].nodes` with
 *    `lod: 'lean'` and the supplied positions. By the rule (≥1 child in lens
 *    → compound renders expanded), one direct child is sufficient; we add all
 *    of them so the user sees the full level-1 fan-out.
 *
 * Caller responsibilities:
 *   - Caller has already parsed the YAML doc (`parseDocument`).
 *   - Caller passes `childrenOf` from the cached model (host-side).
 *   - Caller is responsible for `selfWritePath` and `lastLoadedFileHash` sync
 *     around the call (mirrors the parseAndMutateLensPosition contract).
 */
export async function parseAndMutateLensVisibility(
  fsPath: string,
  doc: YAML.Document,
  lensName: string,
  op: 'collapse' | 'expand',
  uid: Uid,
  childrenOf: ReadonlyMap<Uid, ReadonlyArray<Uid>>,
  childPositions?: Record<Uid, Position>
): Promise<OperationResult> {
  try {
    if (!doc.has('lenses')) {
      doc.set('lenses', new YAML.YAMLMap());
    }
    if (!doc.hasIn(['lenses', lensName])) {
      return { ok: false, error: `Lens '${lensName}' not found.` };
    }
    const lensPath = ['lenses', lensName, 'nodes'] as const;
    if (!doc.getIn(lensPath)) {
      doc.setIn(lensPath, new YAML.YAMLMap());
    }

    let mutationCount = 0;

    if (op === 'collapse') {
      // Walk the subtree rooted at uid (excluding uid itself) and delete each
      // descendant's lens entry. Iterative DFS over `childrenOf`.
      const stack: Uid[] = [...(childrenOf.get(uid) ?? [])];
      while (stack.length > 0) {
        const cur = stack.pop()!;
        if (doc.hasIn([...lensPath, cur])) {
          doc.deleteIn([...lensPath, cur]);
          mutationCount++;
        }
        const grandchildren = childrenOf.get(cur);
        if (grandchildren) stack.push(...grandchildren);
      }
    } else {
      // op === 'expand'
      const directChildren = childrenOf.get(uid) ?? [];
      for (const childUid of directChildren) {
        const entryPath = [...lensPath, childUid] as const;
        // If already present, leave alone (preserves user's prior position/lod).
        if (doc.hasIn(entryPath)) continue;
        const pos = childPositions?.[childUid];
        const newEntry: { lod: string; position?: Position } = { lod: 'lean' };
        if (pos !== undefined) newEntry.position = pos;
        doc.setIn(entryPath, newEntry);
        mutationCount++;
      }
    }

    // No-op early return. The caller (provider) emits a `lensVisibilityNoop`
    // host trace entry on its side so the chain webview→host stays visible
    // even when nothing was on-disk to change.
    if (mutationCount === 0) {
      return { ok: true, noop: true };
    }

    const newContent = doc.toString();
    const newHash = computeFileHash(newContent);
    await writeIgFile({
      fsPath,
      content: newContent,
      caller: op === 'collapse' ? 'lensVisibility.collapse' : 'lensVisibility.expand'
    });

    return { ok: true, newFileHash: newHash };
  } catch (err) {
    return {
      ok: false,
      error: `Cannot mutate lens visibility: ${err instanceof Error ? err.message : String(err)}`
    };
  }
}

/**
 * Persist a leaf's lod change to the active lens. Mirror of
 * parseAndMutateLensPosition's contract: caller has parsed doc; this fn
 * mutates and writes; caller manages selfWritePath + post-write hash sync.
 *
 * If the uid isn't already in the lens, this is a no-op (visibility rule
 * gates membership; lod-only persistence shouldn't add membership).
 */
export async function parseAndMutateLensLod(
  fsPath: string,
  doc: YAML.Document,
  lensName: string,
  uid: Uid,
  lod: 'lean' | 'full'
): Promise<OperationResult> {
  try {
    if (!doc.hasIn(['lenses', lensName, 'nodes', uid])) {
      // Node not in this lens → nothing to persist. Returning noop:true keeps
      // the trace chain visible (provider emits a noop marker).
      return { ok: true, noop: true };
    }

    const currentLod = doc.getIn(['lenses', lensName, 'nodes', uid, 'lod']);
    if (currentLod === lod) {
      return { ok: true, noop: true };
    }

    doc.setIn(['lenses', lensName, 'nodes', uid, 'lod'], lod);

    const newContent = doc.toString();
    const newHash = computeFileHash(newContent);
    await writeIgFile({
      fsPath,
      content: newContent,
      caller: `lensLod.${lod}`
    });
    return { ok: true, newFileHash: newHash };
  } catch (err) {
    return {
      ok: false,
      error: `Cannot mutate lens lod: ${err instanceof Error ? err.message : String(err)}`
    };
  }
}
