// LOD toggle spec.
//
// Tap on a leaf node → LOD promotes from 'lean' to 'full'; a corresponding
// `.ig-full-overlay` DOM element appears with data-uid matching the node.
// A second tap → LOD demotes back to 'lean'; the overlay element is removed.
//
// We trigger the gesture via cy.$('#uid').emit('tap', ...) rather than a real
// Playwright click. Reason: cytoscape `tap` events fire on canvas hit-tests
// against rendered positions, which depend on ELK layout, viewport zoom, and
// HiDPI scaling — fragile across CI machines. Emitting the event directly
// exercises the exact same gestureRouter.onTap path with deterministic input.
//
// To allow this, src/webview/main.ts exposes window.__igTestCy = cy whenever
// __igTestBus is present (test-only hook, no-op in prod).

import { test, expect } from '@playwright/test';

import { loadFixture } from '../fixtures';
import { installLoadHandler } from '../harness/installLoad';

// Structural type covering the cytoscape methods we actually call from tests.
// Avoids dragging the full @types/cytoscape surface (and its
// dependency-of-the-extension build path) into the Playwright TS loader.
interface CyNode {
  emit(event: string): void;
  data(key: string): unknown;
  nonempty(): boolean;
  isParent(): boolean;
  hasClass(c: string): boolean;
}
interface CyLike {
  getElementById(id: string): CyNode;
}

const HARNESS_URL = '/test/playwright/harness/index.html';
const LEAF_UID = 'DISCOVER.1';

test.describe('LOD toggle', () => {
  test('tap on leaf promotes lean → full and mounts overlay', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Sanity: cy is exposed via test hook, and the leaf exists in lean LOD.
    const initialLod = await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy?: CyLike }).__igTestCy;
      if (!cy) return '__no_cy__';
      const node = cy.getElementById(uid);
      if (!node.nonempty()) return '__missing__';
      return (node.data('lod') as string | undefined) ?? 'lean';
    }, LEAF_UID);
    expect(initialLod).toBe('lean');

    // No overlay for this node yet.
    await expect(page.locator(`.ig-full-overlay[data-uid="${LEAF_UID}"]`)).toHaveCount(0);

    // Emit a synthetic tap. The gestureRouter onTap handler reads evt.target
    // (the cy node) and evt.originalEvent?.target.classList.
    await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy?: CyLike }).__igTestCy;
      if (!cy) throw new Error('__igTestCy not exposed');
      const node = cy.getElementById(uid);
      node.emit('tap');
    }, LEAF_UID);

    // After tap: lod=full, overlay mounted.
    await expect
      .poll(() =>
        page.evaluate((uid) => {
          const cy = (window as unknown as { __igTestCy?: CyLike }).__igTestCy;
          return cy?.getElementById(uid).data('lod') as string | undefined;
        }, LEAF_UID)
      )
      .toBe('full');
    await expect(page.locator(`.ig-full-overlay[data-uid="${LEAF_UID}"]`)).toHaveCount(1);
  });

  test('second tap demotes full → lean and removes overlay', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Promote.
    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy
        .getElementById(uid)
        .emit('tap');
    }, LEAF_UID);
    await expect(page.locator(`.ig-full-overlay[data-uid="${LEAF_UID}"]`)).toHaveCount(1);

    // Demote.
    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy
        .getElementById(uid)
        .emit('tap');
    }, LEAF_UID);

    await expect
      .poll(() =>
        page.evaluate((uid) => {
          const cy = (window as unknown as { __igTestCy?: CyLike }).__igTestCy;
          return cy?.getElementById(uid).data('lod') as string | undefined;
        }, LEAF_UID)
      )
      .toBe('lean');
    await expect(page.locator(`.ig-full-overlay[data-uid="${LEAF_UID}"]`)).toHaveCount(0);
  });

  test('tap on uncollapsed compound is ignored (no LOD change)', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    const COMPOUND_UID = 'DISCOVER';

    const before = await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      const node = cy.getElementById(uid);
      return {
        lod: (node.data('lod') as string | undefined) ?? 'lean',
        isParent: node.isParent(),
        isCollapsed: node.hasClass('cy-expand-collapse-collapsed-node')
      };
    }, COMPOUND_UID);
    expect(before.isParent).toBe(true);
    expect(before.isCollapsed).toBe(false);

    await page.evaluate((uid) => {
      (window as unknown as { __igTestCy: CyLike }).__igTestCy
        .getElementById(uid)
        .emit('tap');
    }, COMPOUND_UID);

    // Compound is suppressed by the gestureRouter; lod stays where it was and
    // no overlay is mounted (full-LOD overlay is leaf-only anyway).
    await expect(page.locator(`.ig-full-overlay[data-uid="${COMPOUND_UID}"]`)).toHaveCount(0);
    const after = await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      return (cy.getElementById(uid).data('lod') as string | undefined) ?? 'lean';
    }, COMPOUND_UID);
    expect(after).toBe(before.lod);
  });
});
