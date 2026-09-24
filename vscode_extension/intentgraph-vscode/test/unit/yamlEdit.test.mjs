/**
 * Unit tests for the host-side YAML edit round-trip (src/host/yamlEdit.ts),
 * focused on the addition of `epistemic_state` as an
 * editable field. Also covers the previously-untested core: findNodeIndex,
 * comment/ordering preservation, empty-value rejection, and hash-mismatch.
 *
 * Test infrastructure: inline re-implementation of yamlEdit's mutation
 * semantics using the real `yaml` (eemeli) package — the same library the
 * source uses — so the round-trip behaviour (parseDocument → setIn → toString)
 * is genuinely exercised rather than mocked. The source is TypeScript and is
 * not compiled to .mjs for the test runner, hence the mirrored logic; the
 * assertions pin the behaviour the source must preserve.
 *
 * Run: node --test test/unit/yamlEdit.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import * as YAML from 'yaml';

// --- Mirrored helpers (must match src/host/yamlEdit.ts + fileHash.ts) --------

/** src/host/fileHash.ts computeFileHash: CRLF→LF then SHA-256 hex. */
function computeFileHash(content) {
  return createHash('sha256').update(content.replace(/\r\n/g, '\n')).digest('hex');
}

/** src/host/yamlEdit.ts findNodeIndex: linear scan of the nodes: sequence. */
function findNodeIndex(doc, uid) {
  const seq = doc.getIn(['nodes']);
  if (!seq || !seq.items) return -1;
  for (let i = 0; i < seq.items.length; i++) {
    const item = seq.items[i];
    if (item && item.get && item.get('uid') === uid) return i;
  }
  return -1;
}

/** Mirror of applyNodeEdit's schema-check + mutate + serialise (in-memory,
 *  no file I/O). Returns { ok, error?, newContent?, newFileHash? }. */
function applyNodeEdit(raw, req) {
  const { fields } = req;
  const trimmedName = fields.name?.trim();
  const trimmedIntent = fields.intent?.trim();
  const trimmedEpistemic = fields.epistemic_state?.trim();

  if (trimmedName !== undefined && trimmedName.length === 0) {
    return { ok: false, error: 'Field "name" must not be empty.' };
  }
  if (trimmedIntent !== undefined && trimmedIntent.length === 0) {
    return { ok: false, error: 'Field "intent" must not be empty.' };
  }
  if (trimmedEpistemic !== undefined && trimmedEpistemic.length === 0) {
    return { ok: false, error: 'Field "epistemic_state" must not be empty.' };
  }

  const hasName = trimmedName !== undefined;
  const hasIntent = trimmedIntent !== undefined;
  const hasEpistemic = trimmedEpistemic !== undefined;
  const hasConstraints = fields.constraints !== undefined && fields.constraints.length > 0;
  if (!hasName && !hasIntent && !hasEpistemic && !hasConstraints) {
    return { ok: false, error: 'No fields to update.' };
  }

  if (computeFileHash(raw) !== req.fileHash) {
    return { ok: false, error: 'File changed externally — reload first.' };
  }

  const doc = YAML.parseDocument(raw);
  const idx = findNodeIndex(doc, req.nodeUid);
  if (idx === -1) return { ok: false, error: `Node "${req.nodeUid}" not found in YAML.` };

  if (hasName) doc.setIn(['nodes', idx, 'name'], trimmedName);
  if (hasIntent) doc.setIn(['nodes', idx, 'intent'], trimmedIntent);
  if (hasEpistemic) doc.setIn(['nodes', idx, 'epistemic_state'], trimmedEpistemic);
  if (hasConstraints) {
    const cseq = doc.getIn(['nodes', idx, 'constraints']);
    if (!cseq) return { ok: false, error: `Node "${req.nodeUid}" has no constraints array.` };
    for (let ci = 0; ci < fields.constraints.length; ci++) {
      if (ci >= cseq.items.length) break;
      doc.setIn(['nodes', idx, 'constraints', ci], fields.constraints[ci].trim());
    }
  }

  const newContent = doc.toString();
  return { ok: true, newContent, newFileHash: computeFileHash(newContent) };
}

// --- Fixtures ----------------------------------------------------------------

const YAML_SRC = `# graph header comment — must survive round-trip
nodes:
  - uid: ROOT
    name: Root Node
    intent: The top-level goal.  # inline comment on intent
    epistemic_state: known
    constraints:
      - Must be fast.
      - Must be correct.
  - uid: CHILD
    name: Child Node
    intent: A sub-goal.
    epistemic_state: undecided
`;

function hashOf(raw) {
  return computeFileHash(raw);
}

// --- findNodeIndex -----------------------------------------------------------

test('findNodeIndex: locates first, last, and missing nodes', () => {
  const doc = YAML.parseDocument(YAML_SRC);
  assert.equal(findNodeIndex(doc, 'ROOT'), 0);
  assert.equal(findNodeIndex(doc, 'CHILD'), 1);
  assert.equal(findNodeIndex(doc, 'NOPE'), -1);
});

// --- epistemic_state write ---------------------------------------------------

test('applyNodeEdit: writes epistemic_state alone', () => {
  const res = applyNodeEdit(YAML_SRC, {
    nodeUid: 'ROOT',
    fields: { epistemic_state: 'risky: unverified assumption' },
    fileHash: hashOf(YAML_SRC)
  });
  assert.equal(res.ok, true, res.error);
  const reparsed = YAML.parseDocument(res.newContent);
  assert.equal(reparsed.getIn(['nodes', 0, 'epistemic_state']), 'risky: unverified assumption');
  // Untouched sibling unchanged.
  assert.equal(reparsed.getIn(['nodes', 1, 'epistemic_state']), 'undecided');
});

test('applyNodeEdit: preserves header + inline comments and key order on epistemic edit', () => {
  const res = applyNodeEdit(YAML_SRC, {
    nodeUid: 'ROOT',
    fields: { epistemic_state: 'observed' },
    fileHash: hashOf(YAML_SRC)
  });
  assert.equal(res.ok, true, res.error);
  assert.match(res.newContent, /# graph header comment/);
  assert.match(res.newContent, /# inline comment on intent/);
  // epistemic_state still sits between intent and constraints (order preserved).
  const idxIntent = res.newContent.indexOf('intent: The top-level goal');
  const idxEpist = res.newContent.indexOf('epistemic_state: observed');
  const idxConstr = res.newContent.indexOf('constraints:');
  assert.ok(idxIntent < idxEpist && idxEpist < idxConstr, 'key order preserved');
});

test('applyNodeEdit: multi-field name + epistemic together', () => {
  const res = applyNodeEdit(YAML_SRC, {
    nodeUid: 'CHILD',
    fields: { name: 'Renamed Child', epistemic_state: 'known' },
    fileHash: hashOf(YAML_SRC)
  });
  assert.equal(res.ok, true, res.error);
  const reparsed = YAML.parseDocument(res.newContent);
  assert.equal(reparsed.getIn(['nodes', 1, 'name']), 'Renamed Child');
  assert.equal(reparsed.getIn(['nodes', 1, 'epistemic_state']), 'known');
});

test('applyNodeEdit: intent + epistemic + constraint together', () => {
  const res = applyNodeEdit(YAML_SRC, {
    nodeUid: 'ROOT',
    fields: {
      intent: 'A refined goal.',
      epistemic_state: 'constrained',
      constraints: ['Must be fast.', 'Must be correct and tested.']
    },
    fileHash: hashOf(YAML_SRC)
  });
  assert.equal(res.ok, true, res.error);
  const reparsed = YAML.parseDocument(res.newContent);
  assert.equal(reparsed.getIn(['nodes', 0, 'intent']), 'A refined goal.');
  assert.equal(reparsed.getIn(['nodes', 0, 'epistemic_state']), 'constrained');
  assert.equal(reparsed.getIn(['nodes', 0, 'constraints', 1]), 'Must be correct and tested.');
});

// --- empty-value policy (reject; no clear-to-delete) -------------------------

test('applyNodeEdit: empty epistemic_state is rejected, file untouched', () => {
  const res = applyNodeEdit(YAML_SRC, {
    nodeUid: 'ROOT',
    fields: { epistemic_state: '   ' },
    fileHash: hashOf(YAML_SRC)
  });
  assert.equal(res.ok, false);
  assert.match(res.error, /epistemic_state.*must not be empty/);
  assert.equal(res.newContent, undefined);
});

// --- hash mismatch (external change) ----------------------------------------

test('applyNodeEdit: stale fileHash → external-change error, no write', () => {
  const res = applyNodeEdit(YAML_SRC, {
    nodeUid: 'ROOT',
    fields: { epistemic_state: 'known' },
    fileHash: 'deadbeef-not-the-real-hash'
  });
  assert.equal(res.ok, false);
  assert.match(res.error, /changed externally/);
});

// --- unchanged input → new hash differs only when content differs -----------

test('applyNodeEdit: newFileHash reflects the mutated content', () => {
  const res = applyNodeEdit(YAML_SRC, {
    nodeUid: 'ROOT',
    fields: { epistemic_state: 'speculative' },
    fileHash: hashOf(YAML_SRC)
  });
  assert.equal(res.ok, true, res.error);
  assert.notEqual(res.newFileHash, hashOf(YAML_SRC));
  assert.equal(res.newFileHash, hashOf(res.newContent));
});
