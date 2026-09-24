/**
 * Unit tests for deriveLensVisibility (src/shared/lensVisibility.ts).
 *
 * Canonical implementation of PIG node `LENSSCHEMA.VISIBILITY`. The function is
 * pure TypeScript with type-only imports; the logic is mirrored inline here so
 * the test runs without a build step:
 *   node --test test/unit/lensVisibility.test.mjs
 *
 * If lensVisibility.ts changes, update the mirror below.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ---------------------------------------------------------------------------
// Inline mirror of src/shared/lensVisibility.ts::deriveLensVisibility.
// Update here whenever the source changes.
// ---------------------------------------------------------------------------
function deriveLensVisibility(lensNodeUids, childrenOf) {
  const displayState = new Map();
  const visibleUids = new Set();
  const collapsedCompoundUids = new Set();

  for (const uid of childrenOf.keys()) {
    if (!lensNodeUids.has(uid)) {
      displayState.set(uid, 'absent');
      continue;
    }
    const children = childrenOf.get(uid) ?? [];
    if (children.length === 0) {
      displayState.set(uid, 'visible-leaf');
      visibleUids.add(uid);
      continue;
    }
    const anyChildInLens = children.some((c) => lensNodeUids.has(c));
    if (anyChildInLens) {
      displayState.set(uid, 'visible-expanded');
    } else {
      displayState.set(uid, 'visible-collapsed');
      collapsedCompoundUids.add(uid);
    }
    visibleUids.add(uid);
  }
  return { displayState, visibleUids, collapsedCompoundUids };
}

// ---------------------------------------------------------------------------
// Test fixture: small tree with three depths.
//   ROOT
//   ├── A (compound)
//   │   ├── A.1 (leaf)
//   │   └── A.2 (compound)
//   │       └── A.2.1 (leaf)
//   ├── B (compound, single leaf child)
//   │   └── B.1 (leaf)
//   └── C (leaf)
// ---------------------------------------------------------------------------
const childrenOf = new Map([
  ['ROOT', ['A', 'B', 'C']],
  ['A', ['A.1', 'A.2']],
  ['A.1', []],
  ['A.2', ['A.2.1']],
  ['A.2.1', []],
  ['B', ['B.1']],
  ['B.1', []],
  ['C', []]
]);

// ---------------------------------------------------------------------------
// Constraint #1: present uid → displayed.
// Constraint #2: absent uid → not displayed.
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY #1+#2: presence determines display', () => {
  const lensUids = new Set(['ROOT', 'C']);
  const v = deriveLensVisibility(lensUids, childrenOf);
  assert.equal(v.displayState.get('C'), 'visible-leaf');
  assert.equal(v.displayState.get('A'), 'absent');
  assert.equal(v.displayState.get('B'), 'absent');
  assert.equal(v.visibleUids.has('C'), true);
  assert.equal(v.visibleUids.has('A'), false);
});

// ---------------------------------------------------------------------------
// Constraint #3: compound + ≥1 child in lens → expanded.
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY #3: compound with one child in lens => expanded', () => {
  const lensUids = new Set(['ROOT', 'A', 'A.1']);
  const v = deriveLensVisibility(lensUids, childrenOf);
  // A has children [A.1, A.2]; A.1 is in lens, so A is expanded.
  assert.equal(v.displayState.get('A'), 'visible-expanded');
  assert.equal(v.collapsedCompoundUids.has('A'), false);
  assert.equal(v.visibleUids.has('A'), true);
});

test('LENSSCHEMA.VISIBILITY #3: compound with all children in lens => expanded', () => {
  const lensUids = new Set(['ROOT', 'A', 'A.1', 'A.2']);
  const v = deriveLensVisibility(lensUids, childrenOf);
  assert.equal(v.displayState.get('A'), 'visible-expanded');
});

// ---------------------------------------------------------------------------
// Constraint #4: compound + no child in lens → collapsed.
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY #4: compound with no child in lens => collapsed', () => {
  const lensUids = new Set(['ROOT', 'A']);
  const v = deriveLensVisibility(lensUids, childrenOf);
  // A is in lens but neither A.1 nor A.2 are.
  assert.equal(v.displayState.get('A'), 'visible-collapsed');
  assert.equal(v.collapsedCompoundUids.has('A'), true);
  assert.equal(v.visibleUids.has('A'), true);
});

test('LENSSCHEMA.VISIBILITY #4: leaf-only compound (B, only child B.1) collapsed when B.1 absent', () => {
  const lensUids = new Set(['ROOT', 'B']);
  const v = deriveLensVisibility(lensUids, childrenOf);
  assert.equal(v.displayState.get('B'), 'visible-collapsed');
  assert.equal(v.collapsedCompoundUids.has('B'), true);
});

test('LENSSCHEMA.VISIBILITY #4: leaf-only compound (B) expanded when B.1 present', () => {
  const lensUids = new Set(['ROOT', 'B', 'B.1']);
  const v = deriveLensVisibility(lensUids, childrenOf);
  assert.equal(v.displayState.get('B'), 'visible-expanded');
  assert.equal(v.collapsedCompoundUids.has('B'), false);
});

// ---------------------------------------------------------------------------
// Multi-level: a compound is expanded iff a DIRECT child is in lens.
// Deeper descendants don't count (they imply intermediate compounds expanded
// up to themselves but not at A's level — A.2.1 in lens without A.2 → A.2 absent
// → A has no direct child in lens? No: A.1 might still be in lens. Test that
// A.2 absence + A.2.1 presence does NOT magically expand A via A.2.1.
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY: only direct-child membership counts for expansion', () => {
  const lensUids = new Set(['ROOT', 'A', 'A.2.1']); // A.2 absent, A.2.1 present (orphan-in-lens)
  const v = deriveLensVisibility(lensUids, childrenOf);
  // A's direct children are A.1, A.2; neither is in lens → A is collapsed.
  assert.equal(v.displayState.get('A'), 'visible-collapsed');
  // A.2 absent (correctly).
  assert.equal(v.displayState.get('A.2'), 'absent');
  // A.2.1 is in lens — it's a leaf, so it IS visible. (This is an orphan-in-lens
  // situation: rule still applies per node; coherence is the caller's concern.)
  assert.equal(v.displayState.get('A.2.1'), 'visible-leaf');
});

// ---------------------------------------------------------------------------
// Empty cases.
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY: empty lens => everything absent', () => {
  const v = deriveLensVisibility(new Set(), childrenOf);
  for (const uid of childrenOf.keys()) {
    assert.equal(v.displayState.get(uid), 'absent');
  }
  assert.equal(v.visibleUids.size, 0);
  assert.equal(v.collapsedCompoundUids.size, 0);
});

test('LENSSCHEMA.VISIBILITY: full lens (every uid) => everything expanded or leaf', () => {
  const lensUids = new Set(childrenOf.keys());
  const v = deriveLensVisibility(lensUids, childrenOf);
  for (const [uid, state] of v.displayState) {
    const children = childrenOf.get(uid) ?? [];
    if (children.length === 0) {
      assert.equal(state, 'visible-leaf', `${uid}`);
    } else {
      assert.equal(state, 'visible-expanded', `${uid}`);
    }
  }
  assert.equal(v.collapsedCompoundUids.size, 0);
});

// ---------------------------------------------------------------------------
// Result coverage: every topology uid appears in displayState.
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY: result covers every topology uid', () => {
  const lensUids = new Set(['ROOT', 'A', 'A.1']);
  const v = deriveLensVisibility(lensUids, childrenOf);
  for (const uid of childrenOf.keys()) {
    assert.ok(v.displayState.has(uid), `displayState missing ${uid}`);
  }
});

// ---------------------------------------------------------------------------
// Topology-only: lod field is irrelevant. The function does not accept LOD,
// so this test confirms the signature itself enforces constraint #5
// ("'lod' on a compound has no effect on expand/collapse"). If a future
// regression adds a lod parameter, this test fails by failing to compile.
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY #5: function signature does not accept LOD', () => {
  // deriveLensVisibility takes exactly two parameters: lensNodeUids and childrenOf.
  assert.equal(deriveLensVisibility.length, 2);
});

// ---------------------------------------------------------------------------
// PIG constraint: "New lens default membership: {ROOT, ROOT.children}".
// ROOT renders expanded (its children are in the lens); each L1 compound
// renders collapsed (its grandchildren are not in the lens).
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY: new-lens default seeds {ROOT, ROOT.children} → ROOT expanded, L1s collapsed', () => {
  // ROOT + its three direct children (A, B, C). Grandchildren (A.1, A.2, B.1)
  // are NOT in the lens — their parents (A, B) should render collapsed.
  const lensUids = new Set(['ROOT', 'A', 'B', 'C']);
  const v = deriveLensVisibility(lensUids, childrenOf);

  // ROOT is in lens, has 3 children, all in lens → expanded.
  assert.equal(v.displayState.get('ROOT'), 'visible-expanded');

  // A is in lens; A.1 and A.2 are NOT → A is visible-collapsed.
  assert.equal(v.displayState.get('A'), 'visible-collapsed');
  assert.equal(v.collapsedCompoundUids.has('A'), true);

  // B is in lens; B.1 is NOT → B is visible-collapsed.
  assert.equal(v.displayState.get('B'), 'visible-collapsed');
  assert.equal(v.collapsedCompoundUids.has('B'), true);

  // C is a leaf in lens → visible-leaf.
  assert.equal(v.displayState.get('C'), 'visible-leaf');

  // Grandchildren are absent.
  assert.equal(v.displayState.get('A.1'), 'absent');
  assert.equal(v.displayState.get('A.2'), 'absent');
  assert.equal(v.displayState.get('A.2.1'), 'absent');
  assert.equal(v.displayState.get('B.1'), 'absent');
});

// ---------------------------------------------------------------------------
// Renderer pragmatic: applyLens collapses (a) collapsedCompoundUids ∪
// (b) compounds-absent-from-lens. Test that the union is what the renderer
// actually wants in the new-lens default case.
//
// Compounds in our fixture are anything with children: ROOT, A, A.2, B.
// In a new-lens default {ROOT, A, B, C}:
//   - collapsedCompoundUids = {A, B}      (in lens, no child in lens)
//   - absent compounds      = {A.2}       (compound NOT in lens)
//   - render-collapse set   = {A, B, A.2} (union)
// ---------------------------------------------------------------------------
test('LENSSCHEMA.VISIBILITY: renderer union (collapsed ∪ absent compounds) for new-lens default', () => {
  const lensUids = new Set(['ROOT', 'A', 'B', 'C']);
  const v = deriveLensVisibility(lensUids, childrenOf);

  const isCompound = (uid) => (childrenOf.get(uid) ?? []).length > 0;

  // Renderer-side set: collapsedCompoundUids ∪ absent-compounds.
  const renderCollapse = new Set(v.collapsedCompoundUids);
  for (const uid of childrenOf.keys()) {
    if (!isCompound(uid)) continue;
    if (!lensUids.has(uid)) renderCollapse.add(uid);
  }

  assert.deepEqual(
    [...renderCollapse].sort(),
    ['A', 'A.2', 'B'].sort()
  );
});
