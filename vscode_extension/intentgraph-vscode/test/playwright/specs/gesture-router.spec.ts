// GestureRouter spec.
//
// Three behaviours not covered by lod-toggle / persistence:
//   1. dbltap on a lean leaf → LOD promotes to 'full' AND edit mode is entered
//      (overlay card has fields with `.ig-editing` class, signalling
//      contenteditable=true).
//   2. dbltap on a full leaf → enters edit mode WITHOUT a redundant LOD flip.
//   3. While one node is in edit mode, a drag (grab/free with movement) on a
//      DIFFERENT node does NOT emit PersistPositionRequest (router suppresses
//      drag-persist globally while any node is editing).

import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

import { loadFixture } from '../fixtures';
import { installLoadHandler } from '../harness/installLoad';

const HARNESS_URL = '/test/playwright/harness/index.html';
const LEAF_A = 'DISCOVER.1';
const LEAF_B = 'DISCOVER.2';

interface CyNode {
  emit(event: string): void;
  data(key: string, value?: unknown): unknown;
  position(p?: { x: number; y: number }): { x: number; y: number };
}
interface CyLike {
  getElementById(id: string): CyNode;
}
interface BusMessage {
  method?: string;
  id?: string;
  params?: Record<string, unknown>;
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
      // editNode is awaited inside the dbltap → overlay path. Stub it so
      // commits don't hang.
      bus.handleRequest('intentgraph/editNode', () => ({
        ok: true,
        newFileHash: 'after-edit'
      }));
    };
    install();
  });
}

async function boot(page: Page): Promise<void> {
  const model = await loadFixture('test/fixtures/validator.ig.json');
  await installLoadHandler(page, { model });
  await installPersistAck(page);
  await page.goto(HARNESS_URL);
  await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });
}

test.describe('gesture router', () => {
  test('dbltap on lean leaf promotes to full and enters edit mode', async ({ page }) => {
    await boot(page);

    // Sanity: starts in lean, no overlay yet.
    await expect(page.locator(`.ig-full-overlay[data-uid="${LEAF_A}"]`)).toHaveCount(0);

    await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      cy.getElementById(uid).emit('dbltap');
    }, LEAF_A);

    // LOD now full.
    await expect
      .poll(() =>
        page.evaluate((uid) => {
          const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
          return cy.getElementById(uid).data('lod') as string | undefined;
        }, LEAF_A)
      )
      .toBe('full');

    // Overlay mounted.
    const overlay = page.locator(`.ig-full-overlay[data-uid="${LEAF_A}"]`);
    await expect(overlay).toHaveCount(1);

    // Edit mode entered: at least one editable field inside the overlay
    // gains the `.ig-editing` class (one frame after dbltap via
    // requestAnimationFrame). The card scopes the selector.
    await expect(overlay.locator('.ig-editing').first()).toBeAttached({ timeout: 3_000 });
  });

  test('dbltap on full leaf enters edit mode without redundant LOD flip', async ({ page }) => {
    await boot(page);

    // Promote to full first via single tap.
    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy.getElementById(uid).emit('tap');
    }, LEAF_A);
    await expect(page.locator(`.ig-full-overlay[data-uid="${LEAF_A}"]`)).toHaveCount(1);

    // Capture LOD before dbltap.
    const before = await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      return cy.getElementById(uid).data('lod') as string;
    }, LEAF_A);
    expect(before).toBe('full');

    // Dbltap.
    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy.getElementById(uid).emit('dbltap');
    }, LEAF_A);

    // LOD unchanged.
    const after = await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      return cy.getElementById(uid).data('lod') as string;
    }, LEAF_A);
    expect(after).toBe('full');

    // Edit mode entered.
    const overlay = page.locator(`.ig-full-overlay[data-uid="${LEAF_A}"]`);
    await expect(overlay.locator('.ig-editing').first()).toBeAttached({ timeout: 3_000 });
  });

  test('editing epistemic_state sends it in the editNode payload', async ({ page }) => {
    await boot(page);

    // Enter edit mode on a leaf that carries an epistemic_state (DISCOVER.1 → "known").
    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy.getElementById(uid).emit('dbltap');
    }, LEAF_A);

    const overlay = page.locator(`.ig-full-overlay[data-uid="${LEAF_A}"]`);
    // The epistemic field is now editable (Phase 1.5): it gains .ig-editing on entry.
    const epistField = overlay.locator('.ig-fn-epistemic');
    await expect(epistField).toHaveClass(/ig-editing/, { timeout: 3_000 });

    // Type a new value into the contenteditable epistemic field, then commit by
    // clicking outside the card (document-level pointerdown → commitNodeEdit).
    await epistField.evaluate((el) => {
      el.textContent = 'risky: needs review';
    });
    await page.evaluate(() => {
      document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    });

    // The commit must reach the host as an editNode request carrying the new
    // epistemic_state in fields.
    const editMsg = await page.evaluate(async () => {
      const bus = (window as unknown as {
        __igTestBus: { outbound: BusMessage[]; waitFor: (p: (m: BusMessage) => boolean, t: number) => Promise<BusMessage> };
      }).__igTestBus;
      const m = await bus.waitFor((msg) => msg.method === 'intentgraph/editNode', 3000);
      return m?.params ?? null;
    });

    expect(editMsg).not.toBeNull();
    const fields = (editMsg as { fields?: Record<string, unknown> }).fields;
    expect(fields?.epistemic_state).toBe('risky: needs review');
  });

  test('drag on another node is suppressed while one node is editing', async ({ page }) => {
    await boot(page);

    // Enter edit on LEAF_A.
    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy.getElementById(uid).emit('dbltap');
    }, LEAF_A);
    await expect(
      page.locator(`.ig-full-overlay[data-uid="${LEAF_A}"] .ig-editing`).first()
    ).toBeAttached({ timeout: 3_000 });

    // Clear any prior outbound (the dbltap path may emit unrelated messages).
    await page.evaluate(() => {
      (window as unknown as { __igTestBus: { outbound: BusMessage[] } }).__igTestBus.outbound.length = 0;
    });

    // Drag LEAF_B with real movement.
    await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      const node = cy.getElementById(uid);
      node.emit('grab');
      const p = node.position();
      node.position({ x: p.x + 10, y: p.y + 10 });
      node.emit('free');
    }, LEAF_B);

    // No persist for LEAF_B (edit-mode suppression at the router).
    await page.waitForTimeout(200);
    const persistCount = await page.evaluate(() => {
      const bus = (window as unknown as { __igTestBus: { outbound: BusMessage[] } }).__igTestBus;
      return bus.outbound.filter((m) => m.method === 'intentgraph/persistPosition').length;
    });
    expect(persistCount).toBe(0);
  });
});
