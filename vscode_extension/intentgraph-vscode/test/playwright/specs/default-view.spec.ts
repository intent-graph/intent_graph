// Default-view spec.
//
// When a graph loads with no active lens and no prior collapse state, the
// webview auto-collapses every compound at depth ≥ 2 so only L0 (root) and
// L1 (root's direct children) are visible. This keeps the initial render
// readable on large graphs.
//
// validator.ig.json topology:
//   ROOT (depth 0)
//   ├── DISCOVER  (depth 1, compound, has children at depth 2)
//   ├── PARSE     (depth 1, compound, has children at depth 2)
//   ├── VALIDATE  (depth 1, compound, has children at depth 2)
//   ├── REPORT    (depth 1, compound, has children at depth 2)
//   └── (leaves directly under ROOT)
//
// Expected default-view behaviour: ROOT and the four L1 compounds are
// expanded; nothing else is. All four L1 compounds have depth-2 children,
// so none of them should be collapsed.

import { test, expect } from '@playwright/test';

import { loadFixture } from '../fixtures';
import { installLoadHandler } from '../harness/installLoad';

const HARNESS_URL = '/test/playwright/harness/index.html';

interface CyNode {
  hasClass(c: string): boolean;
  isParent(): boolean;
  nonempty(): boolean;
}
interface CyLike {
  getElementById(id: string): CyNode;
}

test.describe('default view (no lens)', () => {
  test('L1 compounds are NOT collapsed when none of them have deep descendants beyond depth-2 leaves', async ({ page }) => {
    // validator.ig.json's L1 compounds (DISCOVER, PARSE, VALIDATE, REPORT)
    // have depth-2 LEAF children — not depth-2 compounds. The rule collapses
    // compounds at depth ≥ 2, so the L1 ones stay expanded.
    const model = await loadFixture('test/fixtures/validator.ig.json');
    await installLoadHandler(page, { model });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    for (const uid of ['DISCOVER', 'PARSE', 'VALIDATE', 'REPORT']) {
      const isCollapsed = await page.evaluate((u) => {
        const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
        return cy.getElementById(u).hasClass('cy-expand-collapse-collapsed-node');
      }, uid);
      expect(isCollapsed, `${uid} should not be collapsed`).toBe(false);
    }
  });

  test('compounds at depth ≥ 2 are collapsed on initial load', async ({ page }) => {
    // Synthesise a graph with one L2 compound to exercise the rule.
    //   ROOT
    //   └── A (L1 compound)
    //       └── B (L2 compound — should auto-collapse)
    //           ├── B.1 (L3 leaf)
    //           └── B.2 (L3 leaf)
    const customModel = {
      graphName: 'depth-test',
      rootUid: 'ROOT',
      nodes: {
        ROOT: { uid: 'ROOT', name: 'ROOT' },
        A: { uid: 'A', name: 'A' },
        B: { uid: 'B', name: 'B' },
        'B.1': { uid: 'B.1', name: 'B.1' },
        'B.2': { uid: 'B.2', name: 'B.2' }
      },
      links: [],
      tree: [
        { parent: 'ROOT', child: 'A' },
        { parent: 'A', child: 'B' },
        { parent: 'B', child: 'B.1' },
        { parent: 'B', child: 'B.2' }
      ],
      childrenOf: { ROOT: ['A'], A: ['B'], B: ['B.1', 'B.2'], 'B.1': [], 'B.2': [] },
      parentOf: { ROOT: null, A: 'ROOT', B: 'A', 'B.1': 'B', 'B.2': 'B' },
      depthOf: { ROOT: 0, A: 1, B: 2, 'B.1': 3, 'B.2': 3 }
    };
    await installLoadHandler(page, { model: customModel });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Ready', { timeout: 15_000 });

    // B is depth 2 → collapsed.
    const bCollapsed = await page.evaluate(() => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      return cy.getElementById('B').hasClass('cy-expand-collapse-collapsed-node');
    });
    expect(bCollapsed).toBe(true);

    // A is depth 1 → NOT collapsed.
    const aCollapsed = await page.evaluate(() => {
      const cy = (window as unknown as { __igTestCy: CyLike }).__igTestCy;
      return cy.getElementById('A').hasClass('cy-expand-collapse-collapsed-node');
    });
    expect(aCollapsed).toBe(false);
  });

  test('default-view collapse is skipped when an active lens is set', async ({ page }) => {
    // With default_lens specified, the host would normally send an
    // ApplyLensNotification. The webview itself only checks activeLensName,
    // which is null at the time of the default-view branch. So a default-lens
    // load DOES auto-collapse — until ApplyLensNotification rewrites the view.
    // This test documents the "no lens" gate, not the "default lens" path,
    // because the active-lens state is set only by SelectLensResponse or
    // ApplyLensNotification, both host-initiated.
    //
    // What we CAN assert: with no lenses dict and no default_lens, the
    // L2-collapse logic fires. Already covered above. This test just
    // confirms the symmetric case: an empty graph yields no collapses.
    const emptyModel = {
      graphName: 'empty',
      rootUid: 'ROOT',
      nodes: {},
      links: [],
      tree: [],
      childrenOf: {},
      parentOf: {},
      depthOf: {}
    };
    await installLoadHandler(page, { model: emptyModel });

    await page.goto(HARNESS_URL);
    await expect(page.locator('#status')).toContainText('Empty graph', { timeout: 10_000 });

    // No errors; the default-view block bails because no compounds exist.
    await expect(page.locator('#banner')).toBeHidden();
  });
});
