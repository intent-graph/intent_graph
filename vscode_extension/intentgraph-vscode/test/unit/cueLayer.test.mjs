/**
 * CueLayer pure-logic tests.
 *
 * Inline-implementation pattern (matches other test files): we mirror the pure
 * decision functions from src/webview/overlay/cueLayer.ts so tests run without
 * a build step. The DOM-dependent rendering pipeline is exercised by the Step 6
 * Playwright e2e test.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ============================================================================
// INLINE IMPLEMENTATION (mirrors cueLayer.ts::shouldHideCue + decideCompoundAction)
// ============================================================================

function shouldHideCue(state) {
  if (!state.nonempty) return true;
  if (!state.visible) return true;
  if (state.ancestorCollapsed) return true;
  if (state.editing) return true;
  if (state.offScreen) return true;
  if (state.belowMinHeight) return true;
  return false;
}

function decideCompoundAction({ isCollapsible, isExpandable }) {
  if (isCollapsible) return 'collapse';
  if (isExpandable) return 'expand';
  return null;
}

// ============================================================================
// shouldHideCue — truth table
// ============================================================================

const baseHealthy = {
  nonempty: true,
  visible: true,
  ancestorCollapsed: false,
  editing: false,
  offScreen: false,
  belowMinHeight: false
};

test('shouldHideCue: healthy compound visible in viewport → show', () => {
  assert.equal(shouldHideCue(baseHealthy), false);
});

test('shouldHideCue: missing node (deleted) → hide', () => {
  assert.equal(shouldHideCue({ ...baseHealthy, nonempty: false }), true);
});

test('shouldHideCue: cy-marked invisible → hide', () => {
  assert.equal(shouldHideCue({ ...baseHealthy, visible: false }), true);
});

test('shouldHideCue: ancestor collapsed → hide (the orphan-cue case)', () => {
  // This is the analog of the orphan-overlay bug: when an ancestor is collapsed,
  // descendants are removed-and-stashed by cytoscape-expand-collapse. The cue
  // must hide along with the node.
  assert.equal(shouldHideCue({ ...baseHealthy, ancestorCollapsed: true }), true);
});

test('shouldHideCue: this node is editing → hide (PIG LAYOUT.CUES)', () => {
  assert.equal(shouldHideCue({ ...baseHealthy, editing: true }), true);
});

test('shouldHideCue: off-screen → hide (no point rendering)', () => {
  assert.equal(shouldHideCue({ ...baseHealthy, offScreen: true }), true);
});

test('shouldHideCue: below min readable height → hide', () => {
  assert.equal(shouldHideCue({ ...baseHealthy, belowMinHeight: true }), true);
});

test('shouldHideCue: any single hide condition is sufficient', () => {
  // Sanity: each hide condition independently triggers hide.
  const conditions = ['ancestorCollapsed', 'editing', 'offScreen', 'belowMinHeight'];
  for (const c of conditions) {
    assert.equal(shouldHideCue({ ...baseHealthy, [c]: true }), true, `expected hide when ${c} is true`);
  }
});

// ============================================================================
// decideCompoundAction — collapse/expand routing
// ============================================================================

test('decideCompoundAction: isCollapsible=true → collapse', () => {
  assert.equal(decideCompoundAction({ isCollapsible: true, isExpandable: false }), 'collapse');
});

test('decideCompoundAction: isExpandable=true → expand', () => {
  assert.equal(decideCompoundAction({ isCollapsible: false, isExpandable: true }), 'expand');
});

test('decideCompoundAction: neither → null (defensive no-op)', () => {
  assert.equal(decideCompoundAction({ isCollapsible: false, isExpandable: false }), null);
});

test('decideCompoundAction: collapsible takes precedence over expandable (impossible state, deterministic)', () => {
  // The library shouldn't return both true, but if it does, prefer collapse —
  // that matches the source order and is a deterministic fallback.
  assert.equal(decideCompoundAction({ isCollapsible: true, isExpandable: true }), 'collapse');
});
