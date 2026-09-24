// Re-layout button spec.
//
// Clicking #lens-relayout-btn re-runs ELK on the current model, applies the
// new positions, and sends one PersistPositionRequest per moved leaf.
// Compounds are skipped (cytoscape auto-fits their bbox from children).
//
// We verify:
//   1. The button is present and clickable.
//   2. Clicking it produces at least one PersistPositionRequest (one per
//      leaf node).
//   3. Each payload uses the current activeLensName (null if none).
//   4. While a node is in edit mode, re-layout is suppressed (no persist).

import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

import { loadFixture } from '../fixtures';
import { installLoadHandler } from '../harness/installLoad';

const HARNESS_URL = '/test/playwright/harness/index.html';

interface BusMessage {
  method?: string;
  params?: { uid?: string; position?: { x: number; y: number }; activeLensName?: string | null };
}

interface CyNode {
  emit(event: string): void;
  isParent(): boolean;
  nonempty(): boolean;
}
interface CyLike {
  getElementById(id: string): CyNode;
  nodes(selector?: string): { length: number; forEach: (cb: (n: CyNode & { id(): string }) => void) => void };
}

async function installPersistAck(page: Page): Promise<void> {
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
        lensName: 'test',
        autoCreated: false
      }));
      bus.handleRequest('intentgraph/editNode', () => ({
        ok: true,
        newFileHash: 'after-edit'
      }));
    };
    install();
  });
}

test.describe('re-layout button', () => {
  test('button exists and is enabled after load', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });
    await installPersistAck(page);

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    const btn = page.locator('#lens-relayout-btn');
    await expect(btn).toBeAttached();
    await expect(btn).toBeEnabled();
    await expect(btn).toHaveAttribute('title', 'Re-run layout');
  });

  test('clicking emits PersistPositionRequest per leaf with activeLensName=null', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });
    await installPersistAck(page);

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Clear outbound log so we isolate the re-layout messages.
    await page.evaluate(() => {
      (window as unknown as { __igTestBus: { outbound: BusMessage[] } }).__igTestBus.outbound.length = 0;
    });

    await page.locator('#lens-relayout-btn').click();

    // Wait for at least one persist to arrive.
    await page.evaluate(() => {
      const bus = (window as unknown as {
        __igTestBus: { waitFor: (p: (m: BusMessage) => boolean, ms: number) => Promise<BusMessage> };
      }).__igTestBus;
      return bus.waitFor((m: BusMessage) => m.method === 'intentgraph/persistPosition', 5000);
    });

    // Collect every persist; assert at least one leaf was moved and the lens
    // name matches the un-set state (null).
    const persists = await page.evaluate(() => {
      const bus = (window as unknown as { __igTestBus: { outbound: BusMessage[] } }).__igTestBus;
      return bus.outbound.filter((m) => m.method === 'intentgraph/persistPosition');
    });
    expect(persists.length).toBeGreaterThan(0);
    for (const m of persists) {
      expect(m.params?.activeLensName).toBeNull();
      expect(typeof m.params?.uid).toBe('string');
      expect(typeof m.params?.position?.x).toBe('number');
      expect(typeof m.params?.position?.y).toBe('number');
    }

    // No persist for a known compound UID (compounds are skipped).
    const compoundPersists = persists.filter((m) => m.params?.uid === 'DISCOVER');
    expect(compoundPersists.length).toBe(0);
  });

  test('re-layout suppressed while a node is in edit mode', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });
    await installPersistAck(page);

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Enter edit mode on a leaf.
    await page.evaluate(() => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy.getElementById('DISCOVER.1').emit('dbltap');
    });
    await expect(
      page.locator('.ig-full-overlay[data-uid="DISCOVER.1"] .ig-editing').first()
    ).toBeAttached({ timeout: 3_000 });

    // Clear outbound so we isolate the re-layout click.
    await page.evaluate(() => {
      (window as unknown as { __igTestBus: { outbound: BusMessage[] } }).__igTestBus.outbound.length = 0;
    });

    await page.locator('#lens-relayout-btn').click();

    // Wait briefly, then assert no persist fired.
    await page.waitForTimeout(300);
    const persistCount = await page.evaluate(() => {
      const bus = (window as unknown as { __igTestBus: { outbound: BusMessage[] } }).__igTestBus;
      return bus.outbound.filter((m) => m.method === 'intentgraph/persistPosition').length;
    });
    expect(persistCount).toBe(0);

    // The transient status should mention the suppression.
    await expect(page.locator('#status')).toContainText('Re-layout suppressed', { timeout: 2000 });
  });
});
