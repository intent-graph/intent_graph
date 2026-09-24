/**
 * Regression test for Bug A: autosavePersistPosition
 * self-write flag ordering.
 *
 * Verifies:
 *  - PERSISTENCE.AUTOSAVE constraint #4: selfWritePath set BEFORE any await on writeFile
 *  - Bug A fix: move selfWritePath = fsPath to TOP of try block, not after write
 *
 * From PIG: "Self-write suppression: selfWritePath flag MUST be set BEFORE any await
 * on writeFile, not after. Setting after-write causes the watcher to fire before the
 * flag is in place, producing a reload loop."
 *
 * This test uses static analysis: read the source file and assert that
 * selfWritePath assignment appears before the write call in autosavePersistPosition.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

test('PERSISTENCE.AUTOSAVE (Bug A): selfWritePath set before try block', () => {
  const srcPath = fileURLToPath(new URL('../../src/editor/IntentGraphEditorProvider.ts', import.meta.url));
  const src = readFileSync(srcPath, 'utf8');

  // Find the autosavePersistPosition method body.
  // Match from "private async autosavePersistPosition" to the closing "}" at the start of a line.
  const methodMatch = src.match(/private async autosavePersistPosition[\s\S]*?^  \}/m);
  assert.ok(methodMatch, 'autosavePersistPosition method not found');
  const body = methodMatch[0];

  // The correct pattern: selfWritePath is set BEFORE the try block.
  // Bug A was setting it AFTER parseAndMutateLensPosition (which has await inside).
  // Bug A fix: move to before try block, set at method entry point.
  //
  // Verify: selfWritePath = fsPath comes before try {
  const selfWriteAssignIdx = body.indexOf('entry.selfWritePath = fsPath');
  const tryBlockIdx = body.indexOf('try {');

  assert.ok(selfWriteAssignIdx > -1, 'selfWritePath assignment not found');
  assert.ok(tryBlockIdx > -1, 'try block not found');

  // selfWritePath assignment must come BEFORE the try block.
  assert.ok(
    selfWriteAssignIdx < tryBlockIdx,
    `selfWritePath must be set before try block (before any awaits). selfWritePath at ${selfWriteAssignIdx}, try at ${tryBlockIdx}.`
  );
});

test('PERSISTENCE.AUTOSAVE (Bug A): selfWritePath cleared on failure', () => {
  const srcPath = fileURLToPath(new URL('../../src/editor/IntentGraphEditorProvider.ts', import.meta.url));
  const src = readFileSync(srcPath, 'utf8');

  // Find the autosavePersistPosition method body.
  const methodMatch = src.match(/private async autosavePersistPosition[\s\S]*?^  \}/m);
  assert.ok(methodMatch, 'autosavePersistPosition method not found');
  const body = methodMatch[0];

  // Count how many times we clear the flag on failure.
  // Pattern: entry.selfWritePath = null; on error paths.
  const clearMatches = body.match(/entry\.selfWritePath = null/g) || [];
  assert.ok(clearMatches.length >= 3,
    `selfWritePath should be cleared on failure (found ${clearMatches.length} clears, expected >= 3 for createDefaultLens error, parseAndMutateLensPosition error, and catch block)`);
});
