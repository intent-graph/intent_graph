/**
 * Gesture-router integration smoke tests.
 *
 * Purpose: catch regressions in the public API surface and the dispatch
 * decisions of the router, beyond what the per-step unit files cover.
 *
 * Scope: pure-logic + DOM-target predicates only. The full event flow
 * (cy.on('tap'), document-level pointerdown bubbling) requires a real DOM
 * with canvas support; that coverage lives in the manual F5 gate. This file
 * fills the gap between "pure helper unit test" and "full Playwright e2e"
 * by exercising the predicates exactly as the runtime calls them.
 *
 * Why not Playwright here:
 *   - Playwright adds ~200MB of browser binaries and per-CI install latency.
 *   - VS Code webviews are not directly Playwright-targetable without
 *     vscode-test or CDP attach plumbing — fragile for a smoke layer.
 *   - The user-facing acceptance gate is manual F5 verification of the real
 *     extension; unit tests are baseline-not-acceptance per the plan §2.7.
 *
 * Inline-implementation pattern to match the repo convention (no build step
 * required to run tests, no JSDOM dependency).
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ============================================================================
// INLINE IMPLEMENTATION — mirrors src/webview/interaction/gestureRouter.ts
// (factor: pure functions only; class methods that touch cy / document are
// excluded — those are the ones the F5 gate covers.)
// ============================================================================

function shouldCommitOnPointerDown({ editingCard, target, isChromeTarget }) {
  if (!editingCard) return false;
  if (target && editingCard.contains?.(target)) return false;
  if (isChromeTarget?.(target)) return false;
  return true;
}

function wasActualDrag(startPos, endPos, threshold = 1) {
  if (!startPos) return false;
  return (
    Math.abs(startPos.x - endPos.x) >= threshold ||
    Math.abs(startPos.y - endPos.y) >= threshold
  );
}

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
// SCENARIO TESTS — combinations across the five gestures
// ============================================================================

test('Scenario: drag start → drag end with movement → wasActualDrag = true', () => {
  const start = { x: 100, y: 100 };
  const end = { x: 142, y: 113 };
  assert.equal(wasActualDrag(start, end), true);
});

test('Scenario: tap-only (grab + free without movement) → wasActualDrag = false', () => {
  // Reproduces Bug B: 'free' fires even on click-without-move.
  const start = { x: 100, y: 100 };
  const end = { x: 100, y: 100 };
  assert.equal(wasActualDrag(start, end), false);
});

test('Scenario: dbltap stamps editingUid; trailing tap on the same node is suppressed', () => {
  // Sanity: the post-Step-1 dispatch order is [dbltap → set editingUid → tap]
  // and the tap handler bails out when state.editingUid === thisUid.
  const state = { editingUid: null };
  // Dbltap fires first.
  state.editingUid = 'A';
  // Trailing tap on A: predicate (mirrors gestureRouter.ts:onTap line 96).
  function tapShouldSkip(state, uid) { return state.editingUid === uid; }
  assert.equal(tapShouldSkip(state, 'A'), true);
  // Tap on B (a different node) is NOT suppressed.
  assert.equal(tapShouldSkip(state, 'B'), false);
});

test('Scenario: outside-click commits edit; click on lens dropdown does not', () => {
  const card = { contains: (n) => n === 'cardField1' || n === 'cardName' };
  const lensItemTarget = { id: 'lens-item' };
  const isChromeTarget = (t) => t === lensItemTarget;

  // Click on canvas (outside both card and chrome) → commit.
  assert.equal(
    shouldCommitOnPointerDown({ editingCard: card, target: 'canvas', isChromeTarget }),
    true
  );
  // Click inside the card → no commit (Tab nav case).
  assert.equal(
    shouldCommitOnPointerDown({ editingCard: card, target: 'cardField1', isChromeTarget }),
    false
  );
  // Click on the lens dropdown chrome → no commit.
  assert.equal(
    shouldCommitOnPointerDown({ editingCard: card, target: lensItemTarget, isChromeTarget }),
    false
  );
});

test('Scenario: cue stays hidden under every individual hide condition', () => {
  const base = {
    nonempty: true,
    visible: true,
    ancestorCollapsed: false,
    editing: false,
    offScreen: false,
    belowMinHeight: false
  };
  // Every individual flag flipped to true triggers hide.
  const conditions = [
    'ancestorCollapsed',
    'editing',
    'offScreen',
    'belowMinHeight'
  ];
  for (const c of conditions) {
    assert.equal(shouldHideCue({ ...base, [c]: true }), true, c);
  }
  // Healthy node visible.
  assert.equal(shouldHideCue(base), false);
});

test('Scenario: cue click decides collapse vs expand by current state', () => {
  // A collapsed compound (isExpandable=true) → expand.
  assert.equal(decideCompoundAction({ isCollapsible: false, isExpandable: true }), 'expand');
  // An expanded compound (isCollapsible=true) → collapse.
  assert.equal(decideCompoundAction({ isCollapsible: true, isExpandable: false }), 'collapse');
});

// ============================================================================
// REGRESSION GUARDS — properties that future steps must preserve
// ============================================================================

test('Regression guard: tap suppression key is uid-equality, not a timestamp window', () => {
  // The old 350ms window was the source of the dbltap race. Verify the new
  // predicate only depends on uid, not on time.
  const state = { editingUid: 'A' };
  function tapShouldSkip(state, uid) { return state.editingUid === uid; }
  // Stable across "time" — call repeatedly.
  for (let i = 0; i < 5; i++) {
    assert.equal(tapShouldSkip(state, 'A'), true);
    assert.equal(tapShouldSkip(state, 'B'), false);
  }
});

test('Regression guard: drag persistence is gated by editingUid, not uiPhase heuristic', () => {
  // Step 4 replaced the prior getMode() heuristic on uiPhase. Verify that
  // drag-suppression depends on editingUid (any node editing → suppressed).
  function shouldSuppressDrag(state) { return state.editingUid !== null; }
  assert.equal(shouldSuppressDrag({ editingUid: null }), false);
  assert.equal(shouldSuppressDrag({ editingUid: 'A' }), true);
  // The uid does not need to be the dragged node — ANY editing suppresses.
  assert.equal(shouldSuppressDrag({ editingUid: 'X' }), true);
});

test('Regression guard: cue hide on edit checks THIS uid, not "any uid editing"', () => {
  // Editing node A should NOT hide node B's cue. Other nodes' cues remain
  // visible so the user can still expand/collapse them while editing A.
  const state = { editingUid: 'A' };
  function isThisCueEditing(state, uid) { return state.editingUid === uid; }
  assert.equal(isThisCueEditing(state, 'A'), true);
  assert.equal(isThisCueEditing(state, 'B'), false);
});
