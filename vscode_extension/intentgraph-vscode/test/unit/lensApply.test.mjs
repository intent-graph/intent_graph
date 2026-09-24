/**
 * Unit tests for lensConfigToPayload (src/host/lensApply.ts).
 *
 * The function is pure TypeScript with type-only imports (erased at runtime).
 * The logic is reproduced inline here so the test runs without a build step:
 *   node --test test/unit/lensApply.test.mjs
 *
 * If a build step is later added, replace the inline implementation with:
 *   import { lensConfigToPayload } from '../../dist/lensApply.cjs';
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ---------------------------------------------------------------------------
// Inline implementation — mirrors src/host/lensApply.ts exactly.
// Update here whenever lensApply.ts changes.
// Updated to handle LensNodeEntry {lod, position?} and migration detection.
// ---------------------------------------------------------------------------
class LensSchemaMigrationRequired extends Error {
  constructor() {
    super(
      'LensConfig schema migration required. Run (from the repo root):\n' +
      '  python3 src/scripts/migrate_lens_config_v2.py <your-ig-file>'
    );
    this.name = 'LensSchemaMigrationRequired';
  }
}

function lensConfigToPayload(lensConfig, availableNodes, availableLinks = new Set()) {
  const diagnostics = [];

  const filteredNodes = {};
  const filteredPositions = {};
  for (const [uid, entry] of Object.entries(lensConfig.nodes)) {
    // Detect old bare-string shape and throw migration error.
    if (typeof entry === 'string') {
      throw new LensSchemaMigrationRequired();
    }

    // New shape: entry is LensNodeEntry with { lod, position? }.
    const lod = (entry).lod;
    if (typeof lod !== 'string') {
      throw new LensSchemaMigrationRequired();
    }

    if (availableNodes.has(uid)) {
      filteredNodes[uid] = lod;
      const pos = entry.position;
      if (pos && typeof pos.x === 'number' && typeof pos.y === 'number') {
        filteredPositions[uid] = { x: pos.x, y: pos.y };
      }
    } else {
      diagnostics.push({
        level: 'warn',
        uid,
        message: `node '${uid}' not found in graph (stale UID — node may have been deleted)`
      });
    }
  }

  const filteredLinks = [];
  for (const linkUid of (lensConfig.intentlinks ?? [])) {
    if (availableLinks.size === 0 || availableLinks.has(linkUid)) {
      filteredLinks.push(linkUid);
    } else {
      diagnostics.push({
        level: 'warn',
        uid: linkUid,
        message: `link '${linkUid}' not found in graph (stale UID)`
      });
    }
  }

  return {
    name: lensConfig.name,
    nodes: filteredNodes,
    positions: filteredPositions,
    intentlinks: filteredLinks,
    diagnostics
  };
}
// ---------------------------------------------------------------------------

// Case 1: All UIDs present with new LensNodeEntry shape (lod + optional position)
test('all UIDs present: nodes and intentlinks mapped 1:1, diagnostics empty', () => {
  const config = {
    name: 'auth-flow',
    description: 'Auth focus',
    nodes: {
      ROOT: { lod: 'lean' },
      AUTH: { lod: 'full', position: { x: 100, y: 200 } },
      AUTH_1: { lod: 'skeleton' }
    },
    intentlinks: ['AUTH_AUTH_1', 'ROOT_AUTH']
  };
  const availableNodes = new Set(['ROOT', 'AUTH', 'AUTH_1']);
  const availableLinks = new Set(['AUTH_AUTH_1', 'ROOT_AUTH']);

  const payload = lensConfigToPayload(config, availableNodes, availableLinks);

  assert.deepEqual(payload.nodes, { ROOT: 'lean', AUTH: 'full', AUTH_1: 'skeleton' });
  assert.deepEqual(payload.intentlinks, ['AUTH_AUTH_1', 'ROOT_AUTH']);
  assert.deepEqual(payload.diagnostics, []);
  assert.equal(payload.name, 'auth-flow');
});

// Case 2: Stale node UID — entry filtered out, single warn diagnostic with that uid
test('stale node UID: filtered from nodes, warn diagnostic emitted', () => {
  const config = {
    name: 'focused',
    nodes: {
      ROOT: { lod: 'lean' },
      AUTH: { lod: 'full' },
      STALE_NODE: { lod: 'skeleton' }
    },
    intentlinks: []
  };
  const availableNodes = new Set(['ROOT', 'AUTH']);
  const availableLinks = new Set();

  const payload = lensConfigToPayload(config, availableNodes, availableLinks);

  assert.deepEqual(Object.keys(payload.nodes), ['ROOT', 'AUTH']);
  assert.ok(!('STALE_NODE' in payload.nodes), 'STALE_NODE must not appear in filtered nodes');
  assert.equal(payload.diagnostics.length, 1);
  assert.equal(payload.diagnostics[0].level, 'warn');
  assert.equal(payload.diagnostics[0].uid, 'STALE_NODE');
  assert.ok(payload.diagnostics[0].message.includes('STALE_NODE'));
});

// Case 3: Stale intentlink UID — filtered from intentlinks, single warn diagnostic
test('stale intentlink UID: filtered from intentlinks, warn diagnostic emitted', () => {
  const config = {
    name: 'focused',
    nodes: { ROOT: { lod: 'lean' }, AUTH: { lod: 'full' } },
    intentlinks: ['ROOT_AUTH', 'STALE_LINK_UID']
  };
  const availableNodes = new Set(['ROOT', 'AUTH']);
  const availableLinks = new Set(['ROOT_AUTH']); // STALE_LINK_UID absent

  const payload = lensConfigToPayload(config, availableNodes, availableLinks);

  assert.deepEqual(payload.intentlinks, ['ROOT_AUTH']);
  assert.ok(!payload.intentlinks.includes('STALE_LINK_UID'), 'stale link must be filtered');
  assert.equal(payload.diagnostics.length, 1);
  assert.equal(payload.diagnostics[0].level, 'warn');
  assert.equal(payload.diagnostics[0].uid, 'STALE_LINK_UID');
  assert.ok(payload.diagnostics[0].message.includes('STALE_LINK_UID'));
});

// Case 4: Empty nodes and intentlinks — empty payload, empty diagnostics
test('empty nodes and intentlinks: empty payload, empty diagnostics', () => {
  const config = {
    name: 'empty-lens',
    nodes: {},
    intentlinks: []
  };
  const availableNodes = new Set(['ROOT', 'AUTH']);
  const availableLinks = new Set(['ROOT_AUTH']);

  const payload = lensConfigToPayload(config, availableNodes, availableLinks);

  assert.deepEqual(payload.nodes, {});
  assert.deepEqual(payload.intentlinks, []);
  assert.deepEqual(payload.diagnostics, []);
});

// Case 5a: Migration detection — old bare-string shape throws migration error
test('migration detection: old bare-string shape throws LensSchemaMigrationRequired', () => {
  const config = {
    name: 'old-format',
    nodes: { ROOT: 'lean', AUTH: 'full' },  // Old shape: bare strings, not LensNodeEntry
    intentlinks: []
  };
  const availableNodes = new Set(['ROOT', 'AUTH']);

  assert.throws(
    () => lensConfigToPayload(config, availableNodes),
    LensSchemaMigrationRequired,
    'old bare-string shape must throw migration error'
  );
});

// Case 5b: New shape with position is accepted and position is ignored on output
test('new shape with position: lod extracted, position passed through but not on LensApplyPayload', () => {
  const config = {
    name: 'positioned-lens',
    nodes: {
      ROOT: { lod: 'lean', position: { x: 0, y: 0 } },
      AUTH: { lod: 'full', position: { x: 100, y: 200 } },
      AUTH_1: { lod: 'skeleton' }  // position optional
    },
    intentlinks: []
  };
  const availableNodes = new Set(['ROOT', 'AUTH', 'AUTH_1']);

  const payload = lensConfigToPayload(config, availableNodes);

  // LensApplyPayload.nodes should contain LOD values only (positions are stored in full LensConfig, not sent to webview).
  assert.deepEqual(payload.nodes, {
    ROOT: 'lean',
    AUTH: 'full',
    AUTH_1: 'skeleton'
  });
  assert.deepEqual(payload.diagnostics, []);
});

// Case 6: name and description propagate to payload
test('name and description propagate to payload', () => {
  const config = {
    name: 'my-lens',
    description: 'A focused view on auth',
    nodes: { ROOT: { lod: 'lean' } },
    intentlinks: []
  };
  const availableNodes = new Set(['ROOT']);
  const availableLinks = new Set();

  const payload = lensConfigToPayload(config, availableNodes, availableLinks);

  assert.equal(payload.name, 'my-lens');
  // description is not forwarded to LensApplyPayload (spec §9 does not include it);
  // confirm it is absent on the payload (the wire format carries only name/nodes/intentlinks/diagnostics)
  assert.ok(!('description' in payload), 'description must not appear on LensApplyPayload');
});

// Case 7: intentlinks=undefined (field absent) treated as empty — no crash
test('intentlinks absent (undefined): treated as empty, no crash', () => {
  const config = {
    name: 'no-links-lens',
    nodes: { ROOT: { lod: 'full' } }
    // intentlinks intentionally omitted
  };
  const availableNodes = new Set(['ROOT']);

  const payload = lensConfigToPayload(config, availableNodes);

  assert.deepEqual(payload.intentlinks, []);
  assert.deepEqual(payload.diagnostics, []);
});

// Case 8 (Coord-frame fix): position field is propagated to payload.positions
// for available nodes; missing position means uid simply absent from positions.
test('positions: propagated for available nodes; absent when no position', () => {
  const config = {
    name: 'pos-lens',
    nodes: {
      ROOT: { lod: 'lean' },                                            // no position
      'L1.A': { lod: 'lean', position: { x: 100, y: 200 } },             // has position
      'L1.B': { lod: 'full', position: { x: 300, y: 400 } },             // has position
      'L1.C': { lod: 'lean' },                                          // no position
      'STALE': { lod: 'lean', position: { x: 999, y: 999 } }            // not available
    }
  };
  const availableNodes = new Set(['ROOT', 'L1.A', 'L1.B', 'L1.C']);

  const payload = lensConfigToPayload(config, availableNodes);

  assert.deepEqual(payload.positions, {
    'L1.A': { x: 100, y: 200 },
    'L1.B': { x: 300, y: 400 }
  });
  // ROOT and L1.C have no position field → absent from payload.positions.
  assert.equal(payload.positions['ROOT'], undefined);
  assert.equal(payload.positions['L1.C'], undefined);
  // STALE is filtered out entirely (it raised a diagnostic).
  assert.equal(payload.positions['STALE'], undefined);
  assert.equal(payload.diagnostics.length, 1);
});

test('positions: empty object when no node has a position', () => {
  const config = {
    name: 'no-pos-lens',
    nodes: { ROOT: { lod: 'lean' }, 'L1.A': { lod: 'full' } }
  };
  const availableNodes = new Set(['ROOT', 'L1.A']);

  const payload = lensConfigToPayload(config, availableNodes);

  assert.deepEqual(payload.positions, {});
});
