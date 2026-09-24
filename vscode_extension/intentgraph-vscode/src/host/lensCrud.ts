// Lens CRUD operations (create, rename, delete) for the host.
// Mirrors the YAMLMap-aware pattern in autosave.ts so YAML structure is
// preserved across mutations (no comment loss, no key reordering).
//
// PIG LENS_UI.CTRLPANEL.{2,3,4} — every CRUD op writes through parseDocument +
// setIn/deleteIn + toString + writeFile, the same cycle as autosave. The host
// caller is responsible for setting selfWritePath BEFORE the write so the
// file-watcher reload is suppressed (mirrors autosavePersistPosition).

import * as YAML from 'yaml';
import { computeFileHash } from './fileHash';
import { writeIgFile } from './diskWrite';

export interface LensCrudResult {
  ok: boolean;
  error?: string;
  newFileHash?: string;
}

/**
 * Validation for lens names. Names live as YAML map keys; we forbid characters
 * that would force quoting or special parsing (whitespace, leading/trailing
 * dots, control characters). Length is bounded so dropdown chrome remains tidy.
 */
export function isValidLensName(name: string): boolean {
  if (typeof name !== 'string') return false;
  const trimmed = name.trim();
  if (trimmed.length === 0) return false;
  if (trimmed.length > 64) return false;
  // Disallow whitespace, dots, slashes, colons, and control chars in names.
  // A pragmatic regex: keep names simple alphanumerics + - and _.
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(trimmed)) return false;
  return true;
}

/**
 * Topology subset needed to seed a new lens with the canonical default
 * membership `{ROOT, ROOT.children}`. PIG `LENSSCHEMA.VISIBILITY` constraint:
 * "New lens default membership: ROOT plus its direct children. ROOT renders
 * expanded; each L1 compound renders collapsed."
 */
export interface NewLensTopology {
  rootUid: string;
  childrenOfRoot: ReadonlyArray<string>;
}

/**
 * Create a new named lens. Auto-activates by setting meta.default_lens
 * to the new name (so a reload re-applies it).
 *
 * The new lens is seeded with `{rootUid, ...childrenOfRoot}` per the PIG
 * `LENSSCHEMA.VISIBILITY` default-membership rule: this gives the user the
 * top-level structure (root expanded; L1 compounds collapsed) as the
 * starting point, instead of the prior empty-lens behaviour where applyLens
 * fell back to "everything expanded."
 */
export async function createLens(
  fsPath: string,
  doc: YAML.Document,
  name: string,
  topology: NewLensTopology
): Promise<LensCrudResult> {
  try {
    if (!isValidLensName(name)) {
      return { ok: false, error: `Invalid lens name: '${name}'.` };
    }

    if (!doc.has('lenses')) {
      doc.set('lenses', new YAML.YAMLMap());
    }
    if (doc.hasIn(['lenses', name])) {
      return { ok: false, error: `Lens '${name}' already exists.` };
    }

    // Seed nodes with {rootUid, ...childrenOfRoot}. lod 'lean' for all;
    // position omitted (ELK will lay them out fresh on first apply).
    const seedNodes: Record<string, { lod: string }> = {
      [topology.rootUid]: { lod: 'lean' }
    };
    for (const childUid of topology.childrenOfRoot) {
      seedNodes[childUid] = { lod: 'lean' };
    }
    doc.setIn(['lenses', name], { name, nodes: seedNodes });

    if (!doc.has('meta')) {
      doc.set('meta', new YAML.YAMLMap());
    }
    doc.setIn(['meta', 'default_lens'], name);

    const newContent = doc.toString();
    const newHash = computeFileHash(newContent);
    await writeIgFile({ fsPath, content: newContent, caller: 'lensCrud.createLens' });
    return { ok: true, newFileHash: newHash };
  } catch (err) {
    return {
      ok: false,
      error: `Cannot create lens: ${err instanceof Error ? err.message : String(err)}`
    };
  }
}

/**
 * Rename a lens. Updates the lens dict key, the lens's `name` field, and
 * meta.default_lens if the renamed lens was the default.
 */
export async function renameLens(
  fsPath: string,
  doc: YAML.Document,
  oldName: string,
  newName: string
): Promise<LensCrudResult> {
  try {
    if (!isValidLensName(newName)) {
      return { ok: false, error: `Invalid new lens name: '${newName}'.` };
    }
    if (oldName === newName) {
      return { ok: false, error: 'Old and new lens names are identical.' };
    }
    if (!doc.hasIn(['lenses', oldName])) {
      return { ok: false, error: `Lens '${oldName}' does not exist.` };
    }
    if (doc.hasIn(['lenses', newName])) {
      return { ok: false, error: `Lens '${newName}' already exists.` };
    }

    // Read the existing lens config, write under the new key, delete the old.
    // Using getIn returns the YAML node; we re-set it via plain object so the
    // serialiser writes a clean nested mapping.
    const existing = doc.getIn(['lenses', oldName], /* keepScalar */ true);
    // Mutate the lens's `name` field to match its new key (self-documentation).
    if (existing && typeof existing === 'object' && 'set' in existing) {
      // YAMLMap path
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (existing as any).set('name', newName);
      } catch {
        /* ignore — not a YAMLMap */
      }
    }
    doc.setIn(['lenses', newName], existing);
    doc.deleteIn(['lenses', oldName]);

    // Update meta.default_lens if needed.
    const currentDefault = doc.getIn(['meta', 'default_lens']);
    if (currentDefault === oldName) {
      doc.setIn(['meta', 'default_lens'], newName);
    }

    const newContent = doc.toString();
    const newHash = computeFileHash(newContent);
    await writeIgFile({ fsPath, content: newContent, caller: 'lensCrud.renameLens' });
    return { ok: true, newFileHash: newHash };
  } catch (err) {
    return {
      ok: false,
      error: `Cannot rename lens: ${err instanceof Error ? err.message : String(err)}`
    };
  }
}

/**
 * Delete a lens. Unsets meta.default_lens if the deleted lens was the default.
 */
export async function deleteLens(
  fsPath: string,
  doc: YAML.Document,
  name: string
): Promise<LensCrudResult> {
  try {
    if (!doc.hasIn(['lenses', name])) {
      return { ok: false, error: `Lens '${name}' does not exist.` };
    }

    doc.deleteIn(['lenses', name]);

    const currentDefault = doc.getIn(['meta', 'default_lens']);
    if (currentDefault === name) {
      doc.deleteIn(['meta', 'default_lens']);
    }

    const newContent = doc.toString();
    const newHash = computeFileHash(newContent);
    await writeIgFile({ fsPath, content: newContent, caller: 'lensCrud.deleteLens' });
    return { ok: true, newFileHash: newHash };
  } catch (err) {
    return {
      ok: false,
      error: `Cannot delete lens: ${err instanceof Error ? err.message : String(err)}`
    };
  }
}
