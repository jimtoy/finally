import { exec } from 'node:child_process';
import { promisify } from 'node:util';
import { test, expect } from '@playwright/test';
import { watchlistRow } from './helpers';

const run = promisify(exec);

/**
 * The one CI-meaningful check in this suite that isn't "does the page
 * render": data must survive an app-container restart, proving the SQLite
 * volume is actually persisted rather than living in a container's writable
 * layer. Runs last because it restarts the shared app service.
 *
 * Restarting requires a way to reach the docker control plane from inside the
 * Playwright container. docker-compose.test.yml bind-mounts the host's docker
 * socket into this service and sets `RESTART_CMD=docker restart
 * finally-test-app` for exactly this. If a different setup doesn't provide
 * that (e.g. a CI runner without socket access), the var is simply unset and
 * this test documents the gap and skips rather than silently passing.
 */
test.describe('Database persistence', () => {
  test('a watchlist change survives an app restart', async ({ page }) => {
    await page.goto('/');

    const ticker = 'DBTEST';
    await page.getByLabel('Add ticker').fill(ticker);
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(watchlistRow(page, ticker)).toBeVisible();

    const restartCmd = process.env.RESTART_CMD;
    test.skip(!restartCmd, 'RESTART_CMD not set — see test/README.md for how to enable this check');

    await run(restartCmd!);

    // Poll rather than a single reload: the app needs a moment to reopen the
    // SQLite file and re-bind before it serves traffic again.
    await expect(async () => {
      await page.reload({ timeout: 5_000 });
      await expect(watchlistRow(page, ticker)).toBeVisible({ timeout: 2_000 });
    }).toPass({ timeout: 60_000, intervals: [1_000, 2_000, 5_000] });
  });
});
