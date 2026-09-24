// esbuild build script for the IntentGraph VS Code extension.
// Two entry points:
//   1. src/extension.ts -> dist/extension.js   (extension host: node18, cjs)
//   2. src/webview/main.ts -> dist/webview/main.js  (webview: es2020, browser, iife)

import { build, context } from 'esbuild';
import { copyFile, mkdir } from 'fs/promises';
import { dirname } from 'path';

const watch = process.argv.includes('--watch');
const production = process.argv.includes('--production');

async function copyStatic() {
  const target = 'dist/webview/styles.css';
  await mkdir(dirname(target), { recursive: true });
  await copyFile('src/webview/styles.css', target);
}

/** @type {import('esbuild').BuildOptions} */
const extensionConfig = {
  entryPoints: ['src/extension.ts'],
  bundle: true,
  platform: 'node',
  target: 'node18',
  format: 'cjs',
  outfile: 'dist/extension.js',
  external: ['vscode'],
  sourcemap: !production,
  minify: production,
  logLevel: 'info'
};

/** @type {import('esbuild').BuildOptions} */
const webviewConfig = {
  entryPoints: ['src/webview/main.ts'],
  bundle: true,
  platform: 'browser',
  target: 'es2020',
  format: 'iife',
  outfile: 'dist/webview/main.js',
  loader: { '.css': 'text' },
  sourcemap: !production,
  minify: production,
  logLevel: 'info'
};

async function run() {
  await copyStatic();
  if (watch) {
    const ctxExt = await context(extensionConfig);
    const ctxWeb = await context(webviewConfig);
    await Promise.all([ctxExt.watch(), ctxWeb.watch()]);
    console.log('[esbuild] watching for changes...');
  } else {
    await Promise.all([build(extensionConfig), build(webviewConfig)]);
    console.log('[esbuild] build complete');
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
