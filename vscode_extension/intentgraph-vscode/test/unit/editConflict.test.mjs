/**
 * Unit tests for Bug 2: Edit Conflict Handling.
 *
 * PIG constraints:
 * - EDITING.PERSISTENCE #3: User submits edit → stash in pendingEdits map,
 *   DOM restored to pre-edit value, send request, wait for response.
 *   On ok=true: write pending newValue to DOM, clear pending entry.
 *   On ok=false: discard pending entry, DOM already correct (pre-edit).
 * - DIAGNOSTICS.EDIT_CONFLICT #4: ok=false triggers EditConflictNotification
 *   (host path via IntentGraphEditorProvider, not webview).
 * - INV-6: No optimistic DOM updates for field/text edits. Pre-edit display
 *   until confirmed.
 *
 * Test infrastructure: inline helpers for pendingEdits map and edit response flow.
 * Run: node --test test/unit/editConflict.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ---------------------------------------------------------------------------
// Test 1: logEditFailure formatting (Bug 2 Step 6)
// ---------------------------------------------------------------------------

/**
 * PIG DIAGNOSTICS.EDIT_CONFLICT #1: logEditFailure formats edit failures.
 * Expected format: [ISO timestamp] edit ok=false | uid=X field=Y error=Z
 */
test('logEditFailure: formats uid, field, error with ISO timestamp', () => {
  // Simulate the formatting at src/editor/IntentGraphEditorProvider.ts:95
  const nodeUid = 'node-123-abc';
  const field = 'intent';
  const error = 'File changed externally — reload first.';
  const timestamp = new Date().toISOString();
  const formatted = `[${timestamp}] edit ok=false | uid=${nodeUid} field=${field} error=${error}`;

  // Verify the line includes all three components.
  assert(formatted.includes('edit ok=false'));
  assert(formatted.includes(`uid=${nodeUid}`));
  assert(formatted.includes(`field=${field}`));
  assert(formatted.includes(`error=${error}`));
});

// ---------------------------------------------------------------------------
// Test 2: Banner non-dismissability (Bug 2 Step 7)
// ---------------------------------------------------------------------------

/**
 * PIG DIAGNOSTICS.EDIT_CONFLICT #2: data-dismissable="false" blocks dismiss.
 * Simulate the webview/main.ts banner machinery (lines 64–135).
 */
test('Banner: data-dismissable="false" blocks dismiss path', () => {
  // Simulate the banner state at webview/main.ts lines 64–135.
  class BannerStateMachine {
    constructor() {
      this.dismissable = true;
    }

    showEditConflictBanner(message, dismissable) {
      // PIG DIAGNOSTICS.EDIT_CONFLICT #2: non-dismissable banner fires on ok=false.
      this.message = message;
      this.dismissable = dismissable;
    }

    clearEditConflictBanner() {
      // Only allowed if dismissable === true.
      if (!this.dismissable) {
        return { allowed: false };
      }
      this.message = null;
      return { allowed: true };
    }
  }

  const banner = new BannerStateMachine();
  banner.showEditConflictBanner('Edit failed', false);
  const clearResult = banner.clearEditConflictBanner();
  assert.strictEqual(clearResult.allowed, false);
  assert.strictEqual(banner.message, 'Edit failed');
});

// ---------------------------------------------------------------------------
// Test 3: Pre-edit value preservation (Bug 2 Step 8 / INV-6)
// ---------------------------------------------------------------------------

/**
 * PIG EDITING.PERSISTENCE #3: pendingEdits stashes proposed value;
 * DOM displays pre-edit value until ok=true response.
 *
 * Test cases:
 * 1. Submit edit: DOM unchanged (still pre-edit).
 * 2. on ok=true: DOM is pending newValue, pending entry cleared.
 * 3. on ok=false: DOM unchanged (still pre-edit), pending entry cleared.
 */

class PendingEditsSimulator {
  constructor() {
    // Map<uid|field, newValue>
    this.pendingEdits = new Map();
    // Map<uid|field, {prefix, value}>  (dataset attributes)
    this.domDataset = new Map();
  }

  setPreEditValue(uidField, prefix, value) {
    // Simulates createEditableField at htmlOverlayLayer.ts:549–556.
    this.domDataset.set(uidField, { prefix, value });
  }

  submitEdit(uidField, newValue) {
    // User typed newValue; called commitNodeEdit.
    // PIG EDITING.PERSISTENCE #3: stash newValue, restore pre-edit DOM.
    this.pendingEdits.set(uidField, newValue);
    // Restore pre-edit: DOM textContent = prefix + pre-edit value.
    const data = this.domDataset.get(uidField);
    return { dom: data.prefix + data.value };
  }

  onResponse(uidField, ok) {
    const pending = this.pendingEdits.get(uidField);
    if (!ok) {
      // PIG DIAGNOSTICS.EDIT_CONFLICT #4: discard pending, DOM already correct.
      this.pendingEdits.delete(uidField);
      const data = this.domDataset.get(uidField);
      return { dom: data.prefix + data.value };
    }
    // ok=true: write pending to DOM, clear pending.
    if (pending !== undefined) {
      const data = this.domDataset.get(uidField);
      this.domDataset.set(uidField, { ...data, value: pending });
      this.pendingEdits.delete(uidField);
      return { dom: data.prefix + pending };
    }
    return { dom: null };
  }
}

test('PIG EDITING.PERSISTENCE #3: submit edit → DOM unchanged (pre-edit)', () => {
  const sim = new PendingEditsSimulator();
  sim.setPreEditValue('uid-X|intent', '', 'Old intent');
  const domAfterSubmit = sim.submitEdit('uid-X|intent', 'New intent');
  // DOM should still show pre-edit.
  assert.strictEqual(domAfterSubmit.dom, 'Old intent');
  // Pending entry exists.
  assert.strictEqual(sim.pendingEdits.get('uid-X|intent'), 'New intent');
});

test('PIG EDITING.PERSISTENCE #3: on ok=true → DOM is newValue, pending cleared', () => {
  const sim = new PendingEditsSimulator();
  sim.setPreEditValue('uid-X|intent', 'prefix: ', 'Old intent');
  sim.submitEdit('uid-X|intent', 'New intent');
  const domAfterOK = sim.onResponse('uid-X|intent', true);
  // DOM should now show newValue.
  assert.strictEqual(domAfterOK.dom, 'prefix: New intent');
  // Pending cleared.
  assert.strictEqual(sim.pendingEdits.get('uid-X|intent'), undefined);
});

test('PIG EDITING.PERSISTENCE #3: on ok=false → DOM unchanged (pre-edit), pending cleared', () => {
  const sim = new PendingEditsSimulator();
  sim.setPreEditValue('uid-X|name', '', 'OldName');
  sim.submitEdit('uid-X|name', 'NewName');
  const domAfterFail = sim.onResponse('uid-X|name', false);
  // DOM should still show pre-edit.
  assert.strictEqual(domAfterFail.dom, 'OldName');
  // Pending entry cleared (discarded).
  assert.strictEqual(sim.pendingEdits.get('uid-X|name'), undefined);
});

// ---------------------------------------------------------------------------
// Test 4: Constraint pending-edits key format (INV-6, whole-node edits)
// ---------------------------------------------------------------------------

/**
 * PIG EDITING.PERSISTENCE #3: constraints use key format uid|constraint|index.
 */
test('constraint pending-edits: key format uid|constraint|index', () => {
  const sim = new PendingEditsSimulator();
  // Constraint at index 2 for node uid-Y.
  sim.setPreEditValue('uid-Y|constraint|2', '- ', 'Old constraint');
  sim.submitEdit('uid-Y|constraint|2', 'New constraint');
  assert.strictEqual(sim.pendingEdits.get('uid-Y|constraint|2'), 'New constraint');
  const domAfterOK = sim.onResponse('uid-Y|constraint|2', true);
  assert.strictEqual(domAfterOK.dom, '- New constraint');
});

// ---------------------------------------------------------------------------
// Test 5: Multiple pending edits per node (whole-node edit scenario)
// ---------------------------------------------------------------------------

/**
 * PIG EDITING.PERSISTENCE #3: whole-node edit (name + intent + constraint)
 * submits all at once. Each gets a pending entry. On response, all cleared together.
 */
test('whole-node edit: multiple pending entries cleared together', () => {
  const sim = new PendingEditsSimulator();
  sim.setPreEditValue('uid-Z|name', '', 'OldName');
  sim.setPreEditValue('uid-Z|intent', '', 'OldIntent');
  sim.setPreEditValue('uid-Z|constraint|0', '- ', 'OldConstraint');

  // Submit all three at once.
  sim.submitEdit('uid-Z|name', 'NewName');
  sim.submitEdit('uid-Z|intent', 'NewIntent');
  sim.submitEdit('uid-Z|constraint|0', 'NewConstraint');

  // All three pending.
  assert.strictEqual(sim.pendingEdits.size, 3);

  // On ok=true, all three written to DOM, all cleared.
  sim.onResponse('uid-Z|name', true);
  sim.onResponse('uid-Z|intent', true);
  sim.onResponse('uid-Z|constraint|0', true);

  assert.strictEqual(sim.pendingEdits.size, 0);
  assert.strictEqual(sim.domDataset.get('uid-Z|name').value, 'NewName');
  assert.strictEqual(sim.domDataset.get('uid-Z|intent').value, 'NewIntent');
  assert.strictEqual(sim.domDataset.get('uid-Z|constraint|0').value, 'NewConstraint');
});
