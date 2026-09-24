// Playwright globalSetup. Runs once before any spec.
//
// Responsibilities:
//   1. Build the webview bundle so /dist/webview/main.js exists and is fresh.
//      The harness loads the bundle directly via <script src>; without this
//      step, tests would silently run against a stale bundle (or 404).
//
// Skip the build if INTENTGRAPH_SKIP_BUILD=1 — useful for fast iteration
// when you've already run `npm run compile` in a watcher.

import { spawn } from 'node:child_process';
import { join } from 'node:path';

const HERE = __dirname;
const EXTENSION_ROOT = join(HERE, '..', '..');

async function runEsbuild(): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn('node', ['esbuild.mjs'], {
      cwd: EXTENSION_ROOT,
      stdio: 'inherit'
    });
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`esbuild exited with code ${code}`));
    });
    child.on('error', reject);
  });
}

export default async function globalSetup(): Promise<void> {
  if (process.env.INTENTGRAPH_SKIP_BUILD === '1') {
    console.log('[playwright globalSetup] INTENTGRAPH_SKIP_BUILD=1, skipping esbuild');
    return;
  }
  console.log('[playwright globalSetup] running esbuild...');
  await runEsbuild();
  console.log('[playwright globalSetup] esbuild done');
}
