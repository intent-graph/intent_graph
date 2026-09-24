// YAML round-trip edit helper for IntentGraph files.
// Uses `eemeli/yaml` parseDocument (CST-preserving) so comments, anchors, and
// ordering are retained; only the mutated field value changes.
//
// Public API:
//   applyFieldEdit(uri, req, validateOnWrite?) → EditFieldResponse
//
// Constraints:
//   - No vscode.* imports except vscode.Uri (host only; no webview leak).
//   - CRLF normalisation in computeFileHash prevents Windows hash mismatches.
//   - Reads file once per call; no caching.
//   - Optional execFile post-write validation (validateOnWrite setting, default false).

import { readFile, unlink } from 'node:fs/promises';
import { execFile as _execFile } from 'node:child_process';
import { promisify } from 'node:util';
import * as YAML from 'yaml';

import type { EditFieldPayload, EditFieldResponse, EditNodePayload, EditNodeResponse } from '../messaging/messageTypes';
import { computeFileHash } from './fileHash';
import { writeIgFile } from './diskWrite';

const execFileAsync = promisify(_execFile);

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Linear scan: return the index of the node with the given uid in the `nodes:` sequence.
 *  Returns -1 if not found or if nodes is not a YAML sequence. */
function findNodeIndex(doc: YAML.Document, uid: string): number {
  const seq = doc.getIn(['nodes']) as YAML.YAMLSeq | undefined;
  if (!seq) return -1;
  for (let i = 0; i < seq.items.length; i++) {
    const item = seq.items[i] as YAML.YAMLMap | undefined;
    if (item?.get('uid') === uid) return i;
  }
  return -1;
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export interface ApplyFieldEditOptions {
  /** If true, run `ig-tool validate -g <tmp>` before persisting.
   *  Default false. ~300–800 ms per call (Python cold-start). */
  validateOnWrite?: boolean;
  /** Absolute path to ig-tool binary. Defaults to PATH lookup ("ig-tool"). */
  igToolPath?: string;
}

/**
 * Validate and apply a field edit to an IntentGraph YAML file.
 *
 * Pipeline:
 *   Stage 1 — schema check (sync, no I/O).
 *   Stage 2 — read file, hash check.
 *   Stage 3 — parseDocument, setIn, toString, write.
 *   Stage 3b (optional) — subprocess validation via ig-tool.
 *
 * Returns EditFieldResponse.  On ok=true, newFileHash contains the SHA-256
 * of the newly written content, normalised to LF.
 *
 * The caller in IntentGraphEditorProvider is responsible for setting the
 * selfWritePath flag BEFORE calling this (race-safe: flag is set before await).
 */
export async function applyFieldEdit(
  fsPath: string,
  req: EditFieldPayload,
  opts: ApplyFieldEditOptions = {}
): Promise<EditFieldResponse & { newContent?: string }> {
  // ── Stage 1: schema check ──────────────────────────────────────────────

  const trimmedNew = req.newValue.trim();
  if (trimmedNew.length === 0) {
    return { ok: false, error: `Field "${req.field}" must not be empty.` };
  }

  if (req.field === 'constraint') {
    if (typeof req.constraintIndex !== 'number' || !Number.isInteger(req.constraintIndex) || req.constraintIndex < 0) {
      return { ok: false, error: 'constraintIndex must be a non-negative integer.' };
    }
  }

  // ── Stage 2: read + hash check ────────────────────────────────────────

  let raw: string;
  try {
    raw = await readFile(fsPath, 'utf8');
  } catch (err) {
    return { ok: false, error: `Cannot read file: ${(err as Error).message}` };
  }

  const onDiskHash = computeFileHash(raw);
  if (onDiskHash !== req.fileHash) {
    return {
      ok: false,
      error: 'File changed externally — reload first.'
    };
  }

  // ── Stage 3: parse → mutate → serialise ───────────────────────────────

  let doc: YAML.Document;
  try {
    doc = YAML.parseDocument(raw);
  } catch (err) {
    return { ok: false, error: `YAML parse error: ${(err as Error).message}` };
  }

  const idx = findNodeIndex(doc, req.nodeUid);
  if (idx === -1) {
    return { ok: false, error: `Node "${req.nodeUid}" not found in YAML.` };
  }

  // Apply mutation.
  if (req.field === 'constraint') {
    const constraintSeq = doc.getIn(['nodes', idx, 'constraints']) as YAML.YAMLSeq | undefined;
    if (!constraintSeq) {
      return { ok: false, error: `Node "${req.nodeUid}" has no constraints array.` };
    }
    const ci = req.constraintIndex!;
    if (ci >= constraintSeq.items.length) {
      return { ok: false, error: `Constraint index ${ci} out of range (length ${constraintSeq.items.length}).` };
    }
    doc.setIn(['nodes', idx, 'constraints', ci], trimmedNew);
  } else {
    // 'name' or 'intent'
    doc.setIn(['nodes', idx, req.field], trimmedNew);
  }

  // Read-back assertion (non-fatal guard per §21 Risk 2).
  const readback = doc.getIn(
    req.field === 'constraint'
      ? ['nodes', idx, 'constraints', req.constraintIndex!]
      : ['nodes', idx, req.field]
  );
  if (readback !== trimmedNew) {
    // eslint-disable-next-line no-console
    console.warn('[intentgraph] yamlEdit: setIn readback mismatch', { readback, trimmedNew });
  }

  // KNOWN LIMITATION: parseDocument round-trips preserve comments, anchors,
  // and key ordering, but eemeli/yaml re-folds block scalars at the configured
  // lineWidth. For files authored with hand-tuned line wrapping this can
  // produce a larger diff than the single-field change. Phase 2 may revisit
  // with a line-patching strategy if git-minimal diffs become a hard
  // requirement; for Phase 1 the structural correctness of parseDocument is
  // the primary contract.
  const newContent = doc.toString();
  const newHash = computeFileHash(newContent);

  // ── Stage 3b (optional): subprocess validation ────────────────────────

  if (opts.validateOnWrite) {
    const tmpPath = fsPath + '.tmp-validate';
    try {
      await writeIgFile({ fsPath: tmpPath, content: newContent, caller: 'yamlEdit.applyFieldEdit.tmpValidate', tmp: true });
    } catch (err) {
      return { ok: false, error: `Cannot write temp file: ${(err as Error).message}` };
    }
    try {
      const igTool = opts.igToolPath?.trim() || 'ig-tool';
      await execFileAsync(igTool, ['validate', '-g', tmpPath]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      await unlink(tmpPath).catch(() => undefined);
      return { ok: false, error: `Validation failed: ${msg}` };
    }
    await unlink(tmpPath).catch(() => undefined);
  }

  // ── Write ──────────────────────────────────────────────────────────────

  try {
    await writeIgFile({ fsPath, content: newContent, caller: 'yamlEdit.applyFieldEdit' });
  } catch (err) {
    return { ok: false, error: `Cannot write file: ${(err as Error).message}` };
  }

  return { ok: true, newFileHash: newHash, newContent };
}

/**
 * Apply a multi-field node edit atomically in one parseDocument/toString/writeFile cycle.
 * All non-empty fields in `req.fields` are written; empty strings are silently skipped
 * (treated as "no change" for that field).
 *
 * Same three-stage pipeline as applyFieldEdit (schema check → hash check → parse/mutate/write).
 */
export async function applyNodeEdit(
  fsPath: string,
  req: EditNodePayload,
  opts: ApplyFieldEditOptions = {}
): Promise<EditNodeResponse & { newContent?: string }> {
  // ── Stage 1: schema check ──────────────────────────────────────────────

  const { fields } = req;
  const trimmedName = fields.name?.trim();
  const trimmedIntent = fields.intent?.trim();
  const trimmedEpistemic = fields.epistemic_state?.trim();

  if (trimmedName !== undefined && trimmedName.length === 0) {
    return { ok: false, error: 'Field "name" must not be empty.' };
  }
  if (trimmedIntent !== undefined && trimmedIntent.length === 0) {
    return { ok: false, error: 'Field "intent" must not be empty.' };
  }
  if (trimmedEpistemic !== undefined && trimmedEpistemic.length === 0) {
    return { ok: false, error: 'Field "epistemic_state" must not be empty.' };
  }
  if (fields.constraints !== undefined) {
    for (let i = 0; i < fields.constraints.length; i++) {
      if (fields.constraints[i].trim().length === 0) {
        return { ok: false, error: `Constraint[${i}] must not be empty.` };
      }
    }
  }

  // Nothing to write?
  const hasName = trimmedName !== undefined;
  const hasIntent = trimmedIntent !== undefined;
  const hasEpistemic = trimmedEpistemic !== undefined;
  const hasConstraints = fields.constraints !== undefined && fields.constraints.length > 0;
  if (!hasName && !hasIntent && !hasEpistemic && !hasConstraints) {
    return { ok: false, error: 'No fields to update.' };
  }

  // ── Stage 2: read + hash check ────────────────────────────────────────

  let raw: string;
  try {
    raw = await readFile(fsPath, 'utf8');
  } catch (err) {
    return { ok: false, error: `Cannot read file: ${(err as Error).message}` };
  }

  const onDiskHash = computeFileHash(raw);
  if (onDiskHash !== req.fileHash) {
    return { ok: false, error: 'File changed externally — reload first.' };
  }

  // ── Stage 3: parse → mutate all fields → serialise ────────────────────

  let doc: YAML.Document;
  try {
    doc = YAML.parseDocument(raw);
  } catch (err) {
    return { ok: false, error: `YAML parse error: ${(err as Error).message}` };
  }

  const idx = findNodeIndex(doc, req.nodeUid);
  if (idx === -1) {
    return { ok: false, error: `Node "${req.nodeUid}" not found in YAML.` };
  }

  // Apply each field mutation.
  if (hasName) {
    doc.setIn(['nodes', idx, 'name'], trimmedName!);
  }
  if (hasIntent) {
    doc.setIn(['nodes', idx, 'intent'], trimmedIntent!);
  }
  if (hasEpistemic) {
    doc.setIn(['nodes', idx, 'epistemic_state'], trimmedEpistemic!);
  }
  if (hasConstraints) {
    const constraintSeq = doc.getIn(['nodes', idx, 'constraints']) as YAML.YAMLSeq | undefined;
    if (!constraintSeq) {
      return { ok: false, error: `Node "${req.nodeUid}" has no constraints array.` };
    }
    for (let ci = 0; ci < fields.constraints!.length; ci++) {
      if (ci >= constraintSeq.items.length) break;  // do not extend beyond existing length
      doc.setIn(['nodes', idx, 'constraints', ci], fields.constraints![ci].trim());
    }
  }

  const newContent = doc.toString();
  const newHash = computeFileHash(newContent);

  // ── Stage 3b (optional): subprocess validation ────────────────────────

  if (opts.validateOnWrite) {
    const tmpPath = fsPath + '.tmp-validate';
    try {
      await writeIgFile({ fsPath: tmpPath, content: newContent, caller: 'yamlEdit.applyNodeEdit.tmpValidate', tmp: true });
    } catch (err) {
      return { ok: false, error: `Cannot write temp file: ${(err as Error).message}` };
    }
    try {
      const igTool = opts.igToolPath?.trim() || 'ig-tool';
      await execFileAsync(igTool, ['validate', '-g', tmpPath]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      await unlink(tmpPath).catch(() => undefined);
      return { ok: false, error: `Validation failed: ${msg}` };
    }
    await unlink(tmpPath).catch(() => undefined);
  }

  // ── Write ──────────────────────────────────────────────────────────────

  try {
    await writeIgFile({ fsPath, content: newContent, caller: 'yamlEdit.applyNodeEdit' });
  } catch (err) {
    return { ok: false, error: `Cannot write file: ${(err as Error).message}` };
  }

  return { ok: true, newFileHash: newHash, newContent };
}
