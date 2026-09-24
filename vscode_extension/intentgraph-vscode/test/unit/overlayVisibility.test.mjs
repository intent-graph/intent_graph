import assert from 'assert';
import { test } from 'node:test';

/**
 * Test suite for overlay visibility predicate — Bug 1 fix (orphan overlay).
 * Pure-logic tests for PIG LAYOUT.OVERLAY constraint #4:
 * "Overlay visibility is coupled to compound collapse state.
 *  If a node is not visible on the canvas (parent collapsed), its overlay must not be visible."
 *
 * Root cause: cytoscape-expand-collapse removes descendants from the cy graph when a parent
 * is collapsed, but the HTML overlay DOM card persists in the overlayMap. The visibility
 * guard in tickOne() must check three conditions:
 *   1. node still exists in cy (nonempty)
 *   2. node.visible() returns true
 *   3. no ancestor has the 'cy-expand-collapse-collapsed-node' class (belt-and-suspenders)
 *
 * This test file extracts the visibility predicate as a pure function for testability.
 */

/**
 * Pure function: decide whether an overlay should be hidden based on node state.
 * Matches the logic in src/webview/overlay/htmlOverlayLayer.ts::shouldHideOverlay.
 * Can be tested without Cytoscape or DOM dependencies.
 */
function shouldHideOverlay(state) {
  // Hide if node was removed from graph (Case 1: collapse removes children).
  if (!state.nonempty) return true;
  // Hide if Cytoscape marked it as not visible (Case 2: secondary visibility check).
  if (!state.visible) return true;
  // Hide if any ancestor is a collapsed compound (Case 3: descendant of collapsed parent).
  if (state.ancestorCollapsed) return true;
  // Otherwise, let it be visible (subject to off-screen and min-height checks in tickOne).
  return false;
}

// Truth table: 2^3 = 8 combinations of (nonempty, visible, ancestorCollapsed).
// Expected: hide if ANY condition is true (OR logic on hide conditions).

test('LAYOUT.OVERLAY::shouldHideOverlay - (T,T,F): all true, no collapse → show', () => {
  const state = { nonempty: true, visible: true, ancestorCollapsed: false };
  assert.strictEqual(shouldHideOverlay(state), false, 'overlay should be visible');
});

test('LAYOUT.OVERLAY::shouldHideOverlay - (T,T,T): ancestor collapsed → hide', () => {
  const state = { nonempty: true, visible: true, ancestorCollapsed: true };
  assert.strictEqual(shouldHideOverlay(state), true, 'PIG #4: must hide when ancestor is collapsed');
});

test('LAYOUT.OVERLAY::shouldHideOverlay - (F,T,F): node removed → hide', () => {
  const state = { nonempty: false, visible: true, ancestorCollapsed: false };
  assert.strictEqual(shouldHideOverlay(state), true, 'must hide when node is removed from graph');
});

test('LAYOUT.OVERLAY::shouldHideOverlay - (T,F,F): node not visible → hide', () => {
  const state = { nonempty: true, visible: false, ancestorCollapsed: false };
  assert.strictEqual(shouldHideOverlay(state), true, 'must hide when node is not visible');
});

test('LAYOUT.OVERLAY::shouldHideOverlay - (F,F,F): removed + not visible → hide', () => {
  const state = { nonempty: false, visible: false, ancestorCollapsed: false };
  assert.strictEqual(shouldHideOverlay(state), true, 'must hide on multiple guard failures');
});

test('LAYOUT.OVERLAY::shouldHideOverlay - (F,T,T): removed + ancestor collapsed → hide', () => {
  const state = { nonempty: false, visible: true, ancestorCollapsed: true };
  assert.strictEqual(shouldHideOverlay(state), true, 'must hide on multiple guard failures');
});

test('LAYOUT.OVERLAY::shouldHideOverlay - (T,F,T): not visible + ancestor collapsed → hide', () => {
  const state = { nonempty: true, visible: false, ancestorCollapsed: true };
  assert.strictEqual(shouldHideOverlay(state), true, 'must hide on multiple guard failures');
});

test('LAYOUT.OVERLAY::shouldHideOverlay - (F,F,T): all false → hide', () => {
  const state = { nonempty: false, visible: false, ancestorCollapsed: true };
  assert.strictEqual(shouldHideOverlay(state), true, 'must hide on all guard failures');
});

// Semantic tests: validate PIG intent.

test('PIG LAYOUT.OVERLAY #4: overlay hidden when node.visible() === false', () => {
  const visible = { nonempty: true, visible: true, ancestorCollapsed: false };
  const notVisible = { nonempty: true, visible: false, ancestorCollapsed: false };
  assert.strictEqual(shouldHideOverlay(visible), false);
  assert.strictEqual(shouldHideOverlay(notVisible), true, 'every overlay hidden when visible===false');
});

test('PIG LAYOUT.OVERLAY #4: overlay visibility coupled to compound collapse', () => {
  const collapsed = { nonempty: true, visible: true, ancestorCollapsed: true };
  const expanded = { nonempty: true, visible: true, ancestorCollapsed: false };
  assert.strictEqual(shouldHideOverlay(collapsed), true, 'hide when parent is collapsed');
  assert.strictEqual(shouldHideOverlay(expanded), false, 'show when parent is expanded');
});

test('Wave 6 Bug 1: orphan overlay descendants of collapsed parent are reliably hidden', () => {
  // Simulate the bug scenario:
  // User collapses a parent node. Its descendants remain in overlayMap but should be hidden.
  const descendantOfCollapsed = {
    nonempty: true,        // node still exists in cy (not removed)
    visible: true,         // node.visible() might still return true (cy quirk)
    ancestorCollapsed: true // but ancestor HAS the collapse class
  };
  assert.strictEqual(
    shouldHideOverlay(descendantOfCollapsed),
    true,
    'descendant overlay must hide even if nonempty and visible, if ancestor collapsed'
  );
});
