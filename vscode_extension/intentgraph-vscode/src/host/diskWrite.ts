// Centralised IG file writes for full disk-I/O traceability.
//
// PIG OBSERVABILITY constraint #2 (extended): "Every file write to the IG path
// goes through a single wrapper that logs the caller and the selfWritePath
// state at the moment of write." Until this module landed, writes were
// scattered across autosave.ts / lensCrud.ts / yamlEdit.ts and the trace had no
// way to see which one was firing during a reload-loop investigation.
//
// Public API:
//   - registerTraceSink(sink) — called once from IntentGraphEditorProvider per
//     panel construction. The sink emits `{src:'host', kind:'fileWrite', ...}`.
//   - writeIgFile({fsPath, content, caller, tmp?}) — single write entrypoint.
//     Use for ALL writes to the IG file or its tmp neighbours. Emits a trace
//     entry then delegates to fs.promises.writeFile.

import { writeFile } from 'node:fs/promises';

import type { TraceEntry } from '../messaging/messageTypes';

// We don't import TraceSink directly because that would create a circular
// dependency with src/editor/. Instead we accept a minimal write callback.
type TraceWriter = (entry: TraceEntry) => void;

let _traceWrite: TraceWriter | null = null;
let _hostSeq = 0;

/**
 * Register the host-side trace writer. Idempotent — calling again replaces.
 * Pass `null` to deregister (e.g. on panel disposal, though writes from
 * disposed-panel paths are rare and harmless).
 */
export function registerTraceSink(writer: TraceWriter | null): void {
  _traceWrite = writer;
}

export interface WriteIgFileArgs {
  /** Absolute path being written. */
  fsPath: string;
  /** Content to write (utf8). */
  content: string;
  /**
   * Logical caller, e.g. 'autosave.createDefaultLens', 'lensCrud.create',
   * 'yamlEdit.applyFieldEdit', 'yamlEdit.tmpValidate'. Used as the trace
   * `cause` field so a reader can grep one source of writes instantly.
   */
  caller: string;
  /**
   * True if this is a throwaway temp file (e.g. ig-tool validate target).
   * Helps distinguish "real" writes from validation scratchpads in the trace.
   */
  tmp?: boolean;
  /**
   * Did the caller set entry.selfWritePath BEFORE this write? Caller passes
   * the boolean so the trace records it; the wrapper does not consult any
   * shared state. If undefined, the trace records `null`.
   */
  selfWritePathSet?: boolean;
}

/**
 * Write a file and emit one fileWrite trace entry. Mirrors `fs.promises.writeFile`
 * semantics (always utf8). Errors propagate to the caller — the wrapper does not
 * swallow them; it just emits the trace and lets the caller's existing try/catch
 * handle failures.
 */
export async function writeIgFile(args: WriteIgFileArgs): Promise<void> {
  if (_traceWrite) {
    try {
      _traceWrite({
        ts: new Date().toISOString(),
        seq: _hostSeq++,
        src: 'host',
        kind: 'fileWrite',
        cause: args.caller,
        data: {
          path: args.fsPath,
          bytes: args.content.length,
          tmp: args.tmp === true,
          selfWritePathSet: args.selfWritePathSet ?? null
        }
      });
    } catch {
      // Never let trace failures break a real write.
    }
  }
  await writeFile(args.fsPath, args.content, 'utf8');
}
