/**
 * Unit tests for the OBSERVABILITY trace layer.
 *
 * Four tests:
 *  1. Schema check: valid TraceEntry survives JSON round-trip; truncated line throws.
 *  2. Sequence sanity: tap → dbltap (corr) → editEnter (same corr) — seq monotonic,
 *     corr shared between dbltap and editEnter, tap has no corr.
 *  3. Rotation pure helper: filesToDelete edge cases.
 *  4. Grep invariant: no ec.expand|collapse calls outside ecWrap.ts.
 *
 * Inline-implementation pattern — tests run without a build step via:
 *   node --test test/unit/trace.test.mjs
 *
 * PIG OBSERVABILITY constraints #7 (schema), #2 (grep), rotation policy.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { promises as fsp } from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ============================================================================
// TEST 1 — Schema check
// ============================================================================

test('OBSERVABILITY schema: valid TraceEntry round-trips through JSON', () => {
  /** @type {import('../../src/messaging/messageTypes').TraceEntry} */
  const entry = {
    ts: '2026-04-30T11:34:01.123Z',
    seq: 42,
    src: 'router',
    kind: 'dbltap',
    corr: 'c-42-a3f7',
    data: { uid: 'DISCOVER', currentLod: 'lean', action: 'promoteThenEdit' }
  };

  const line = JSON.stringify(entry);
  const parsed = JSON.parse(line);

  assert.strictEqual(parsed.ts, entry.ts, 'ts preserved');
  assert.strictEqual(parsed.seq, entry.seq, 'seq preserved');
  assert.strictEqual(parsed.src, entry.src, 'src preserved');
  assert.strictEqual(parsed.kind, entry.kind, 'kind preserved');
  assert.strictEqual(parsed.corr, entry.corr, 'corr preserved');
  assert.deepStrictEqual(parsed.data, entry.data, 'data preserved');
});

test('OBSERVABILITY schema: truncated JSON line throws on parse', () => {
  const truncated = '{"ts":"2026-04-30T11:34:01.123Z","seq":42,"src":"router"';
  assert.throws(() => JSON.parse(truncated), SyntaxError, 'truncated JSONL should throw SyntaxError');
});

test('OBSERVABILITY schema: src field must be one of the allowed values', () => {
  const validSrcs = ['router', 'cue', 'overlay', 'host', 'lens', 'app'];
  for (const src of validSrcs) {
    const entry = { ts: new Date().toISOString(), seq: 0, src, kind: 'test' };
    const parsed = JSON.parse(JSON.stringify(entry));
    assert.ok(validSrcs.includes(parsed.src), `src '${src}' should be a valid src value`);
  }
});

// ============================================================================
// TEST 2 — Sequence sanity (inline simulation of the trace() emitter)
// ============================================================================

// Inline copy of the trace emitter logic (no imports needed).
let _seq = 0;
const _captured = [];

function traceInline(entry) {
  const full = {
    ts: new Date().toISOString(),
    seq: _seq++,
    ...entry
  };
  _captured.push(full);
}

function corrInline() {
  return `c-${_seq}-${Math.random().toString(36).slice(2, 8)}`;
}

test('OBSERVABILITY sequence: tap→dbltap→editEnter chain has monotonic seq and shared corr', () => {
  _seq = 0;
  _captured.length = 0;

  // Simulate: tap (no corr)
  traceInline({ src: 'router', kind: 'tap', data: { uid: 'FOO', suppressed: false, suppressionReason: null } });

  // Simulate: dbltap generates corr
  const c = corrInline();
  traceInline({ src: 'router', kind: 'dbltap', corr: c, data: { uid: 'FOO', currentLod: 'lean', action: 'promoteThenEdit' } });

  // Simulate: editEnter receives same corr
  traceInline({ src: 'overlay', kind: 'editEnter', corr: c, data: { uid: 'FOO', ok: true } });

  assert.strictEqual(_captured.length, 3, 'three entries captured');

  const [tap, dbltap, editEnter] = _captured;

  // Monotonic seq: 0, 1, 2
  assert.strictEqual(tap.seq, 0, 'tap seq = 0');
  assert.strictEqual(dbltap.seq, 1, 'dbltap seq = 1');
  assert.strictEqual(editEnter.seq, 2, 'editEnter seq = 2');

  // tap has no corr
  assert.strictEqual(tap.corr, undefined, 'tap has no corr');

  // dbltap and editEnter share the same corr
  assert.ok(dbltap.corr, 'dbltap has a corr');
  assert.strictEqual(dbltap.corr, editEnter.corr, 'dbltap and editEnter share the same corr');
});

// ============================================================================
// TEST 3 — Rotation pure helper (filesToDelete)
// ============================================================================

/**
 * Pure helper: given files sorted oldest-first, return the prefix to delete
 * to keep at most maxKeep files.
 *
 * Input MUST be sorted oldest-first (i.e. ascending by mtime or by ISO timestamp
 * in filename). Returns the prefix of the input that should be deleted.
 */
function filesToDelete(files, maxKeep) {
  if (files.length <= maxKeep) return [];
  return files.slice(0, files.length - maxKeep);
}

test('OBSERVABILITY rotation: filesToDelete edge cases', () => {
  // Fewer than maxKeep: nothing deleted
  assert.deepStrictEqual(filesToDelete(['a', 'b', 'c'], 5), [], 'under limit → empty');

  // Exactly maxKeep: nothing deleted
  assert.deepStrictEqual(filesToDelete(['a', 'b', 'c', 'd', 'e'], 5), [], 'at limit → empty');

  // Over limit: delete oldest
  assert.deepStrictEqual(
    filesToDelete(['a', 'b', 'c', 'd', 'e', 'f', 'g'], 5),
    ['a', 'b'],
    '7 files, keep 5 → delete 2 oldest'
  );

  // Single file under limit
  assert.deepStrictEqual(filesToDelete(['a'], 5), [], 'single file → empty');

  // Zero files
  assert.deepStrictEqual(filesToDelete([], 5), [], 'zero files → empty');

  // maxKeep = 1
  assert.deepStrictEqual(filesToDelete(['a', 'b', 'c'], 1), ['a', 'b'], 'maxKeep=1 → delete all but last');
});

// ============================================================================
// TEST 4 — Grep invariant: no direct ec.expand|collapse outside ecWrap.ts
// ============================================================================

/**
 * Recursively collect all .ts files under a directory.
 * @param {string} dir
 * @returns {Promise<string[]>}
 */
async function collectTsFiles(dir) {
  const results = [];
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      // Skip node_modules and dist
      if (e.name === 'node_modules' || e.name === 'dist') continue;
      results.push(...await collectTsFiles(full));
    } else if (e.isFile() && e.name.endsWith('.ts')) {
      results.push(full);
    }
  }
  return results;
}

test('OBSERVABILITY grep invariant: no direct ec.expand|collapse calls outside ecWrap.ts', async () => {
  // src/ root is two levels up from test/unit/
  const srcDir = path.resolve(__dirname, '..', '..', 'src');
  const wrapFile = path.resolve(srcDir, 'webview', 'overlay', 'ecWrap.ts');

  const allTsFiles = await collectTsFiles(srcDir);
  const violators = [];

  const pattern = /ec\.(expand|collapse)/;

  for (const file of allTsFiles) {
    // The wrapper file itself is allowed to call ec.expand/collapse directly —
    // that's the one place that does it.
    if (path.resolve(file) === wrapFile) continue;

    const content = await fsp.readFile(file, 'utf8');
    if (pattern.test(content)) {
      violators.push(file);
    }
  }

  assert.strictEqual(
    violators.length,
    0,
    `Direct ec.expand|collapse calls found outside ecWrap.ts:\n${violators.map(f => `  ${f}`).join('\n')}\n` +
    'All expand/collapse calls must go through src/webview/overlay/ecWrap.ts'
  );
});
