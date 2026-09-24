// Playwright config for the IntentGraph webview harness.
//
// Goals:
//   1. Serve the extension root (intentgraph-vscode/) over HTTP so the harness
//      can pull both /dist/webview/main.js (the bundled webview) and the harness
//      JS files at /test/playwright/harness/*.
//   2. Run `node esbuild.mjs` once before any test via globalSetup so dist/ is
//      always fresh against the source tree.
//   3. Chromium only — webview targets Electron Chromium in prod.

import { defineConfig } from '@playwright/test';
import { join } from 'node:path';

// __dirname is synthesised by Playwright's TS loader (CJS context).
const HERE = __dirname;
const EXTENSION_ROOT = join(HERE, '..', '..');

export default defineConfig({
  testDir: './specs',
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  timeout: 30_000,
  expect: { timeout: 5_000 },

  globalSetup: require.resolve('./globalSetup.ts'),

  webServer: {
    command: `node ${join(HERE, 'staticServer.mjs')} 5173 ${EXTENSION_ROOT}`,
    url: 'http://127.0.0.1:5173/test/playwright/harness/index.html',
    reuseExistingServer: !process.env.CI,
    timeout: 15_000,
    stdout: 'pipe',
    stderr: 'pipe'
  },

  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    viewport: { width: 1280, height: 800 },
    trace: 'retain-on-failure'
  },

  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' }
    }
  ]
});
