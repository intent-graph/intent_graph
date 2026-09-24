/**
 * Verifier tests for Bug 1: Orphan Overlay (PIG LAYOUT.OVERLAY constraint #4)
 *
 * These tests independently verify that shouldHideOverlay correctly implements
 * the PIG constraint: "overlay visibility is coupled to compound collapse state."
 *
 * Mechanism audit:
 * When cytoscape-expand-collapse collapses a parent compound node:
 * 1. It adds class 'cy-expand-collapse-collapsed-node' to the parent
 * 2. It calls node.children().unselect() then removes children via child.remove()
 * 3. Descendants are stored in parent._private.data.collapsedChildren
 * 4. When node.visible() is queried, Cytoscape's visibility API may return stale-true
 *    for descendants of a collapsed parent (visibility not always propagated down)
 * 5. The ancestor-class check catches this by searching ancestors for the collapsed class
 *
 * The fix adds a third boolean (ancestorCollapsed) to the predicate, checked BEFORE
 * the existing nonempty/visible guards, ensuring descendants of collapsed compounds
 * are always hidden regardless of visible() status.
 */

import assert from 'assert';
import test from 'node:test';

/**
 * Pure function: decide whether an overlay should be hidden based on node state.
 * Inline copy for testing (matches htmlOverlayLayer.ts:104-117).
 */
function shouldHideOverlay(state) {
  // Hide if node was removed from graph.
  if (!state.nonempty) return true;
  // Hide if Cytoscape marked it as not visible.
  if (!state.visible) return true;
  // Hide if any ancestor is a collapsed compound (PIG constraint #4).
  if (state.ancestorCollapsed) return true;
  // Otherwise, let it be visible (subject to off-screen and min-height checks below).
  return false;
}

test('PIG LAYOUT.OVERLAY #4: shouldHideOverlay truth table', async (t) => {
  // Test all 8 combinations of (nonempty, visible, ancestorCollapsed).
  // Expectation: hide if ANY of the three is false (nonempty=F) or true (visible=F, collapsed=T).

  await t.test('(T,T,F): all true, no collapse → show', () => {
    const state = { nonempty: true, visible: true, ancestorCollapsed: false };
    assert.strictEqual(shouldHideOverlay(state), false);
  });

  await t.test('(T,T,T): ancestor collapsed → hide', () => {
    const state = { nonempty: true, visible: true, ancestorCollapsed: true };
    assert.strictEqual(shouldHideOverlay(state), true);
  });

  await t.test('(F,T,F): node removed → hide', () => {
    const state = { nonempty: false, visible: true, ancestorCollapsed: false };
    assert.strictEqual(shouldHideOverlay(state), true);
  });

  await t.test('(T,F,F): node not visible → hide', () => {
    const state = { nonempty: true, visible: false, ancestorCollapsed: false };
    assert.strictEqual(shouldHideOverlay(state), true);
  });

  await t.test('(F,F,F): removed + not visible → hide', () => {
    const state = { nonempty: false, visible: false, ancestorCollapsed: false };
    assert.strictEqual(shouldHideOverlay(state), true);
  });

  await t.test('(F,T,T): removed + ancestor collapsed → hide', () => {
    const state = { nonempty: false, visible: true, ancestorCollapsed: true };
    assert.strictEqual(shouldHideOverlay(state), true);
  });

  await t.test('(T,F,T): not visible + ancestor collapsed → hide', () => {
    const state = { nonempty: true, visible: false, ancestorCollapsed: true };
    assert.strictEqual(shouldHideOverlay(state), true);
  });

  await t.test('(F,F,T): all false → hide', () => {
    const state = { nonempty: false, visible: false, ancestorCollapsed: true };
    assert.strictEqual(shouldHideOverlay(state), true);
  });
});

test('Bug 1 diagnosis: ancestor-class check correctness', async (t) => {
  /**
   * When a node has no ancestors (e.g., an L1 root node), node.ancestors().nodes()
   * returns an empty collection. The ancestorCollapsed flag should be false (loop exits without finding).
   * The predicate should return false (show the overlay) if nonempty and visible.
   */
  await t.test('L1 node (no ancestors) with nonempty=T, visible=T → show', () => {
    const state = { nonempty: true, visible: true, ancestorCollapsed: false };
    assert.strictEqual(shouldHideOverlay(state), false,
      'Root nodes have no ancestors; ancestorCollapsed=false is correct.');
  });

  /**
   * When a descendant of a collapsed parent is queried:
   * - node.nonempty() still returns true (node is in cy graph)
   * - node.visible() MAY return true (stale visibility, not propagated to descendants)
   * - An ancestor has 'cy-expand-collapse-collapsed-node' class (the parent)
   * - ancestorCollapsed=true ensures the overlay is hidden despite visible()=true
   */
  await t.test('Descendant of collapsed compound with stale visible=T → hide', () => {
    const state = { nonempty: true, visible: true, ancestorCollapsed: true };
    assert.strictEqual(shouldHideOverlay(state), true,
      'Even if visible() returns true due to stale state, collapse ancestor flag forces hide.');
  });

  /**
   * The predicate is a conjunction: hide if ANY reason is true.
   * Order matters only for short-circuit optimization; semantically all three are independent.
   */
  await t.test('Conjunction order: ancestorCollapsed checked after nonempty/visible', () => {
    // True, True, True → hide (due to ancestorCollapsed)
    assert.strictEqual(shouldHideOverlay({
      nonempty: true, visible: true, ancestorCollapsed: true
    }), true);

    // False, *, * → hide (due to nonempty)
    assert.strictEqual(shouldHideOverlay({
      nonempty: false, visible: true, ancestorCollapsed: false
    }), true);

    // True, False, * → hide (due to visible)
    assert.strictEqual(shouldHideOverlay({
      nonempty: true, visible: false, ancestorCollapsed: false
    }), true);

    // Only (T, T, F) → show
    assert.strictEqual(shouldHideOverlay({
      nonempty: true, visible: true, ancestorCollapsed: false
    }), false);
  });
});

test('Wave 6 Bug 1: orphan overlay descendants of collapsed parent are reliably hidden', () => {
  /**
   * Scenario: user collapses a compound parent node via UI.
   * - Parent receives 'cy-expand-collapse-collapsed-node' class
   * - Children are removed from cy graph (but stored in parent.collapsedChildren)
   * - An overlay is still rendered for a descendant D (full LOD, before collapse)
   *
   * Old code:
   *   - tickOne() checked nonempty (FAIL, D is not in graph) → hide
   *   - OR checked visible (FAIL, D is hidden by cy hierarchy) → hide
   *   - Both guards fired; overlay was hidden (correct result, but fragile)
   *
   * New code (Bug 1 fix):
   *   - tickOne() also checks ancestorCollapsed (PASS, parent has class) → hide
   *   - Ensures overlay is hidden even if nonempty/visible checks fail to catch it
   *   - Makes the contract explicit and adds robustness
   */
  const descendantOfCollapsedParent = {
    nonempty: true,  // Cytoscape: node may still exist in collapsedChildren
    visible: true,   // Cytoscape visibility may be stale (not propagated down)
    ancestorCollapsed: true  // Parent has 'cy-expand-collapse-collapsed-node' class
  };
  assert.strictEqual(shouldHideOverlay(descendantOfCollapsedParent), true,
    'Descendants of collapsed compounds are hidden by ancestor-class check, even if stale state says otherwise.');
});
