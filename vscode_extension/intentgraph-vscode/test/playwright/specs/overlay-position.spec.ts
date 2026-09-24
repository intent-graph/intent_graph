// Overlay position spec.
//
// The HTML overlay layer positions a `.ig-full-overlay` card so its top-left
// matches the cytoscape node's renderedBoundingBox.x1 / y1 on every render
// frame (src/webview/overlay/htmlOverlayLayer.ts tickOne).
//
// This spec exercises the "overlay tracks node" invariant — a previously
// catalogued class of regression:
//   1. Promote a leaf to full LOD → overlay mounts.
//   2. Snapshot overlay rect and node rect.
//   3. Move the node by Δ via cy.position(...).
//   4. Snapshot again → overlay rect should have shifted by the same Δ
//      (or, more precisely, overlay.left/top still equal node rect.x1/y1).

import { test, expect } from '@playwright/test';

import { loadFixture } from '../fixtures';
import { installLoadHandler } from '../harness/installLoad';

const HARNESS_URL = '/test/playwright/harness/index.html';
const LEAF_UID = 'DISCOVER.1';

interface CyNode {
  emit(event: string): void;
  position(p?: { x: number; y: number }): { x: number; y: number };
  renderedBoundingBox(opts?: unknown): { x1: number; y1: number; x2: number; y2: number; w: number; h: number };
  data(key: string): unknown;
}
interface CyLike {
  getElementById(id: string): CyNode;
}

test.describe('overlay position', () => {
  test('overlay tracks cytoscape rendered bbox on initial mount', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Promote to full.
    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy.getElementById(uid).emit('tap');
    }, LEAF_UID);

    const overlay = page.locator(`.ig-full-overlay[data-uid="${LEAF_UID}"]`);
    await expect(overlay).toHaveCount(1);

    // Compare the overlay's CSS left/top against the node's renderedBoundingBox.
    const { overlayLeft, overlayTop, nodeX1, nodeY1 } = await page.evaluate((uid) => {
      const card = document.querySelector(
        `.ig-full-overlay[data-uid="${uid}"]`
      ) as HTMLElement;
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      const rect = cy.getElementById(uid).renderedBoundingBox({});
      return {
        overlayLeft: parseFloat(card.style.left),
        overlayTop: parseFloat(card.style.top),
        nodeX1: rect.x1,
        nodeY1: rect.y1
      };
    }, LEAF_UID);

    // Overlay.left and node.x1 must agree to sub-pixel precision (tickOne
    // writes them in the same render frame from the same rect).
    expect(Math.abs(overlayLeft - nodeX1)).toBeLessThan(0.5);
    expect(Math.abs(overlayTop - nodeY1)).toBeLessThan(0.5);
  });

  test('overlay follows node when node is moved', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Promote.
    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy.getElementById(uid).emit('tap');
    }, LEAF_UID);
    await expect(page.locator(`.ig-full-overlay[data-uid="${LEAF_UID}"]`)).toHaveCount(1);

    // Snapshot before move.
    const before = await page.evaluate((uid) => {
      const card = document.querySelector(`.ig-full-overlay[data-uid="${uid}"]`) as HTMLElement;
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      const node = cy.getElementById(uid);
      return {
        overlayLeft: parseFloat(card.style.left),
        overlayTop: parseFloat(card.style.top),
        nodePos: node.position()
      };
    }, LEAF_UID);

    // Move the node by a known delta.
    const DX = 200;
    const DY = 150;
    await page.evaluate(
      ({ uid, dx, dy }) => {
        const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
        const node = cy.getElementById(uid);
        const p = node.position();
        node.position({ x: p.x + dx, y: p.y + dy });
      },
      { uid: LEAF_UID, dx: DX, dy: DY }
    );

    // tickOne fires on the cy 'render' event which cy.position() triggers
    // synchronously. Poll to be safe.
    await expect
      .poll(() =>
        page.evaluate((uid) => {
          const card = document.querySelector(
            `.ig-full-overlay[data-uid="${uid}"]`
          ) as HTMLElement;
          return parseFloat(card.style.left);
        }, LEAF_UID)
      )
      .not.toBe(before.overlayLeft);

    const after = await page.evaluate((uid) => {
      const card = document.querySelector(`.ig-full-overlay[data-uid="${uid}"]`) as HTMLElement;
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      const rect = cy.getElementById(uid).renderedBoundingBox({});
      return {
        overlayLeft: parseFloat(card.style.left),
        overlayTop: parseFloat(card.style.top),
        nodeX1: rect.x1,
        nodeY1: rect.y1
      };
    }, LEAF_UID);

    // After move: overlay still locked to node rect (the invariant).
    expect(Math.abs(after.overlayLeft - after.nodeX1)).toBeLessThan(0.5);
    expect(Math.abs(after.overlayTop - after.nodeY1)).toBeLessThan(0.5);

    // Sanity: the delta is roughly DX / DY (same Δ in model coords; rendered
    // coords differ only by zoom, which is 1.0 in the harness viewport by
    // default unless cy.fit() shrunk it. Be generous with tolerance.)
    const deltaLeft = after.overlayLeft - before.overlayLeft;
    const deltaTop = after.overlayTop - before.overlayTop;
    expect(deltaLeft).toBeGreaterThan(0);
    expect(deltaTop).toBeGreaterThan(0);
  });
});
