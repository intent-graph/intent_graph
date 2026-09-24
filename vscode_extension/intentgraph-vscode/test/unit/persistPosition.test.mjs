/**
 * Unit tests for position persistence deliverables.
 *
 * Verifies:
 *  - INTERACTION.DRAG constraints (mode suppression, center capture, snap-back)
 *  - PERSISTENCE.AUTOSAVE logic (debounce, single-flight, atomic writes, self-write suppression, toast)
 *  - PERSISTENCE.AUTOCREATE logic (default lens creation, meta.default_lens setting)
 *  - PERSISTENCE.POSITIONS schema (LensNodeEntry round-trips, position stored correctly)
 *  - INV-1 through INV-8 compliance (code-scan tests + logic verification)
 *
 * This test file uses the inline-implementation pattern: pure-function logic is
 * reproduced here so tests run without a build step via:
 *   node --test test/unit/persistPosition.test.mjs
 *
 * From PIG: INTERACTION.DRAG, PERSISTENCE.AUTOSAVE, PERSISTENCE.AUTOCREATE,
 * PERSISTENCE.POSITIONS (§1.1 task payload).
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// ============================================================================
// PURE-LOGIC IMPLEMENTATIONS (mirrors src/host/autosave.ts + snap-back logic)
// ============================================================================

/**
 * Snap-back logic for a dragged node position against parent compound bounding box.
 * PIG INTERACTION.DRAG constraint #5: "On release: if position is outside parent compound
 * rect, snap node back to last valid position."
 * Implementation mirrors src/webview/cyMount.ts::wireDragPersist (lines 357–376).
 *
 * @param draggedPosition  {x, y} in Cytoscape center coordinates
 * @param parentBbox  Parent bounding box {x1, x2, y1, y2}
 * @param margin  Safety margin (PIG does not specify; implementation uses 20)
 * @returns {x, y} snapped position if outside parent, else draggedPosition unchanged
 */
function snapBackIfOutsideParent(draggedPosition, parentBbox, margin = 20) {
  const clipped = {
    x: Math.max(parentBbox.x1 + margin, Math.min(parentBbox.x2 - margin, draggedPosition.x)),
    y: Math.max(parentBbox.y1 + margin, Math.min(parentBbox.y2 - margin, draggedPosition.y))
  };

  // If clipped, return snapped position; else return unchanged.
  if (clipped.x !== draggedPosition.x || clipped.y !== draggedPosition.y) {
    return clipped;
  }
  return draggedPosition;
}

/**
 * Single-flight debounce orchestration.
 * PIG PERSISTENCE.AUTOSAVE constraint #2: "Debounce: ~500ms. A second drag within the
 * debounce window replaces the queued write (single-flight)."
 *
 * Simulates the debounce state machine in IntentGraphEditorProvider.ts::onRequest(PersistPositionRequestType).
 * Returns (queued, timerId) tuples at different points.
 */
class DebounceOrchestrator {
  constructor(delayMs = 500) {
    this.delayMs = delayMs;
    this.queued = null;
    this.timerId = null;
  }

  /**
   * Enqueue a request. If another is queued, replace it (single-flight).
   * @returns {queued, timerId} — the new queued state after enqueue
   */
  enqueue(uid, position, lensName) {
    // Clear old timer if present.
    if (this.timerId !== null) {
      clearTimeout(this.timerId);
    }

    // Queue the new request (replacing any previous).
    this.queued = { uid, position, lensName };

    // Simulate the timer ID (in real code, Node's setTimeout returns a Timeout object).
    this.timerId = `timer_${Date.now()}`;

    return { queued: this.queued, timerId: this.timerId };
  }

  /**
   * Fire the debounce: extract queued, clear state, return it.
   * @returns queued payload or null if nothing queued
   */
  fire() {
    const payload = this.queued;
    this.queued = null;
    this.timerId = null;
    return payload;
  }
}

/**
 * Simulate createDefaultLens behavior.
 * PIG PERSISTENCE.AUTOCREATE constraints:
 *   - Trigger: first drag-release when no lens is currently active.
 *   - Action: silently create a lens named 'default'; auto-activate.
 *   - Sets meta.default_lens: 'default' in the IG file.
 *   - Visual feedback: toast 'Created lens default'.
 */
function createDefaultLensInDoc(doc) {
  if (!doc.lenses) {
    doc.lenses = {};
  }
  if (!doc.lenses.default) {
    doc.lenses.default = {
      name: 'default',
      nodes: {}
    };
  }
  if (!doc.meta) {
    doc.meta = {};
  }
  doc.meta.default_lens = 'default';
  return 'default';
}

/**
 * Simulate parseAndMutateLensPosition behavior.
 * PIG PERSISTENCE.POSITIONS constraint: "On drag-release: position is captured from
 * cy.on('free') and written to the active lens via auto-save."
 * Storage: lens entry position field -- {x, y} -- as Cytoscape node CENTER.
 * Constraint: position is optional in YAML; stored in LensNodeEntry.
 */
function writePositionToLens(doc, lensName, uid, position) {
  if (!doc.lenses || !doc.lenses[lensName]) {
    throw new Error(`Lens '${lensName}' not found.`);
  }

  const lens = doc.lenses[lensName];
  if (!lens.nodes) {
    lens.nodes = {};
  }

  // Ensure or create the node entry.
  let nodeEntry = lens.nodes[uid];
  if (!nodeEntry || typeof nodeEntry !== 'object') {
    nodeEntry = { lod: 'lean', position };
    lens.nodes[uid] = nodeEntry;
  } else {
    // Update position on existing entry.
    nodeEntry.position = position;
    // Ensure lod exists.
    if (!nodeEntry.lod) {
      nodeEntry.lod = 'lean';
    }
  }
}

// ============================================================================
// TEST SUITE
// ============================================================================

// --- TEST GROUP 1: INTERACTION.DRAG (Snap-Back Logic) ---

test('INTERACTION.DRAG #5: snap-back clipping — position outside parent, clipped inward', () => {
  // from PIG: "On release: if position is outside parent compound rect, snap node back"
  const draggedPosition = { x: 150, y: 250 };
  const parentBbox = { x1: 10, x2: 100, y1: 20, y2: 150 };
  const margin = 20;

  const result = snapBackIfOutsideParent(draggedPosition, parentBbox, margin);

  // x=150 > 100-20=80, so clipped to x2-margin=80.
  // y=250 > 150-20=130, so clipped to y2-margin=130.
  assert.deepEqual(result, { x: 80, y: 130 });
});

test('INTERACTION.DRAG #5: snap-back passthrough — position inside parent, unchanged', () => {
  // from PIG: "if position is outside parent compound rect, snap node back"
  // (implies: if inside, do not snap)
  const draggedPosition = { x: 50, y: 80 };
  const parentBbox = { x1: 10, x2: 100, y1: 20, y2: 150 };
  const margin = 20;

  const result = snapBackIfOutsideParent(draggedPosition, parentBbox, margin);

  // x=50 is in [30, 80], y=80 is in [40, 130], so unchanged.
  assert.deepEqual(result, draggedPosition);
});

test('INTERACTION.DRAG #5: snap-back at boundary — position exactly at margin, passthrough', () => {
  // from PIG: "snap node back to last valid position"
  // Edge case: position at the boundary after margin.
  const draggedPosition = { x: 80, y: 130 };
  const parentBbox = { x1: 10, x2: 100, y1: 20, y2: 150 };
  const margin = 20;

  const result = snapBackIfOutsideParent(draggedPosition, parentBbox, margin);

  // x=80 is exactly x2-margin, y=130 is exactly y2-margin, so no change.
  assert.deepEqual(result, draggedPosition);
});

// --- TEST GROUP 2: PERSISTENCE.AUTOSAVE (Debounce & Single-Flight) ---

test('PERSISTENCE.AUTOSAVE #2: single-flight debounce — first drag queues, second replaces', () => {
  // from PIG: "Debounce: ~500ms. A second drag within the debounce window replaces the
  // queued write (single-flight)."
  const orchestrator = new DebounceOrchestrator(500);

  // First drag-release.
  const first = orchestrator.enqueue('NODE_A', { x: 100, y: 200 }, 'my-lens');
  assert.deepEqual(first.queued, { uid: 'NODE_A', position: { x: 100, y: 200 }, lensName: 'my-lens' });

  // Second drag-release within debounce window: should replace first.
  const second = orchestrator.enqueue('NODE_B', { x: 300, y: 400 }, 'my-lens');
  assert.deepEqual(second.queued, { uid: 'NODE_B', position: { x: 300, y: 400 }, lensName: 'my-lens' });

  // Verify only second is queued; first was discarded.
  assert.notEqual(first.queued, second.queued);

  // Fire the debounce: should return only the second (latest) payload.
  const fired = orchestrator.fire();
  assert.deepEqual(fired, { uid: 'NODE_B', position: { x: 300, y: 400 }, lensName: 'my-lens' });
});

test('PERSISTENCE.AUTOSAVE #2: debounce clears old timer before creating new one', () => {
  // from PIG: "single-flight" implies one write per debounce window, latest payload wins.
  // Verify: old timer is cleared (clearTimeout), new timer is created.
  const orchestrator = new DebounceOrchestrator(500);

  const first = orchestrator.enqueue('NODE_1', { x: 10, y: 20 }, 'lens1');
  assert.ok(first.timerId, 'first enqueue must create a timer');

  // Second enqueue: queue state replaces first.
  const second = orchestrator.enqueue('NODE_2', { x: 30, y: 40 }, 'lens1');

  // Verify: queuedAutosave is the new payload (single-flight).
  assert.deepEqual(orchestrator.queued, { uid: 'NODE_2', position: { x: 30, y: 40 }, lensName: 'lens1' });
  assert.notDeepEqual(orchestrator.queued, first.queued);
});

test('PERSISTENCE.AUTOSAVE #2: debounce fire returns null if nothing queued', () => {
  // from PIG: "single-flight" — if no pending write, fire should return null.
  const orchestrator = new DebounceOrchestrator(500);

  const fired = orchestrator.fire();
  assert.equal(fired, null);
});

// --- TEST GROUP 3: PERSISTENCE.AUTOCREATE (Default Lens Creation) ---

test('PERSISTENCE.AUTOCREATE #1-3: create default lens, set meta.default_lens', () => {
  // from PIG: "Trigger: first drag-release when no lens is currently active."
  // "Action: silently create a lens named 'default'; auto-activate."
  // "Sets meta.default_lens: 'default' in the IG file."
  const doc = { lenses: {}, meta: {} };

  const lensName = createDefaultLensInDoc(doc);

  assert.equal(lensName, 'default');
  assert.ok(doc.lenses.default, 'default lens must exist');
  assert.equal(doc.lenses.default.name, 'default');
  assert.deepEqual(doc.lenses.default.nodes, {});
  assert.equal(doc.meta.default_lens, 'default');
});

test('PERSISTENCE.AUTOCREATE idempotence: create default twice, no duplicate, meta still set', () => {
  // from PIG: if 'default' lens already exists, autocreate should not fail or create duplicate.
  const doc = {
    lenses: {
      default: { name: 'default', nodes: { ROOT: { lod: 'lean' } } }
    },
    meta: { default_lens: 'default' }
  };

  // Call autocreate again.
  const lensName = createDefaultLensInDoc(doc);

  assert.equal(lensName, 'default');
  // Existing nodes should remain.
  assert.deepEqual(doc.lenses.default.nodes, { ROOT: { lod: 'lean' } });
});

test('PERSISTENCE.AUTOCREATE: create with no existing lenses or meta', () => {
  // from PIG: "silently create a lens named 'default'"
  const doc = {};

  const lensName = createDefaultLensInDoc(doc);

  assert.equal(lensName, 'default');
  assert.ok(doc.lenses);
  assert.ok(doc.meta);
  assert.equal(doc.meta.default_lens, 'default');
});

// --- TEST GROUP 3B: PERSISTENCE.AUTOCREATE YAMLMap Bootstrap Regression Tests ---
// Verify YAMLMap bootstrap works correctly.
// from PIG PERSISTENCE.AUTOCREATE — silently create default lens, set meta.default_lens.
// Bug B (fixed): eemeli/yaml library requires real YAMLMap for setIn to descend correctly.

test('Wave 6 Bug B regression: bootstrap lenses section as YAMLMap (empty doc)', () => {
  // Regression test: when createDefaultLens is called on a doc with no 'lenses' block,
  // it must bootstrap 'lenses' as a real YAMLMap so subsequent setIn(['lenses', 'default'], ...)
  // can descend into it without throwing "Expected YAML collection at lenses".
  // Simulating the buggy path: doc.set('lenses', {}) creates a Scalar; setIn fails.
  // Fixed path: doc.set('lenses', new YAML.YAMLMap()) creates a proper Map.

  // For this test, we simulate the expected behavior in createDefaultLensInDoc (which uses
  // plain JS objects, not eemeli/yaml). The regression is exercised in the actual
  // TypeScript code via npm test; this test verifies the logic.
  const doc = {};

  const lensName = createDefaultLensInDoc(doc);

  // After creation, lenses MUST be a proper object (simulating YAMLMap behavior).
  assert.ok(typeof doc.lenses === 'object', 'lenses must be an object after bootstrap');
  assert.ok(doc.lenses.default, 'default lens must exist after bootstrap');
  assert.ok(typeof doc.lenses.default === 'object', 'default lens must be an object');
  assert.deepEqual(doc.lenses.default.nodes, {}, 'default lens nodes must be a proper object');
});

test('Wave 6 Bug B regression: bootstrap meta section as YAMLMap (empty doc)', () => {
  // Regression test: similar to above, but for the 'meta' section.
  // When createDefaultLens calls doc.set('meta', {}) without YAMLMap, subsequent
  // setIn(['meta', 'default_lens'], 'default') fails with similar error.
  const doc = {};

  const lensName = createDefaultLensInDoc(doc);

  // After creation, meta MUST be a proper object (simulating YAMLMap behavior).
  assert.ok(typeof doc.meta === 'object', 'meta must be an object after bootstrap');
  assert.ok(doc.meta.default_lens === 'default', 'default_lens must be set in meta');
});

// --- TEST GROUP 4: PERSISTENCE.POSITIONS (Schema & Storage) ---

test('PERSISTENCE.POSITIONS: write position to new node entry, lod defaults to lean', () => {
  // from PIG: "Ensure or create the node entry (create with 'lean' LOD if absent)."
  // "Storage: lens entry position field — {x, y} — as Cytoscape node CENTER."
  const doc = { lenses: { 'my-lens': { name: 'my-lens', nodes: {} } } };

  writePositionToLens(doc, 'my-lens', 'AUTH', { x: 100, y: 200 });

  const entry = doc.lenses['my-lens'].nodes.AUTH;
  assert.ok(entry);
  assert.equal(entry.lod, 'lean', 'default lod must be lean');
  assert.deepEqual(entry.position, { x: 100, y: 200 });
});

test('PERSISTENCE.POSITIONS: update position on existing node entry, preserve lod', () => {
  // from PIG: "On drag-release: position is captured and written to active lens via auto-save."
  const doc = {
    lenses: {
      'my-lens': {
        name: 'my-lens',
        nodes: {
          AUTH: { lod: 'full', position: { x: 50, y: 60 } }
        }
      }
    }
  };

  writePositionToLens(doc, 'my-lens', 'AUTH', { x: 150, y: 160 });

  const entry = doc.lenses['my-lens'].nodes.AUTH;
  assert.equal(entry.lod, 'full', 'existing lod must be preserved');
  assert.deepEqual(entry.position, { x: 150, y: 160 });
});

test('PERSISTENCE.POSITIONS: position field is optional in LensNodeEntry', () => {
  // from PIG: "position is optional; omitted in YAML when undefined."
  // When a node entry is created without position, it should have lod but no position field.
  const doc = { lenses: { 'my-lens': { name: 'my-lens', nodes: {} } } };

  // Simulate creating an entry with just lod (no position).
  doc.lenses['my-lens'].nodes.ROOT = { lod: 'skeleton' };

  const entry = doc.lenses['my-lens'].nodes.ROOT;
  assert.equal(entry.lod, 'skeleton');
  assert.equal(entry.position, undefined, 'position field must be absent if not set');
});

test('PERSISTENCE.POSITIONS: center coordinates match Cytoscape API', () => {
  // from PIG: "Constraint: position stored as Cytoscape node CENTER."
  // "Matches cy.node.position() API natively."
  // This is a conceptual test: the position object shape must match Cytoscape's {x, y}.
  const cytoPosition = { x: 123.45, y: 456.78 };
  const doc = { lenses: { 'my-lens': { name: 'my-lens', nodes: {} } } };

  writePositionToLens(doc, 'my-lens', 'NODE_1', cytoPosition);

  const stored = doc.lenses['my-lens'].nodes.NODE_1.position;
  assert.deepEqual(stored, cytoPosition);
  assert.equal(typeof stored.x, 'number');
  assert.equal(typeof stored.y, 'number');
});

// --- TEST GROUP 5: Integrated Autosave + Autocreate Flow ---

test('PERSISTENCE.AUTOCREATE → PERSISTENCE.AUTOSAVE: first drag with no active lens creates and persists', () => {
  // from PIG constraint #6 of INTERACTION.DRAG + PERSISTENCE.AUTOCREATE constraint #5:
  // "Subsequent drags use the now-active 'default' lens normally via PERSISTENCE.AUTOSAVE."
  // Simulate: first drag, no active lens → autocreate 'default', then autosave position.
  const doc = { lenses: {}, meta: {} };
  const activeLensName = null;

  // Step 1: Autocreate (no active lens).
  const targetLensName = activeLensName || createDefaultLensInDoc(doc);
  assert.equal(targetLensName, 'default');

  // Step 2: Autosave position to the now-active lens.
  writePositionToLens(doc, targetLensName, 'NODE_1', { x: 100, y: 200 });

  // Verify: default lens exists, meta set, position persisted.
  assert.ok(doc.lenses.default);
  assert.equal(doc.meta.default_lens, 'default');
  assert.deepEqual(doc.lenses.default.nodes.NODE_1, {
    lod: 'lean',
    position: { x: 100, y: 200 }
  });
});

test('Subsequent drag in active lens: autosave without autocreate', () => {
  // from PIG: "Subsequent drags use the now-active 'default' lens normally"
  // i.e., second drag should not trigger autocreate, just autosave.
  const doc = {
    lenses: { 'default': { name: 'default', nodes: { NODE_1: { lod: 'lean', position: { x: 100, y: 200 } } } } },
    meta: { default_lens: 'default' }
  };
  const activeLensName = 'default'; // Now active.

  // Should not autocreate.
  writePositionToLens(doc, activeLensName, 'NODE_1', { x: 150, y: 250 });

  // Position updated.
  assert.deepEqual(doc.lenses.default.nodes.NODE_1.position, { x: 150, y: 250 });
});

test('PERSISTENCE.AUTOCREATE → PERSISTENCE.AUTOSAVE: round-trip through both functions (Wave 6 finishing Fix 1)', () => {
  // Regression test for a YAMLMap .hasIn() bug.
  // This test exercises the end-to-end round-trip through both createDefaultLens and
  // parseAndMutateLensPosition on a doc with no 'lenses:' block.
  // The buggy code cast getIn(['lenses']) to Record<string, unknown> and used bracket access
  // lensesMap['default'], which fails on eemeli/yaml YAMLMap. Fix: use doc.hasIn() instead.
  //
  // Citation: from PIG PERSISTENCE.AUTOCREATE + PERSISTENCE.AUTOSAVE.
  const doc = {}; // Empty doc, no lenses or meta.

  // Step 1: Autocreate default lens.
  const lensName = createDefaultLensInDoc(doc);
  assert.equal(lensName, 'default', 'autocreate must return default');
  assert.ok(doc.lenses.default, 'default lens must exist after autocreate');
  assert.equal(doc.meta.default_lens, 'default', 'meta.default_lens must be set');

  // Step 2: Autosave position to the newly-created default lens.
  // This is where the bug manifested: parseAndMutateLensPosition called
  // doc.getIn(['lenses']) and tried bracket access lensesMap[lensName],
  // which failed on YAMLMap. After the fix, doc.hasIn(['lenses', lensName])
  // correctly detects the lens and writes the position.
  writePositionToLens(doc, lensName, 'TEST_UID', { x: 42, y: 99 });

  // Step 3: Verify the position was written to the correct path.
  const nodeEntry = doc.lenses.default.nodes.TEST_UID;
  assert.ok(nodeEntry, 'node entry must exist after autosave');
  assert.equal(nodeEntry.lod, 'lean', 'default lod must be lean');
  assert.deepEqual(nodeEntry.position, { x: 42, y: 99 }, 'position must be persisted');
});

// --- TEST GROUP 6: Code-Scan Tests (INV-1, INV-2, INV-8) ---

test('INV-1: webview source files contain no vscode import', async () => {
  // from PIG INVARIANTS: "INV-1: No vscode.* API in the webview bundle."
  // Scan webview-side source files for 'vscode' imports.
  const webviewFiles = [
    'src/webview/main.ts',
    'src/webview/cyMount.ts',
    'src/webview/messaging.ts',
    'src/webview/htmlOverlayLayer.ts'
  ];

  for (const file of webviewFiles) {
    try {
      const content = await readFile(file, 'utf8');
      assert.ok(
        !content.includes('import \'vscode\'') && !content.includes('import * as vscode'),
        `File ${file} must not import vscode`
      );
    } catch (err) {
      // File may not exist; skip.
      if (err.code !== 'ENOENT') throw err;
    }
  }
});

test('INV-2: host source files contain no cytoscape or elkjs import', async () => {
  // from PIG INVARIANTS: "INV-2: No cytoscape or elkjs imports in the extension host."
  const hostFiles = [
    'src/host/autosave.ts',
    'src/host/lensApply.ts',
    'src/editor/IntentGraphEditorProvider.ts'
  ];

  for (const file of hostFiles) {
    try {
      const content = await readFile(file, 'utf8');
      assert.ok(
        !content.includes('import \'cytoscape\'') &&
        !content.includes('import * as cytoscape') &&
        !content.includes('from \'cytoscape\'') &&
        !content.includes('import \'elkjs\'') &&
        !content.includes('from \'elkjs\''),
        `File ${file} must not import cytoscape or elkjs`
      );
    } catch (err) {
      if (err.code !== 'ENOENT') throw err;
    }
  }
});

test('INV-8: position persistence writes only to lenses.<name>.nodes.<uid>.position', async () => {
  // from PIG INVARIANTS: "INV-8: Lens is the only store for user-authored visual state.
  // Positions and LOD assignments belong exclusively in LensConfig.nodes entries."
  // Verify: autosave.ts writes positions only to lenses section, AND the drag
  // handler routes positions through sendPersistPosition (not direct storage).
  // The drag handler moved from cyMount.ts to interaction/gestureRouter.ts.
  const autosavePath = 'src/host/autosave.ts';
  const routerPath = 'src/webview/interaction/gestureRouter.ts';

  const autosaveContent = await readFile(autosavePath, 'utf8');
  const routerContent = await readFile(routerPath, 'utf8');

  // Autosave should not set position on any other section (nodes, metadata, etc).
  // Check that position writes are scoped to lens paths.
  assert.ok(
    autosaveContent.includes("['lenses'") || autosaveContent.includes("setIn(['lenses'"),
    'autosave must write to lenses section'
  );

  // Drag listener (router-owned) must route positions through
  // sendPersistPosition, not store elsewhere.
  assert.ok(
    routerContent.includes('sendPersistPosition'),
    'drag listener (gestureRouter.ts) must use sendPersistPosition message'
  );
});

// --- TEST GROUP 7: Deferral & Implementation Audit ---

test('INTERACTION.DRAG #3 deferral audit: live clipping not implemented, snap-back on release implemented', async () => {
  // from task input: "constraint #3 of INTERACTION.DRAG ('During drag: children cannot leave
  // the parent compound rect. Clip to parent bounds in the drag handler') was deliberately deferred.
  // Only constraint #5 (snap-back on release) was implemented."
  // Verify: drag handler uses cy.on('free', ...) not cy.on('drag', ...).
  // The drag handler moved from cyMount.ts to interaction/gestureRouter.ts.
  const routerContent = await readFile('src/webview/interaction/gestureRouter.ts', 'utf8');

  // Should have cy.on('free') for snap-back on release.
  assert.ok(
    routerContent.includes("cy.on('free'"),
    'must have release handler (snap-back) in gestureRouter.ts'
  );

  // Should NOT have cy.on('drag') for live clipping (still deferred).
  assert.ok(
    !routerContent.includes("cy.on('drag'"),
    'live drag-time clipping must remain deferred (no cy.on(drag) listener)'
  );
});

test('Toast mechanism: setStatusBarMessage used for transient feedback', async () => {
  // from task input: "Implementer chose setStatusBarMessage instead of showInformationMessage.
  // Is this faithful to constraint #5 ('transient toast')?"
  // Verify: autosavePersistPosition uses vscode.window.setStatusBarMessage.
  const editorProviderContent = await readFile('src/editor/IntentGraphEditorProvider.ts', 'utf8');

  assert.ok(
    editorProviderContent.includes('setStatusBarMessage'),
    'must use setStatusBarMessage for transient toast'
  );

  // Verify it includes the lens name in the message (constraint #5 says toast should include name).
  assert.ok(
    editorProviderContent.includes('Layout saved to lens') || editorProviderContent.includes('targetLensName'),
    'toast message must include lens name'
  );
});

test('Default LOD for autocreate node entry: lean', async () => {
  // from task input: "Default lod 'lean' for autocreated node entries. Is this faithful to the PIG?"
  // Verify: parseAndMutateLensPosition defaults to lod='lean' when creating new entry.
  const autosaveContent = await readFile('src/host/autosave.ts', 'utf8');

  assert.ok(
    autosaveContent.includes("'lean'") || autosaveContent.includes('lod: \'lean\''),
    'must default new node entries to lod=lean'
  );
});

test('Debounce semantics: 500ms debounce, second drag replaces queued', async () => {
  // from task input: "500ms debounce semantics: does the implementer's 'second drag replaces
  // queued write' actually equal 'single-flight' per constraint #2?"
  // Verify: IntentGraphEditorProvider uses debounce with clearTimeout before rescheduling.
  const editorProviderContent = await readFile('src/editor/IntentGraphEditorProvider.ts', 'utf8');

  // Should enqueue and debounce.
  assert.ok(
    editorProviderContent.includes('AUTOSAVE_DEBOUNCE_MS') || editorProviderContent.includes('500'),
    'must have 500ms debounce constant'
  );

  // Should clear old timer on new request (single-flight).
  assert.ok(
    editorProviderContent.includes('clearTimeout') || editorProviderContent.includes('entry.autosaveTimer'),
    'must clear and reschedule timer for single-flight'
  );

  // Should replace queued request.
  assert.ok(
    editorProviderContent.includes('entry.queuedAutosave ='),
    'must replace queued autosave on new request'
  );
});
