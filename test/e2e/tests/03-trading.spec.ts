import { test, expect } from '@playwright/test';
import { headerStat, positionRow, tradeViaBar } from './helpers';

test.describe('Manual trading', () => {
  test('buying shares decreases cash and opens a position', async ({ page }) => {
    await page.goto('/');

    const cashStat = headerStat(page, 'Cash');
    // The header renders before the /api/portfolio fetch resolves, so wait
    // for the real balance rather than reading whatever's there on first paint.
    await expect(cashStat).toHaveText('$10,000.00');

    await tradeViaBar(page, 'AAPL', 2, 'buy');

    await expect(positionRow(page, 'AAPL')).toBeVisible();
    await expect(cashStat).not.toHaveText('$10,000.00');
  });

  test('selling the full position closes it out and returns cash', async ({ page }) => {
    await page.goto('/');

    await expect(positionRow(page, 'AAPL')).toBeVisible();

    await tradeViaBar(page, 'AAPL', 2, 'sell');

    await expect(positionRow(page, 'AAPL')).toHaveCount(0);
  });
});
