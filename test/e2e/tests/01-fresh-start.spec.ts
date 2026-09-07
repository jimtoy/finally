import { test, expect } from '@playwright/test';
import { DEFAULT_TICKERS, waitForPrice, watchlistRow } from './helpers';

test.describe('Fresh start', () => {
  test('shows the default watchlist, starting cash, and a live stream', async ({ page }) => {
    await page.goto('/');

    for (const ticker of DEFAULT_TICKERS) {
      await expect(watchlistRow(page, ticker)).toBeVisible();
    }

    await expect(page.getByText('$10,000.00').first()).toBeVisible();

    await expect(page.getByRole('status', { name: /Stream/ })).toBeVisible();
    await expect(page.getByTestId('connection-dot')).toBeVisible();

    // Prices must actually be streaming. Per-tick moves are sub-cent (GBM with
    // a ~500ms step), so no single ticker is guaranteed to visibly tick within
    // any short window — watch several of the more volatile tickers and pass
    // as soon as any one of them changes its displayed value.
    const watched = ['TSLA', 'NVDA', 'NFLX', 'AMZN'];
    const cells = await Promise.all(watched.map((ticker) => waitForPrice(page, ticker)));
    const initialValues = await Promise.all(cells.map((cell) => cell.textContent()));

    await expect
      .poll(
        async () => {
          const current = await Promise.all(cells.map((cell) => cell.textContent()));
          return current.some((value, index) => value !== initialValues[index]);
        },
        { timeout: 30_000, message: 'expected at least one watched price to update via SSE' },
      )
      .toBe(true);
  });
});
