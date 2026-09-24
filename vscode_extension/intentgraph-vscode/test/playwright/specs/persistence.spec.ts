// Persistence spec.
//
// On drag (grab→free with movement > 1px), the gestureRouter sends a
// PersistPositionRequest (method 'intentgraph/persistPosition') to the host
// with { uid, position, activeLensName }. The host writes the position to
// the active lens; on next reload, ApplyLensNotification restores it.
//
// This spec verifies the webview side of the contract:
//   1. A real grab+free with movement triggers exactly one PersistPositionRequest.
//   2. The payload's uid matches the dragged node.
//   3. The payload's position equals the node's new cytoscape position.
//   4. A click without movement (grab+free with <1px delta) sends nothing.
//
// We do NOT verify the host's lens-write logic — that's a separate concern
// covered by host-side integration tests.

import { test, expect } from '@playwright/test';

import { loadFixture } from '../fixtures';
import { installLoadHandler } from '../harness/installLoad';

const HARNESS_URL = '/test/playwright/harness/index.html';
const LEAF_UID = 'DISCOVER.1';

interface CyNode {
  emit(event: string): void;
  position(p?: { x: number; y: number }): { x: number; y: number };
  parent(): { nonempty(): boolean; boundingBox(): { x1: number; y1: number; x2: number; y2: number } };
}
interface CyLike {
  getElementById(id: string): CyNode;
}

interface BusMessage {
  method?: string;
  id?: string;
  params?: { uid?: string; position?: { x: number; y: number }; activeLensName?: string | null };
}

// Install a handler that ACKs persistPosition so the webview doesn't show an
// error banner. Without this, the request would time out and the message
// would still be captured, but the trace would include an unrelated banner.
async function installPersistAck(page: import('@playwright/test').Page): Promise<void> {
  await page.addInitScript(() => {
    const install = () => {
      const bus = (window as unknown as {
        __igTestBus?: { handleRequest: (m: string, h: () => unknown) => void };
      }).__igTestBus;
      if (!bus) {
        setTimeout(install, 0);
        return;
      }
      bus.handleRequest('intentgraph/persistPosition', () => ({
        ok: true,
        lensName: 'test-lens',
        autoCreated: false
      }));
    };
    install();
  });
}

test.describe('drag persistence', () => {
  test('drag emits exactly one PersistPositionRequest with new position', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });
    await installPersistAck(page);

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Move the node and dispatch grab + free against the cy event system.
    // Keep the move INSIDE the parent compound bbox so the snap-back path
    // (which suppresses persist) doesn't fire.
    const DX = 5;
    const DY = 5;
    const { newX, newY } = await page.evaluate(
      ({ uid, dx, dy }) => {
        const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
        const node = cy.getElementById(uid);

        // Capture starting position, emit grab (router stores it).
        node.emit('grab');

        // Move within the parent compound's interior bounds. Use a small delta
        // so we stay well inside the parent's bbox even after ELK layout.
        const p0 = node.position();
        node.position({ x: p0.x + dx, y: p0.y + dy });
        node.emit('free');

        const p1 = node.position();
        return { newX: p1.x, newY: p1.y };
      },
      { uid: LEAF_UID, dx: DX, dy: DY }
    );

    // Wait for the outbound message to appear on the bus.
    const persistMsg = await page.evaluate(async () => {
      const bus = (window as unknown as {
        __igTestBus: { waitFor: (p: (m: BusMessage) => boolean, ms: number) => Promise<BusMessage> };
      }).__igTestBus;
      return bus.waitFor((m: BusMessage) => m.method === 'intentgraph/persistPosition', 5000);
    });

    expect(persistMsg.params?.uid).toBe(LEAF_UID);
    expect(persistMsg.params?.position?.x).toBeCloseTo(newX, 1);
    expect(persistMsg.params?.position?.y).toBeCloseTo(newY, 1);

    // Exactly one persist for this uid (no spurious duplicates).
    const persistCount = await page.evaluate(() => {
      const bus = (window as unknown as {
        __igTestBus: { outbound: BusMessage[] };
      }).__igTestBus;
      return bus.outbound.filter((m) => m.method === 'intentgraph/persistPosition').length;
    });
    expect(persistCount).toBe(1);
  });

  test('click without movement does NOT emit a persist request', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });
    await installPersistAck(page);

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Grab and free without moving. wasActualDrag should return false
    // (sub-pixel jitter threshold = 1px, identical positions → false).
    await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      const node = cy.getElementById(uid);
      node.emit('grab');
      node.emit('free');
    }, LEAF_UID);

    // Give the bus a tick to drain; then assert no persist was sent.
    await page.waitForTimeout(200);
    const persistCount = await page.evaluate(() => {
      const bus = (window as unknown as { __igTestBus: { outbound: BusMessage[] } }).__igTestBus;
      return bus.outbound.filter((m) => m.method === 'intentgraph/persistPosition').length;
    });
    expect(persistCount).toBe(0);
  });
});
