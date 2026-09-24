// Shared helper: install an 'intentgraph/load' handler on the test bus via
// page.addInitScript. Polls until __igTestBus is installed by vscodeShim.js,
// then registers the handler. Runs before main.js mounts.

import type { Page } from '@playwright/test';
import type { SerialisedIntentGraphModel } from '../fixtures';

export interface LoadFixture {
  model: SerialisedIntentGraphModel;
  fileHash?: string;
  lenses?: Record<string, unknown>;
  default_lens?: string | null;
}

export async function installLoadHandler(page: Page, fixture: LoadFixture): Promise<void> {
  await page.addInitScript((payload) => {
    const install = () => {
      const bus = (window as unknown as { __igTestBus?: { handleRequest: (m: string, h: () => unknown) => void } }).__igTestBus;
      if (!bus) {
        setTimeout(install, 0);
        return;
      }
      bus.handleRequest('intentgraph/load', () => ({
        ok: true,
        model: payload.model,
        fileHash: payload.fileHash ?? 'test-fixture-hash',
        lenses: payload.lenses ?? {},
        default_lens: payload.default_lens ?? null
      }));
    };
    install();
  }, fixture as unknown as Record<string, unknown>);
}
