import { test, expect } from '@playwright/test';
import { waitForPrice, watchlistRow } from './helpers';

test.describe('Watchlist management', () => {
  test('adds and then removes a ticker via the UI', async ({ page }) => {
    await page.goto('/');

    const ticker = 'PYPL';
    await expect(watchlistRow(page, ticker)).toHaveCount(0);

    await page.getByLabel('Add ticker').fill(ticker);
    await page.getByRole('button', { name: 'Add', exact: true }).click();

    await expect(watchlistRow(page, ticker)).toBeVisible();
    // A newly added ticker gets a deterministic plausible price immediately (PLAN.md sec 6).
    await waitForPrice(page, ticker);

    await page.getByLabel(`Remove ${ticker}`).click();
    await expect(watchlistRow(page, ticker)).toHaveCount(0);
  });
});
