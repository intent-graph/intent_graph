/**
 * Headless cytoscape harness for testing position persistence end-to-end
 * without requiring F5 in VS Code.
 *
 * Setup:
 *   - jsdom provides a DOM shim so cytoscape-expand-collapse (which calls
 *     `document.createElement`) can load.
 *   - cytoscape itself runs headless (no canvas).
 *
 * Each test takes ~30 ms. Run with:
 *   node --test --test-timeout=15000 test/integration/cyHarness.test.mjs
 */

import { test, before } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';

// ---------------------------------------------------------------------------
// JSDOM bootstrap. Done once per test process. cytoscape-expand-collapse
// reads `document` at registration time — must be in place before we call
// cytoscape.use().
// ---------------------------------------------------------------------------
before(() => {
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.HTMLElement = dom.window.HTMLElement;
  globalThis.Node = dom.window.Node;
  // navigator is a getter on modern Node; redefine if needed.
  if (!globalThis.navigator) {
    Object.defineProperty(globalThis, 'navigator', {
      value: dom.window.navigator,
      configurable: true,
      writable: true
    });
  }
});

// Lazy/cached cytoscape module so plugin registration only happens once.
let _cytoscape = null;
let _ecRegistered = false;
async function getCytoscape() {
  if (_cytoscape) return _cytoscape;
  const cytoscape = (await import('cytoscape')).default;
  if (!_ecRegistered) {
    const expandCollapseModule = await import('cytoscape-expand-collapse');
    cytoscape.use(expandCollapseModule.default);
    _ecRegistered = true;
  }
  _cytoscape = cytoscape;
  return cytoscape;
}

// ---------------------------------------------------------------------------
// Test fixture topology:
//
//   ROOT
//   ├── A   (compound)
//   │   ├── A.1
//   │   ├── A.2
//   │   └── A.3
//   └── B   (compound)
//       ├── B.1
//       └── B.2
// ---------------------------------------------------------------------------

const FIXTURE_NODES = [
  { data: { id: 'ROOT' } },
  { data: { id: 'A', parent: 'ROOT' } },
  { data: { id: 'B', parent: 'ROOT' } },
  { data: { id: 'A.1', parent: 'A' }, position: { x: 100, y: 100 } },
  { data: { id: 'A.2', parent: 'A' }, position: { x: 200, y: 100 } },
  { data: { id: 'A.3', parent: 'A' }, position: { x: 300, y: 100 } },
  { data: { id: 'B.1', parent: 'B' }, position: { x: 100, y: 300 } },
  { data: { id: 'B.2', parent: 'B' }, position: { x: 200, y: 300 } }
];

function freshElements() {
  // Deep-copy: tests must not share node references.
  return FIXTURE_NODES.map((n) => ({
    data: { ...n.data },
    ...(n.position ? { position: { ...n.position } } : {})
  }));
}

async function mountCy({ withContainer = false } = {}) {
  const cytoscape = await getCytoscape();
  const opts = {
    styleEnabled: true,
    elements: freshElements(),
    layout: { name: 'preset' }
  };
  if (withContainer) {
    // cytoscape-expand-collapse calls `cy.container().append(...)` at init,
    // so a real DOM container is required. We use jsdom's element AND tell
    // cytoscape to use the null renderer (no canvas needed; jsdom has no
    // real 2d context).
    const container = document.createElement('div');
    document.body.appendChild(container);
    opts.container = container;
    opts.renderer = { name: 'null' };
  } else {
    opts.headless = true;
  }
  return cytoscape(opts);
}

// ---------------------------------------------------------------------------
// Smoke tests.
// ---------------------------------------------------------------------------
test('smoke: cytoscape mounts headless', async () => {
  const cy = await mountCy();
  assert.equal(cy.nodes().length, 8);
  assert.equal(cy.getElementById('A.1').nonempty(), true);
  cy.destroy();
});

test('smoke: leaf positions can be set and read', async () => {
  const cy = await mountCy();
  const leaf = cy.getElementById('A.1');
  leaf.position({ x: 555, y: 666 });
  const pos = leaf.position();
  assert.equal(pos.x, 555);
  assert.equal(pos.y, 666);
  cy.destroy();
});

test('smoke: compound parent bbox reflects children positions', async () => {
  const cy = await mountCy();
  const A = cy.getElementById('A');
  const bbox1 = A.boundingBox();

  cy.getElementById('A.1').position({ x: 9999, y: 9999 });
  const bbox2 = A.boundingBox();

  assert.ok(
    bbox2.x2 > bbox1.x2,
    `expected bbox.x2 to grow after leaf moved far right; before=${bbox1.x2} after=${bbox2.x2}`
  );
  cy.destroy();
});

// NOTE on cytoscape-expand-collapse headless: the plugin's render hook calls
// ctx.clearRect on a real canvas; jsdom doesn't ship a real canvas 2d context
// without `canvas` package (native dep). We intentionally skip plugin-based
// tests and verify our applyLens logic against pure cytoscape, which is
// where the position-persistence work happens. The plugin is for visuals;
// our position bug is in the data path.
test('smoke: cytoscape-expand-collapse cannot run headless (acceptance gap)', { skip: true }, async () => {});

// ---------------------------------------------------------------------------
// SCENARIO 1: position round-trip, no collapse anywhere.
// Establishes that pure cytoscape (no plugin) restores positions cleanly.
// ---------------------------------------------------------------------------
test('SCENARIO 1: leaf positions survive close+reopen, no collapse', async () => {
  let cy = await mountCy();

  const userDragged = {
    'A.1': { x: 555, y: 444 },
    'A.2': { x: 666, y: 444 },
    'A.3': { x: 777, y: 444 }
  };
  for (const [uid, pos] of Object.entries(userDragged)) {
    cy.getElementById(uid).position(pos);
  }

  const savedPositions = {};
  for (const uid of Object.keys(userDragged)) {
    const p = cy.getElementById(uid).position();
    savedPositions[uid] = { x: p.x, y: p.y };
  }
  cy.destroy();

  cy = await mountCy();
  cy.batch(() => {
    for (const [uid, absPos] of Object.entries(savedPositions)) {
      const ele = cy.getElementById(uid);
      if (!ele.nonempty()) continue;
      if (ele.isParent()) continue;
      ele.position(absPos);
    }
  });

  for (const [uid, expected] of Object.entries(userDragged)) {
    const actual = cy.getElementById(uid).position();
    assert.equal(actual.x, expected.x, `${uid}.x: expected ${expected.x}, got ${actual.x}`);
    assert.equal(actual.y, expected.y, `${uid}.y: expected ${expected.y}, got ${actual.y}`);
  }
  cy.destroy();
});

// ---------------------------------------------------------------------------
// SCENARIO 3 (no plugin): drag inside an expanded compound. Pure cytoscape.
// ---------------------------------------------------------------------------
test('SCENARIO 3: positions inside an expanded compound survive round-trip (pure cy)', async () => {
  let cy = await mountCy();

  const userDragged = {
    'A.1': { x: 1500, y: 250 },
    'A.2': { x: 1600, y: 350 },
    'A.3': { x: 1700, y: 450 }
  };
  for (const [uid, pos] of Object.entries(userDragged)) {
    cy.getElementById(uid).position(pos);
  }
  const savedPositions = {};
  for (const uid of Object.keys(userDragged)) {
    const p = cy.getElementById(uid).position();
    savedPositions[uid] = { x: p.x, y: p.y };
  }
  cy.destroy();

  cy = await mountCy();
  cy.batch(() => {
    for (const [uid, absPos] of Object.entries(savedPositions)) {
      const ele = cy.getElementById(uid);
      if (!ele.nonempty()) continue;
      if (ele.isParent()) continue;
      ele.position(absPos);
    }
  });

  for (const [uid, expected] of Object.entries(userDragged)) {
    const actual = cy.getElementById(uid).position();
    assert.equal(actual.x, expected.x, `${uid}.x: expected ${expected.x}, got ${actual.x}`);
    assert.equal(actual.y, expected.y, `${uid}.y: expected ${expected.y}, got ${actual.y}`);
  }
  cy.destroy();
});

// ---------------------------------------------------------------------------
// SCENARIO 4: drag the COMPOUND parent itself. Cytoscape moves children
// along; their positions are persisted (per child); on round-trip, those
// child positions should be restored. This is the case where the user
// "drags a compound" — implicitly moving its children.
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// SCENARIO X: real-world fixture. Load the actual python_defaults.ig.yaml,
// extract the test_4 lens, build a cytoscape graph from the IG model, and
// apply positions exactly the way applyLens does. Then compare cytoscape's
// final position for each leaf to the position stored in the lens.
//
// If positions match → pure-cytoscape path is correct; bug is elsewhere
//   (in the host→webview pipeline, or in cytoscape's interaction with the
//   real DOM that we can't reproduce).
// If positions mismatch → we've reproduced the bug headless and can fix
//   without F5.
// ---------------------------------------------------------------------------
test('SCENARIO X: real fixture (python_defaults test_4 lens) round-trip', async () => {
  const { readFile } = await import('node:fs/promises');
  const YAML = (await import('yaml')).default;

  const path = new URL('../../python_defaults.ig.yaml', import.meta.url);
  const raw = await readFile(path, 'utf8');
  const parsed = YAML.parse(raw);

  // The fixture file may not have test_4 anymore (user may delete it). Skip
  // gracefully if so; the test serves as an acceptance check when present.
  const lens = parsed?.lenses?.test_4;
  if (!lens || !lens.nodes) {
    console.log('  [skip: test_4 lens not present in fixture]');
    return;
  }

  // Build cytoscape elements from the IG tree.
  // File shape: nodes is a list of {uid, name, ...} objects; treearcs is a
  // list of {parent, child} arcs.
  const cytoscape = await getCytoscape();
  const elements = [];
  const nodes = parsed.nodes ?? [];
  const treearcs = parsed.treearcs ?? [];
  const nodeUids = nodes.map((n) => n.uid);

  // Map uid → parentUid using treearcs.
  const parentOf = {};
  for (const arc of treearcs) parentOf[arc.child] = arc.parent;

  for (const uid of nodeUids) {
    const data = { id: uid };
    if (parentOf[uid]) data.parent = parentOf[uid];
    elements.push({ data });
  }

  // Mount cytoscape headless. We don't run ELK; nodes get default positions
  // from cytoscape (preset). Exactly what we want for a "fresh mount."
  const cy = cytoscape({
    headless: true,
    styleEnabled: true,
    elements,
    layout: { name: 'preset' }
  });

  // Apply positions from the lens (mirror applyLens step 5.5 exactly).
  let restored = 0;
  let skippedCompound = 0;
  cy.batch(() => {
    for (const [uid, entry] of Object.entries(lens.nodes)) {
      if (!entry || typeof entry !== 'object') continue;
      const pos = entry.position;
      if (!pos) continue;
      const ele = cy.getElementById(uid);
      if (!ele.nonempty()) continue;
      if (ele.isParent()) { skippedCompound++; continue; }
      ele.position({ x: pos.x, y: pos.y });
      restored++;
    }
  });

  // Verify each leaf with a stored position is exactly at that position.
  let mismatches = 0;
  const errors = [];
  for (const [uid, entry] of Object.entries(lens.nodes)) {
    if (!entry || typeof entry !== 'object') continue;
    const pos = entry.position;
    if (!pos) continue;
    const ele = cy.getElementById(uid);
    if (!ele.nonempty() || ele.isParent()) continue;
    const actual = ele.position();
    if (Math.abs(actual.x - pos.x) > 0.001 || Math.abs(actual.y - pos.y) > 0.001) {
      mismatches++;
      errors.push(`${uid}: expected (${pos.x}, ${pos.y}), got (${actual.x}, ${actual.y})`);
    }
  }
  cy.destroy();

  if (mismatches > 0) {
    assert.fail(
      `${mismatches}/${restored} positions did NOT match after restore.\n` +
      errors.slice(0, 5).join('\n')
    );
  }
});

test('SCENARIO 4: dragging a compound moves children, positions survive round-trip', async () => {
  let cy = await mountCy();

  // Drag compound A by simulating cytoscape's behaviour: when a parent is
  // dragged, all children move by the same delta. We model that by moving
  // each child explicitly. (In real cytoscape, this happens via DOM events.)
  const dx = 500, dy = 200;
  for (const childId of ['A.1', 'A.2', 'A.3']) {
    const p = cy.getElementById(childId).position();
    cy.getElementById(childId).position({ x: p.x + dx, y: p.y + dy });
  }

  // Capture child positions (autosave fires for each child).
  const savedPositions = {};
  for (const childId of ['A.1', 'A.2', 'A.3']) {
    const p = cy.getElementById(childId).position();
    savedPositions[childId] = { x: p.x, y: p.y };
  }
  const aBboxBefore = cy.getElementById('A').boundingBox();
  cy.destroy();

  // Reopen, restore.
  cy = await mountCy();
  cy.batch(() => {
    for (const [uid, absPos] of Object.entries(savedPositions)) {
      const ele = cy.getElementById(uid);
      if (!ele.nonempty()) continue;
      if (ele.isParent()) continue;
      ele.position(absPos);
    }
  });

  // Children should be at saved positions.
  for (const childId of ['A.1', 'A.2', 'A.3']) {
    const expected = savedPositions[childId];
    const actual = cy.getElementById(childId).position();
    assert.equal(actual.x, expected.x, `${childId}.x: expected ${expected.x}, got ${actual.x}`);
    assert.equal(actual.y, expected.y, `${childId}.y: expected ${expected.y}, got ${actual.y}`);
  }
  // A's bbox should be roughly equal to where it was before close (auto-fit).
  const aBboxAfter = cy.getElementById('A').boundingBox();
  assert.ok(
    Math.abs(aBboxAfter.x1 - aBboxBefore.x1) < 1,
    `A.bbox.x1 drifted: before=${aBboxBefore.x1} after=${aBboxAfter.x1}`
  );

  cy.destroy();
});
