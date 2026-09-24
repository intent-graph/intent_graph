// TraceSink — host-side structured trace writer.
// PIG OBSERVABILITY constraints #5–#7.
//
// Writes one JSONL file per panel session. Rotates: keeps at most 5 files.
// Path resolution: configuredPath → <workspace>/.intentgraph-traces/ → <extensionDir>/test/traces/.
// Symlinks latest.jsonl to current file; falls back to a regular-file copy on failure.

import * as fs from 'node:fs';
import * as fsp from 'node:fs/promises';
import * as path from 'node:path';
import type * as vscode from 'vscode';

import type { TraceEntry } from '../messaging/messageTypes';

export interface TraceSinkOptions {
  /** vscode.workspace.workspaceFolders[0]?.uri.fsPath */
  workspaceFolder: string | undefined;
  /** Path to the extension repo (for fallback traces dir). */
  extensionDir: string;
  /** intentgraph.trace.path setting; may be undefined or empty. */
  configuredPath: string | undefined;
  enabled: boolean;
  /** For one-shot disable-on-error reporting. */
  outputChannel: vscode.OutputChannel;
  /** vscode.version */
  vscodeVersion: string;
}

/**
 * Pure helper: given a list of filenames sorted oldest-first, returns the prefix
 * that must be deleted to keep at most `maxKeep` files.
 *
 * Input MUST be sorted oldest-first (i.e. ascending by mtime or by ISO timestamp
 * in filename). Returns the prefix of the input that should be deleted.
 */
export function filesToDelete(files: string[], maxKeep: number): string[] {
  if (files.length <= maxKeep) return [];
  return files.slice(0, files.length - maxKeep);
}

export class TraceSink {
  private readonly opts: TraceSinkOptions;
  private traceDir = '';
  private traceFile = '';
  private latestLink = '';
  private disabled = false;
  private seq = 0;

  // Single-flight Promise chain: every write appends after the previous completes.
  private queue: Promise<void> = Promise.resolve();

  constructor(opts: TraceSinkOptions) {
    this.opts = opts;

    if (!opts.enabled) {
      this.disabled = true;
      return;
    }

    // Resolve trace directory.
    if (opts.configuredPath && opts.configuredPath.trim().length > 0) {
      this.traceDir = opts.configuredPath.trim();
    } else if (opts.workspaceFolder) {
      this.traceDir = path.join(opts.workspaceFolder, '.intentgraph-traces');
    } else {
      this.traceDir = path.join(opts.extensionDir, 'test', 'traces');
    }

    // Build session filename using ISO timestamp with colons replaced by dashes.
    const isoNow = new Date().toISOString().replace(/:/g, '-').replace(/\.\d+Z$/, 'Z');
    this.traceFile = path.join(this.traceDir, `trace-${isoNow}.jsonl`);
    this.latestLink = path.join(this.traceDir, 'latest.jsonl');

    // Queue the async initialization.
    this.queue = this.queue.then(() => this.initialize());
  }

  private async initialize(): Promise<void> {
    try {
      // mkdir -p the trace directory.
      await fsp.mkdir(this.traceDir, { recursive: true });

      // Rotate: list all trace-*.jsonl, sort by mtime ascending, delete excess.
      await this.rotate();

      // Write sessionStart entry (schemaVersion inline in first line).
      const entry: TraceEntry & { schemaVersion: number } = {
        schemaVersion: 1,
        ts: new Date().toISOString(),
        seq: this.seq++,
        src: 'host',
        kind: 'sessionStart',
        data: {
          pid: process.pid,
          vscodeVersion: this.opts.vscodeVersion,
          // Include the resolved path + which fallback fired.
          // Lets a reader confirm at a glance which directory the trace is
          // landing in and whether configured/workspace/extensionDir won.
          traceDir: this.traceDir,
          pathSource:
            this.opts.configuredPath && this.opts.configuredPath.trim().length > 0
              ? 'configured'
              : this.opts.workspaceFolder
                ? 'workspaceFolder'
                : 'extensionDirFallback',
          traceFile: this.traceFile
        }
      };
      await fsp.appendFile(this.traceFile, JSON.stringify(entry) + '\n', 'utf8');

      // Update latest.jsonl symlink.
      await this.updateLatestLink();
    } catch (err) {
      this.reportError(err);
    }
  }

  private async rotate(): Promise<void> {
    try {
      const entries = await fsp.readdir(this.traceDir);
      const traceFiles = entries.filter((f) => /^trace-.*\.jsonl$/.test(f));

      if (traceFiles.length === 0) return;

      // Get mtime for each file, sort ascending (oldest first).
      const withMtime = await Promise.all(
        traceFiles.map(async (f) => {
          try {
            const stat = await fsp.stat(path.join(this.traceDir, f));
            return { name: f, mtime: stat.mtimeMs };
          } catch {
            return { name: f, mtime: 0 };
          }
        })
      );
      withMtime.sort((a, b) => a.mtime - b.mtime);
      const sortedNames = withMtime.map((e) => e.name);

      const toDelete = filesToDelete(sortedNames, 5);
      for (const f of toDelete) {
        try {
          await fsp.unlink(path.join(this.traceDir, f));
        } catch {
          /* ignore */
        }
      }
    } catch {
      /* ignore rotation errors — don't crash the session */
    }
  }

  private async updateLatestLink(): Promise<void> {
    // Try creating/replacing a symlink first.
    try {
      // Remove existing symlink or file.
      try { await fsp.unlink(this.latestLink); } catch { /* no existing */ }
      await fsp.symlink(this.traceFile, this.latestLink);
    } catch {
      // Symlink failed (e.g. Windows without dev-mode) — fall back to regular-file copy.
      try {
        await fsp.copyFile(this.traceFile, this.latestLink);
      } catch {
        /* ignore — don't crash session over latest.jsonl */
      }
    }
  }

  /** Append one trace entry to the JSONL file. No-op when disabled. */
  async write(entry: TraceEntry): Promise<void> {
    if (this.disabled) return;
    this.queue = this.queue.then(async () => {
      if (this.disabled) return;
      try {
        await fsp.appendFile(this.traceFile, JSON.stringify(entry) + '\n', 'utf8');
      } catch (err) {
        this.reportError(err);
      }
    });
    return this.queue;
  }

  /**
   * Emit a marker entry with `{kind:'mark', data:{label}}`.
   * Useful for manual user-invoked marks via the command palette.
   */
  async mark(label: string): Promise<void> {
    if (this.disabled) return;
    return this.write({
      ts: new Date().toISOString(),
      seq: this.seq++,
      src: 'host',
      kind: 'mark',
      data: { label }
    });
  }

  /**
   * Flush the write queue and update the latest.jsonl copy/symlink.
   * Call from panel disposal.
   */
  async close(): Promise<void> {
    if (this.disabled) return;
    // Emit a sessionEnd marker so a reader can tell whether
    // the panel was closed cleanly vs the trace being cut off mid-event.
    this.queue = this.queue.then(async () => {
      try {
        const entry: TraceEntry = {
          ts: new Date().toISOString(),
          seq: this.seq++,
          src: 'host',
          kind: 'sessionEnd'
        };
        await fsp.appendFile(this.traceFile, JSON.stringify(entry) + '\n', 'utf8');
      } catch {
        /* ignore — panel is already closing */
      }
    });
    this.queue = this.queue.then(async () => {
      // On systems where symlink worked at init, update the copy on close too.
      try {
        // Check if it's a real copy fallback: stat both and compare inodes.
        const traceStats = await fsp.stat(this.traceFile).catch(() => null);
        const latestStats = await fsp.stat(this.latestLink).catch(() => null);
        if (traceStats && latestStats && traceStats.ino !== latestStats.ino) {
          // It's a copy (not a symlink) — overwrite it with current content.
          await fsp.copyFile(this.traceFile, this.latestLink).catch(() => {/* ignore */});
        }
      } catch {
        /* ignore */
      }
    });
    return this.queue;
  }

  /** Get the current sequence number (for host-side entries). */
  nextSeq(): number {
    return this.seq++;
  }

  private reportError(err: unknown): void {
    if (this.disabled) return;
    const msg = err instanceof Error ? err.message : String(err);
    this.opts.outputChannel.appendLine(`[IntentGraph Trace] write error: ${msg} — trace disabled for this session.`);
    this.disabled = true;
  }
}

/**
 * Check if symlinks are supported in the given directory.
 * Returns true if a test symlink can be created.
 */
export function symlinksSupportedSync(dir: string): boolean {
  const testTarget = path.join(dir, '.symlink-test-target');
  const testLink = path.join(dir, '.symlink-test');
  try {
    fs.writeFileSync(testTarget, '');
    fs.symlinkSync(testTarget, testLink);
    fs.unlinkSync(testLink);
    fs.unlinkSync(testTarget);
    return true;
  } catch {
    try { fs.unlinkSync(testTarget); } catch { /* ignore */ }
    try { fs.unlinkSync(testLink); } catch { /* ignore */ }
    return false;
  }
}
