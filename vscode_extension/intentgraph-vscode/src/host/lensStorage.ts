// Lens storage facade.
// Centralises the read-file → parseDocument → mutate-doc → write cycle that
// every lens persistence path used to inline in IntentGraphEditorProvider.
// Each method returns the same OperationResult / LensCrudResult contract as
// the underlying helpers in autosave.ts and lensCrud.ts, so callers can keep
// their existing response handling.
//
// This module is framework-agnostic: no vscode imports, no Messenger. Caller
// (EditorProvider) is still responsible for selfWritePath bookkeeping around
// each call — that flag is about the file-watcher, not about lens I/O.

import { readFile } from 'node:fs/promises';
import { parseDocument } from 'yaml';
import {
  createDefaultLens,
  parseAndMutateLensPosition,
  parseAndMutateLensVisibility,
  parseAndMutateLensLod,
  type OperationResult
} from './autosave';
import {
  createLens as createLensRaw,
  renameLens as renameLensRaw,
  deleteLens as deleteLensRaw,
  type LensCrudResult,
  type NewLensTopology
} from './lensCrud';
import type { Uid, Position } from '../shared/graphTypes';

export interface LensStorage {
  /** PIG PERSISTENCE.AUTOCREATE: create 'default' lens if absent; idempotent. */
  ensureDefaultLens(): Promise<OperationResult>;

  /** PIG PERSISTENCE.POSITIONS: write a node position to the named lens. */
  persistPosition(lensName: string, uid: Uid, position: Position): Promise<OperationResult>;

  /** PIG LENSSCHEMA.VISIBILITY: collapse/expand a compound's lens membership. */
  persistVisibility(
    lensName: string,
    op: 'collapse' | 'expand',
    uid: Uid,
    childrenOf: ReadonlyMap<Uid, ReadonlyArray<Uid>>,
    childPositions?: Record<Uid, Position>
  ): Promise<OperationResult>;

  /** Persist a leaf's lod transition (lean ↔ full) to the named lens. */
  persistLod(lensName: string, uid: Uid, lod: 'lean' | 'full'): Promise<OperationResult>;

  /** PIG LENS_UI.CTRLPANEL.2: create a named lens with default seed membership. */
  createLens(name: string, topology: NewLensTopology): Promise<LensCrudResult>;

  /** PIG LENS_UI.CTRLPANEL.3: rename a lens. */
  renameLens(oldName: string, newName: string): Promise<LensCrudResult>;

  /** PIG LENS_UI.CTRLPANEL.4: delete a lens. */
  deleteLens(name: string): Promise<LensCrudResult>;
}

async function readDoc(fsPath: string): Promise<ReturnType<typeof parseDocument>> {
  const raw = await readFile(fsPath, 'utf8');
  return parseDocument(raw);
}

export function createLensStorage(fsPath: string): LensStorage {
  return {
    async ensureDefaultLens() {
      const doc = await readDoc(fsPath);
      return createDefaultLens(fsPath, doc);
    },

    async persistPosition(lensName, uid, position) {
      const doc = await readDoc(fsPath);
      return parseAndMutateLensPosition(fsPath, doc, lensName, uid, position);
    },

    async persistVisibility(lensName, op, uid, childrenOf, childPositions) {
      const doc = await readDoc(fsPath);
      return parseAndMutateLensVisibility(fsPath, doc, lensName, op, uid, childrenOf, childPositions);
    },

    async persistLod(lensName, uid, lod) {
      const doc = await readDoc(fsPath);
      return parseAndMutateLensLod(fsPath, doc, lensName, uid, lod);
    },

    async createLens(name, topology) {
      const doc = await readDoc(fsPath);
      return createLensRaw(fsPath, doc, name, topology);
    },

    async renameLens(oldName, newName) {
      const doc = await readDoc(fsPath);
      return renameLensRaw(fsPath, doc, oldName, newName);
    },

    async deleteLens(name) {
      const doc = await readDoc(fsPath);
      return deleteLensRaw(fsPath, doc, name);
    }
  };
}
