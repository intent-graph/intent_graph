/**
 * Unit tests for the whole-node edit field collector and the epistemic-state
 * risk predicate (epistemic_state made editable).
 *
 * Covers:
 *   - collectChangedFields: the per-field "changed & non-empty" collector shared
 *     by htmlOverlayLayer.commitNodeEdit and editStateMachine.exitEditModeAndCollect,
 *     including the new `epistemic_state` field and the no-op guard.
 *   - isRiskState: the predicate (src/webview/cyMount.ts) that maps an epistemic
 *     string to the epistemicRisk styling flag — the restyle coupling that the
 *     post-edit local mirror (main.ts) must recompute.
 *
 * Inline-implementation pattern (matches gestureRouter.test.mjs): the collector
 * is modelled over plain {dataset, textContent} field objects, so it runs with
 * no DOM / jsdom. The Playwright gesture-router spec owns the live-DOM path.
 *
 * Run: node --test test/unit/editStateMachine.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

// --- Mirror of src/webview/cyMount.ts::isRiskState ---------------------------

function isRiskState(state) {
  if (!state) return false;
  const lower = state.toLowerCase();
  return lower.startsWith('risky') || lower.startsWith('speculative') || lower.startsWith('undecided');
}

// --- Mirror of the field collector (commitNodeEdit / exitEditModeAndCollect) --
// A "field" is a plain object standing in for an [data-ig-editable] element:
//   { dataset: { igField, igValue, igConstraintIndex? }, textContent }

function collectChangedFields(fields) {
  const single = (name) => {
    const el = fields.find((f) => f.dataset.igField === name);
    if (!el) return undefined;
    const newVal = (el.textContent ?? '').trim();
    const origVal = (el.dataset.igValue ?? '').trim();
    return newVal !== origVal && newVal.length > 0 ? newVal : undefined;
  };

  const changedName = single('name');
  const changedIntent = single('intent');
  const changedEpistemic = single('epistemic_state');

  const changedConstraints = (() => {
    const cEls = fields.filter((f) => f.dataset.igField === 'constraint');
    if (cEls.length === 0) return undefined;
    const arr = [];
    let any = false;
    for (const el of cEls) {
      const ci = el.dataset.igConstraintIndex !== undefined ? parseInt(el.dataset.igConstraintIndex, 10) : -1;
      if (ci < 0) continue;
      const newVal = (el.textContent ?? '').trim();
      const origVal = (el.dataset.igValue ?? '').trim();
      arr[ci] = newVal || origVal;
      if (newVal !== origVal && newVal.length > 0) any = true;
    }
    return any ? arr : undefined;
  })();

  if (!changedName && !changedIntent && !changedEpistemic && !changedConstraints) return null;
  return { name: changedName, intent: changedIntent, epistemic_state: changedEpistemic, constraints: changedConstraints };
}

const field = (igField, igValue, textContent, extra = {}) => ({
  dataset: { igField, igValue, ...extra },
  textContent
});

// --- collector: epistemic_state ---------------------------------------------

test('collector: returns epistemic_state when changed', () => {
  const out = collectChangedFields([
    field('name', 'N', 'N'),
    field('epistemic_state', 'known', 'risky: not yet validated')
  ]);
  assert.deepEqual(out, {
    name: undefined,
    intent: undefined,
    epistemic_state: 'risky: not yet validated',
    constraints: undefined
  });
});

test('collector: epistemic_state unchanged → not reported', () => {
  const out = collectChangedFields([
    field('epistemic_state', 'known', 'known')
  ]);
  assert.equal(out, null);
});

test('collector: whitespace-only epistemic edit is treated as no-op', () => {
  const out = collectChangedFields([
    field('epistemic_state', 'known', '   ')
  ]);
  assert.equal(out, null);
});

test('collector: multi-field name + epistemic', () => {
  const out = collectChangedFields([
    field('name', 'Old', 'New Name'),
    field('epistemic_state', 'undecided', 'constrained')
  ]);
  assert.equal(out.name, 'New Name');
  assert.equal(out.epistemic_state, 'constrained');
});

test('collector: no editable epistemic field present → epistemic undefined', () => {
  const out = collectChangedFields([field('name', 'A', 'B')]);
  assert.equal(out.name, 'B');
  assert.equal(out.epistemic_state, undefined);
});

// --- isRiskState (restyle coupling) -----------------------------------------

test('isRiskState: risk keywords → true', () => {
  assert.equal(isRiskState('risky'), true);
  assert.equal(isRiskState('risky: unverified'), true);
  assert.equal(isRiskState('speculative'), true);
  assert.equal(isRiskState('undecided'), true);
  assert.equal(isRiskState('Undecided — pending review'), true); // case-insensitive
});

test('isRiskState: non-risk / empty → false', () => {
  assert.equal(isRiskState('known'), false);
  assert.equal(isRiskState('observed'), false);
  assert.equal(isRiskState('inherited'), false);
  assert.equal(isRiskState(''), false);
  assert.equal(isRiskState(undefined), false);
});

test('isRiskState: compound "known | gap:" → false (base state wins)', () => {
  // Compound annotations keep the base state at the start, so a `known | gap: …`
  // node is NOT flagged as risk even though it carries an issue annotation.
  assert.equal(isRiskState('known | gap: missing detail'), false);
});
