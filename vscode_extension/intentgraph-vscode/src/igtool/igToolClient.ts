// Thin wrapper around `ig-tool` invocations via child_process.execFile.
// Surface: resolveIgToolPath, runIgTool, withTempOutput, ping.
// queryNode/igToolQueries removed — node content arrives in the
// initial LoadGraphResponse (no lazy fetch on tap).

import { execFile } from 'child_process';
import { promisify } from 'util';
import { mkdtemp, rm } from 'fs/promises';
import { join } from 'path';
import { tmpdir } from 'os';
import * as vscode from 'vscode';

import type { PingResponse } from '../messaging/messageTypes';

const execFileAsync = promisify(execFile);

export interface RunOptions {
  cwd?: string;
  signal?: AbortSignal;
  timeoutMs?: number;
}

export interface RunResult {
  stdout: string;
  stderr: string;
  code: number;
}

const DEFAULT_TIMEOUT_MS = 30_000;

export class IgToolClient {
  /** Reads `intentgraph.igToolPath`; falls back to `ig-tool` (PATH lookup). */
  resolveIgToolPath(): string {
    const cfg = vscode.workspace.getConfiguration('intentgraph');
    const explicit = cfg.get<string>('igToolPath', '');
    if (explicit && explicit.trim().length > 0) {
      return explicit.trim();
    }
    return 'ig-tool';
  }

  /** Run ig-tool with arbitrary args. NEVER uses a shell. */
  async runIgTool(args: string[], opts: RunOptions = {}): Promise<RunResult> {
    const bin = this.resolveIgToolPath();
    const timeout = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    try {
      const { stdout, stderr } = await execFileAsync(bin, args, {
        cwd: opts.cwd,
        signal: opts.signal,
        timeout,
        windowsHide: true
      });
      return { stdout, stderr, code: 0 };
    } catch (err) {
      const e = err as NodeJS.ErrnoException & { code?: string | number; stdout?: string; stderr?: string };
      const code = typeof e.code === 'number' ? e.code : 1;
      return {
        stdout: e.stdout ?? '',
        stderr: e.stderr ?? String(e.message ?? e),
        code
      };
    }
  }

  /**
   * Allocate a unique temp directory, run `fn(outPath)`, always clean up.
   * Retained for future host-side ig-tool invocations.
   */
  async withTempOutput<T>(fn: (outPath: string) => Promise<T>): Promise<T> {
    const dir = await mkdtemp(join(tmpdir(), 'ig-'));
    const outPath = join(dir, 'out.yaml');
    try {
      return await fn(outPath);
    } finally {
      await rm(dir, { recursive: true, force: true }).catch(() => {
        /* swallow cleanup errors */
      });
    }
  }

  /** Smoke-test: run `ig-tool --help` and report whether the binary is reachable. */
  async ping(): Promise<PingResponse> {
    const bin = this.resolveIgToolPath();
    try {
      await execFileAsync(bin, ['--help'], { timeout: 10_000, windowsHide: true });
      return { ok: true, igToolFound: true };
    } catch (err) {
      const e = err as NodeJS.ErrnoException;
      if (e.code === 'ENOENT') {
        return {
          ok: false,
          igToolFound: false,
          error: `ig-tool not found at "${bin}". Set intentgraph.igToolPath or add it to your PATH.`
        };
      }
      return {
        ok: false,
        igToolFound: false,
        error: String(e.message ?? e)
      };
    }
  }
}
