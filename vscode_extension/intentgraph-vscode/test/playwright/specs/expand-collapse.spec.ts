// Expand/collapse spec.
//
// CueLayer mounts one `<button data-ig-compound-cue="UID">` per compound node.
// Clicking it calls the cytoscape-expand-collapse API:
//   - if expandable (collapsed) → expand
//   - if collapsible (expanded with children) → collapse
//
// On collapse, the compound node gains class `cy-expand-collapse-collapsed-node`
// and its children are stripped from the cy graph. On expand, the class is
// removed and children reappear.
//
// We assert via cytoscape state, not pixel positions, for the same reason as
// lod-toggle: DOM hit-testing on a synthetic canvas is fragile.

import { test, expect } from '@playwright/test';

import { loadFixture } from '../fixtures';
import { installLoadHandler } from '../harness/installLoad';

const HARNESS_URL = '/test/playwright/harness/index.html';
const COMPOUND_UID = 'DISCOVER';

interface CyNode {
  nonempty(): boolean;
  hasClass(c: string): boolean;
  children(): { length: number };
  isParent(): boolean;
}
interface CyLike {
  getElementById(id: string): CyNode;
  nodes(): { length: number };
}

test.describe('expand-collapse', () => {
  test('cue button exists for every compound', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // validator.ig.json has compounds: ROOT, DISCOVER, PARSE, VALIDATE, REPORT.
    // ROOT may be filtered out in some configurations; assert at least the
    // four interior compounds have a cue button.
    for (const uid of ['DISCOVER', 'PARSE', 'VALIDATE', 'REPORT']) {
      await expect(page.locator(`button[data-ig-compound-cue="${uid}"]`)).toHaveCount(1);
    }
  });

  test('clicking cue collapses the compound', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Before: DISCOVER is expanded — it's a parent with children, not collapsed.
    const before = await page.evaluate((uid) => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      const node = cy.getElementById(uid);
      return {
        isParent: node.isParent(),
        isCollapsed: node.hasClass('cy-expand-collapse-collapsed-node'),
        nodeCount: cy.nodes().length
      };
    }, COMPOUND_UID);
    expect(before.isParent).toBe(true);
    expect(before.isCollapsed).toBe(false);

    // Click the cue. The cue is positioned absolutely via tickOne but is a
    // real DOM button — Playwright dispatches a click event that the addEventListener
    // in CueLayer.createCueButton receives. We use dispatchEvent rather than
    // .click() because the button may be outside the viewport at our fixture's
    // ELK layout position (the harness viewport is 1280x800; ELK puts nodes
    // at arbitrary coords).
    await page.evaluate((uid) => {
      const btn = document.querySelector(
        `button[data-ig-compound-cue="${uid}"]`
      ) as HTMLButtonElement | null;
      if (!btn) throw new Error(`cue button for ${uid} not found`);
      btn.click();
    }, COMPOUND_UID);

    // After: collapsed. The plugin removes children from the live graph and
    // stamps the class on the compound node.
    await expect
      .poll(() =>
        page.evaluate((uid) => {
          const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
          return cy.getElementById(uid).hasClass('cy-expand-collapse-collapsed-node');
        }, COMPOUND_UID)
      )
      .toBe(true);

    const after = await page.evaluate(() => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      return { nodeCount: cy.nodes().length };
    });
    // Children of DISCOVER (DISCOVER.1, .2, .3) should be stripped.
    expect(after.nodeCount).toBeLessThan(before.nodeCount);
  });

  test('second click expands the compound', async ({ page }) => {
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // Collapse, then expand.
    await page.evaluate((uid) => {
      (document.querySelector(`button[data-ig-compound-cue="${uid}"]`) as HTMLButtonElement).click();
    }, COMPOUND_UID);

    await expect
      .poll(() =>
        page.evaluate((uid) => {
          const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
          return cy.getElementById(uid).hasClass('cy-expand-collapse-collapsed-node');
        }, COMPOUND_UID)
      )
      .toBe(true);

    await page.evaluate((uid) => {
      (document.querySelector(`button[data-ig-compound-cue="${uid}"]`) as HTMLButtonElement).click();
    }, COMPOUND_UID);

    await expect
      .poll(() =>
        page.evaluate((uid) => {
          const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
          return cy.getElementById(uid).hasClass('cy-expand-collapse-collapsed-node');
        }, COMPOUND_UID)
      )
      .toBe(false);
  });
});
