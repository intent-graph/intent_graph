/**
 * Gesture router state semantics tests.
 *
 * Pure-logic / state-shape tests for:
 *   - createGestureStateFrom: shared-reference invariant for nodeLOD/collapseSet
 *     (so reload snapshot/restore on WebviewState continues to work)
 *   - editingUid mutability (replaces the 350ms timing window)
 *   - grabPosition independence (per-router-instance)
 *
 * Inline-implementation pattern (matches wheelGestures.test.mjs / persistPosition.test.mjs):
 * pure logic is reproduced here so tests run without a build step.
 *
 * The router's tap/dbltap dispatch logic is not unit-tested here — Cytoscape
 * events require a live cy instance. The Step 6 Playwright e2e test owns that
 * coverage.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ============================================================================
// INLINE IMPLEMENTATION (mirrors src/webview/interaction/state.ts::createGestureStateFrom)
// ============================================================================

function createGestureStateFrom(parts) {
  return {
    nodeLOD: parts.nodeLOD,
    collapseSet: parts.collapseSet,
    editingUid: null,
    grabPosition: new Map()
  };
}

// ============================================================================
// TESTS
// ============================================================================

test('createGestureStateFrom reuses provided Map and Set instances', () => {
  const nodeLOD = new Map([['A', 'full']]);
  const collapseSet = new Set(['B']);
  const state = createGestureStateFrom({ nodeLOD, collapseSet });

  // Identity equality — the GestureState must NOT clone the parts so that
  // reload snapshot/restore on WebviewState continues to work.
  assert.equal(state.nodeLOD, nodeLOD);
  assert.equal(state.collapseSet, collapseSet);

  // editingUid starts null and grabPosition is its own fresh Map.
  assert.equal(state.editingUid, null);
  assert.ok(state.grabPosition instanceof Map);
  assert.equal(state.grabPosition.size, 0);
});

test('editingUid is mutable and observable (replaces 350ms timing window)', () => {
  const state = createGestureStateFrom({
    nodeLOD: new Map(),
    collapseSet: new Set()
  });

  assert.equal(state.editingUid, null);
  state.editingUid = 'A';
  assert.equal(state.editingUid, 'A');
  state.editingUid = null;
  assert.equal(state.editingUid, null);
});

test('GestureState.nodeLOD writes are visible on the original Map (shared reference)', () => {
  const original = new Map();
  const state = createGestureStateFrom({
    nodeLOD: original,
    collapseSet: new Set()
  });

  state.nodeLOD.set('A', 'full');
  assert.equal(original.get('A'), 'full');
  assert.equal(original.size, 1);
});

test('GestureState.collapseSet writes are visible on the original Set (shared reference)', () => {
  const original = new Set();
  const state = createGestureStateFrom({
    nodeLOD: new Map(),
    collapseSet: original
  });

  state.collapseSet.add('A');
  assert.ok(original.has('A'));
  assert.equal(original.size, 1);
});

test('grabPosition is per-instance (not shared across createGestureStateFrom calls)', () => {
  const state1 = createGestureStateFrom({
    nodeLOD: new Map(),
    collapseSet: new Set()
  });
  state1.grabPosition.set('A', { x: 1, y: 2 });
  assert.equal(state1.grabPosition.size, 1);

  const state2 = createGestureStateFrom({
    nodeLOD: new Map(),
    collapseSet: new Set()
  });
  assert.equal(state2.grabPosition.size, 0);
});

// ============================================================================
// Tap-vs-dbltap suppression decision (the rule replaced the 350ms window)
// ============================================================================

/**
 * Predicate the router uses in its tap handler to decide whether to skip the
 * LOD toggle for a given uid. Mirrors the explicit guard in gestureRouter.ts
 * (state.editingUid === uid → return).
 */
function shouldSuppressTapForLodToggle(state, uid) {
  return state.editingUid === uid;
}

test('shouldSuppressTapForLodToggle: returns true only for the editing uid', () => {
  const state = createGestureStateFrom({ nodeLOD: new Map(), collapseSet: new Set() });
  state.editingUid = 'A';

  // Suppressed for the editing node.
  assert.equal(shouldSuppressTapForLodToggle(state, 'A'), true);
  // Not suppressed for any other node.
  assert.equal(shouldSuppressTapForLodToggle(state, 'B'), false);
});

test('shouldSuppressTapForLodToggle: returns false when nothing is editing (default state)', () => {
  const state = createGestureStateFrom({ nodeLOD: new Map(), collapseSet: new Set() });
  assert.equal(state.editingUid, null);
  assert.equal(shouldSuppressTapForLodToggle(state, 'A'), false);
});

test('shouldSuppressTapForLodToggle: stays correct after a transition (A then B)', () => {
  const state = createGestureStateFrom({ nodeLOD: new Map(), collapseSet: new Set() });
  state.editingUid = 'A';
  assert.equal(shouldSuppressTapForLodToggle(state, 'A'), true);
  state.editingUid = 'B';
  assert.equal(shouldSuppressTapForLodToggle(state, 'A'), false);
  assert.equal(shouldSuppressTapForLodToggle(state, 'B'), true);
});

// ============================================================================
// Outside-click decision (mirrors gestureRouter.ts::shouldCommitOnPointerDown)
// ============================================================================

/**
 * Inline mirror of the predicate. Uses minimal stand-ins: `editingCard.contains(target)`
 * is faithful to Node.contains semantics; `isChromeTarget` is an arbitrary callback.
 */
function shouldCommitOnPointerDown({ editingCard, target, isChromeTarget }) {
  if (!editingCard) return false;
  // Faithful Node.contains: the test stand-in card uses an array of "owned" nodes.
  if (target && editingCard.contains?.(target)) return false;
  if (isChromeTarget?.(target)) return false;
  return true;
}

function makeStandInCard(ownedNodes = []) {
  return {
    contains: (node) => ownedNodes.includes(node)
  };
}

test('shouldCommitOnPointerDown: returns false when nothing is editing', () => {
  assert.equal(
    shouldCommitOnPointerDown({ editingCard: null, target: {} }),
    false
  );
});

test('shouldCommitOnPointerDown: returns false when target is inside the editing card (Tab nav case)', () => {
  const fieldA = { id: 'fieldA' };
  const card = makeStandInCard([fieldA]);
  assert.equal(
    shouldCommitOnPointerDown({ editingCard: card, target: fieldA }),
    false
  );
});

test('shouldCommitOnPointerDown: returns true when target is outside both card and chrome', () => {
  const card = makeStandInCard([]);
  const target = { id: 'canvas' };
  assert.equal(
    shouldCommitOnPointerDown({
      editingCard: card,
      target,
      isChromeTarget: () => false
    }),
    true
  );
});

test('shouldCommitOnPointerDown: returns false when target is inside the lens-selector chrome', () => {
  const card = makeStandInCard([]);
  const target = { id: 'lens-list-item' };
  assert.equal(
    shouldCommitOnPointerDown({
      editingCard: card,
      target,
      isChromeTarget: (t) => t === target
    }),
    false
  );
});

test('shouldCommitOnPointerDown: card.contains takes precedence over chrome predicate', () => {
  const fieldA = { id: 'fieldA' };
  const card = makeStandInCard([fieldA]);
  // Even if isChromeTarget says yes, the card containing the target should
  // already short-circuit to false — sanity check on the order of checks.
  assert.equal(
    shouldCommitOnPointerDown({
      editingCard: card,
      target: fieldA,
      isChromeTarget: () => true
    }),
    false
  );
});
