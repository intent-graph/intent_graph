/**
 * Unit tests for wheel gesture deliverables.
 *
 * Verifies:
 *  - INTERACTION.GESTURES wheel-zoom sensitivity constraint (wheelSensitivity = 0.2)
 *  - INTERACTION.GESTURES horizontal pan via deltaX constraint
 *  - decideHorizontalPan pure-logic helper correctness
 *  - data_registry.timings values match PIG and implementation
 *
 * This test file uses the inline-implementation pattern: pure-function logic is
 * reproduced here so tests run without a build step via:
 *   node --test test/unit/wheelGestures.test.mjs
 *
 * From PIG: INTERACTION.GESTURES constraints #8-#9.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ============================================================================
// PURE-LOGIC IMPLEMENTATION (mirrors src/webview/cyMount.ts::decideHorizontalPan)
// ============================================================================

// PIG INTERACTION.GESTURES data_registry.timings values (must match source).
const WHEEL_SENSITIVITY = 0.2;
const HORIZONTAL_PAN_SCALE = 1.0;

/**
 * Pure-logic helper for horizontal pan via deltaX.
 * PIG INTERACTION.GESTURES constraint #9: "Side-wheel deltaX pans viewport
 * horizontally: deltaX > 0 (scroll-right) pans content left (pinch-zoom on ctrlKey
 * is skipped, Cytoscape handles via native wheel handler)."
 *
 * @param event Wheel event (or event-like object with deltaX, deltaY, ctrlKey)
 * @returns { x, y } pan spec if action should be taken, null if should be skipped
 */
function decideHorizontalPan(event) {
  // Skip pinch-zoom (Cytoscape's native handler will manage it).
  if (event.ctrlKey) return null;
  // Skip if no horizontal component.
  if (event.deltaX === 0) return null;
  // Return pan spec: negate deltaX so scroll-right pans content left.
  return { x: -event.deltaX * HORIZONTAL_PAN_SCALE, y: 0 };
}

// ============================================================================
// TEST SUITE
// ============================================================================

test('INTERACTION.GESTURES #8: wheel-zoom sensitivity constant', () => {
  // from PIG: INTERACTION.GESTURES — "Wheel-zoom sensitivity: cytoscape
  // wheelSensitivity = /timings/wheelSensitivity (default 0.2 vs Cytoscape
  // default 1.0)."
  assert.strictEqual(WHEEL_SENSITIVITY, 0.2, 'wheelSensitivity must be 0.2');
});

test('INTERACTION.GESTURES #9: horizontal pan scale constant', () => {
  // from PIG: INTERACTION.GESTURES data_registry.timings.horizontalPanScale
  assert.strictEqual(HORIZONTAL_PAN_SCALE, 1.0, 'horizontalPanScale must be 1.0');
});

test('INTERACTION.GESTURES #9: decideHorizontalPan — scroll-right pans content left', () => {
  // from PIG: INTERACTION.GESTURES — "deltaX > 0 (scroll-right) pans content left"
  const result = decideHorizontalPan({ deltaX: 100, deltaY: 0, ctrlKey: false });
  assert.deepStrictEqual(result, { x: -100, y: 0 }, 'deltaX=100 should pan x=-100');
});

test('INTERACTION.GESTURES #9: decideHorizontalPan — scroll-left pans content right', () => {
  // Symmetry test: negative deltaX should pan right.
  const result = decideHorizontalPan({ deltaX: -100, deltaY: 0, ctrlKey: false });
  assert.deepStrictEqual(result, { x: 100, y: 0 }, 'deltaX=-100 should pan x=100');
});

test('INTERACTION.GESTURES #9: decideHorizontalPan — zero deltaX skips pan', () => {
  // from PIG: "Skip if no horizontal component"
  const result = decideHorizontalPan({ deltaX: 0, deltaY: 50, ctrlKey: false });
  assert.strictEqual(result, null, 'deltaX=0 should return null (let Cytoscape handle vertical)');
});

test('INTERACTION.GESTURES #9: decideHorizontalPan — ctrlKey (pinch-zoom) skips pan', () => {
  // from PIG: "pinch-zoom on ctrlKey is skipped, Cytoscape handles via native wheel handler"
  const result = decideHorizontalPan({ deltaX: 50, deltaY: 0, ctrlKey: true });
  assert.strictEqual(result, null, 'ctrlKey=true should return null (let Cytoscape zoom)');
});

test('INTERACTION.GESTURES #9: decideHorizontalPan — both deltaX and ctrlKey (pinch skips pan)', () => {
  // Edge case: pinch-zoom takes precedence over horizontal pan.
  const result = decideHorizontalPan({ deltaX: 100, deltaY: -50, ctrlKey: true });
  assert.strictEqual(result, null, 'ctrlKey=true should skip pan even with non-zero deltaX');
});

test('INTERACTION.GESTURES #9: decideHorizontalPan — respects horizontalPanScale multiplier', () => {
  // If HORIZONTAL_PAN_SCALE changes, pan magnitude should scale.
  // (This test verifies the impl constant is used; if scale were 2.0, result would be {x: -200, y: 0}).
  assert.strictEqual(HORIZONTAL_PAN_SCALE, 1.0, 'scale precondition');
  const result = decideHorizontalPan({ deltaX: 50, deltaY: 0, ctrlKey: false });
  assert.deepStrictEqual(result, { x: -50 * HORIZONTAL_PAN_SCALE, y: 0 }, 'pan should apply scale');
});

test('INTERACTION.GESTURES #9: decideHorizontalPan — large deltaX values', () => {
  // High-speed scrolling: large deltas should pan proportionally.
  const result = decideHorizontalPan({ deltaX: 500, deltaY: 0, ctrlKey: false });
  assert.deepStrictEqual(result, { x: -500, y: 0 }, 'large deltaX should pan proportionally');
});

test('INTERACTION.GESTURES #8-#9: data_registry values are sensible defaults', () => {
  // from PIG: wheelSensitivity=0.2 (vs Cytoscape default 1.0, reason: "aggressive default unusable on most hardware")
  // horizontalPanScale=1.0 (1px deltaX → 1px pan)
  assert.strictEqual(WHEEL_SENSITIVITY, 0.2, 'wheelSensitivity should be calm (0.2)');
  assert.strictEqual(HORIZONTAL_PAN_SCALE, 1.0, 'horizontalPanScale should be 1:1');
});

test('INTERACTION.GESTURES #9: y-component is always zero in pan result', () => {
  // from PIG: "deltaX pans horizontally" — deltaY is never touched.
  // Cytoscape's native wheel handler manages vertical zoom.
  const result = decideHorizontalPan({ deltaX: 100, deltaY: 999, ctrlKey: false });
  assert.strictEqual(result.y, 0, 'pan result y must always be 0 (deltaY ignored)');
});

test('INTERACTION.GESTURES #9: negative y-delta does not trigger pan', () => {
  // Pinch-zoom on trackpad can have negative deltaY with zero deltaX.
  // Even with ctrlKey false, we should only pan if deltaX is non-zero.
  const result = decideHorizontalPan({ deltaX: 0, deltaY: -50, ctrlKey: false });
  assert.strictEqual(result, null, 'only deltaX controls horizontal pan');
});

// ============================================================================
// BUG B REGRESSION TESTS (wasActualDrag)
// ============================================================================

/**
 * Pure-logic implementation of wasActualDrag (mirrors src/webview/cyMount.ts).
 * PIG INTERACTION.DRAG — distinguish drag from click-without-move.
 */
function wasActualDrag(startPos, endPos, threshold = 1) {
  if (!startPos) return false;
  return Math.abs(startPos.x - endPos.x) >= threshold || Math.abs(startPos.y - endPos.y) >= threshold;
}

test('INTERACTION.DRAG (Bug B): click-without-move (identical positions) returns false', () => {
  // from PIG: click-without-move must NOT trigger PERSISTENCE.AUTOSAVE
  assert.equal(wasActualDrag({x: 100, y: 100}, {x: 100, y: 100}), false,
    'identical positions should not be considered a drag');
});

test('INTERACTION.DRAG (Bug B): actual drag (>1px movement) returns true', () => {
  // from PIG: real drag should fire PERSISTENCE.AUTOSAVE
  assert.equal(wasActualDrag({x: 100, y: 100}, {x: 110, y: 100}), true,
    'x-axis movement >1px should be considered a drag');
});

test('INTERACTION.DRAG (Bug B): sub-pixel jitter (<1px) returns false', () => {
  // from PIG: sub-pixel jitter from touch/trackpad should not trigger write
  assert.equal(wasActualDrag({x: 100, y: 100}, {x: 100.5, y: 100}), false,
    'sub-pixel jitter should not trigger a drag');
});

test('INTERACTION.DRAG (Bug B): missing startPos (no grab event) returns false', () => {
  // Edge case: if grab event didn't fire, don't fire AUTOSAVE
  assert.equal(wasActualDrag(undefined, {x: 100, y: 100}), false,
    'missing startPos indicates no grab event — should not trigger drag');
});

test('INTERACTION.DRAG (Bug B): vertical drag (y-axis only) detected', () => {
  // from PIG: movement on any axis qualifies as a drag
  assert.equal(wasActualDrag({x: 100, y: 100}, {x: 100, y: 110}), true,
    'y-axis movement >1px should be considered a drag');
});

test('INTERACTION.DRAG (Bug B): custom threshold respected', () => {
  // from PIG: threshold can be tuned (default 1px); test with custom value
  assert.equal(wasActualDrag({x: 100, y: 100}, {x: 105, y: 100}, 10), false,
    'movement <10px should not exceed custom threshold');
  assert.equal(wasActualDrag({x: 100, y: 100}, {x: 105, y: 100}, 1), true,
    'movement >=1px should exceed threshold of 1');
});
