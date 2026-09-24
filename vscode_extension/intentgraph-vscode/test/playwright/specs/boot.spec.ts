// Boot spec: the simplest possible round-trip.
//
// 1. Navigate to the harness page (the webview JS has already mounted and
//    immediately called `messaging.loadGraph()`, which posts an
//    'intentgraph/load' request to our shim).
// 2. Test-side: register a handler that returns the serialised model built
//    from test/fixtures/validator.ig.json.
// 3. Wait for the UI to reach the 'ready' phase and assert on the status text
//    + DOM hooks.

import { test, expect } from '@playwright/test';

import { loadFixture } from '../fixtures';

const HARNESS_URL = '/test/playwright/harness/index.html';

test.describe('boot', () => {
  test('loads validator.ig.json and reaches ready state with 21 nodes / 19 links', async ({ page }) => {
    // Build the model on the Node side, then push it into the page once the
    // bus is installed but BEFORE main.js fires its load request. We can't
    // race that easily — instead, install the handler via init script.
    const model = await loadFixture('test/fixtures/validator.ig.json');

    // initScript runs before any other script on the page. It registers a
    // load-graph handler on a "pre-bus" stash; vscodeShim.js (loaded next)
    // installs the real bus and immediately drains the stash.
    //
    // Simpler approach: addInitScript injects the model + handler installer
    // and uses a polling install that runs the moment __igTestBus appears.
    await page.addInitScript((serialisedModel) => {
      (window as any).__igPendingModel = serialisedModel;
      const install = () => {
        const bus = (window as any).__igTestBus;
        if (!bus) {
          setTimeout(install, 0);
          return;
        }
        bus.handleRequest('intentgraph/load', () => ({
          ok: true,
          model: serialisedModel,
          fileHash: 'test-fixture-hash',
          lenses: {},
          default_lens: null
        }));
      };
      install();
    }, model);

    await page.goto(HARNESS_URL);

    // The shim, main.js, then loadAndRender() runs. ELK layout is async so
    // the ready transition is not synchronous. Wait for status text.
    const status = page.locator('#status');
    await expect(status).toContainText('Ready', { timeout: 15_000 });
    await expect(status).toContainText('21 nodes');
    await expect(status).toContainText('19 links');

    // Spinner gone, empty placeholder not active.
    await expect(page.locator('#spinner')).toBeHidden();
    await expect(page.locator('#cy')).not.toHaveClass(/ig-empty/);

    // No error banner.
    await expect(page.locator('#banner')).toBeHidden();
  });

  test('empty load shows empty placeholder', async ({ page }) => {
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
    await page.addInitScript((m) => {
      const install = () => {
        const bus = (window as any).__igTestBus;
        if (!bus) {
          setTimeout(install, 0);
          return;
        }
        bus.handleRequest('intentgraph/load', () => ({
          ok: true,
          model: m,
          fileHash: 'empty',
          lenses: {},
          default_lens: null
        }));
      };
      install();
    }, emptyModel);

    await page.goto(HARNESS_URL);

    await expect(page.locator('#status')).toContainText('Empty graph', { timeout: 10_000 });
    await expect(page.locator('#cy')).toHaveClass(/ig-empty/);
  });
});
