import { Page, expect } from '@playwright/test';

export const DEFAULT_TICKERS = [
  'AAPL',
  'GOOGL',
  'MSFT',
  'AMZN',
  'TSLA',
  'NVDA',
  'META',
  'JPM',
  'V',
  'NFLX',
];

export function watchlistRow(page: Page, ticker: string) {
  return page
    .locator('section[aria-label="Watchlist"] tbody tr')
    .filter({ has: page.getByRole('cell', { name: ticker, exact: true }) });
}

export function positionRow(page: Page, ticker: string) {
  return page
    .locator('section[aria-label="Positions"] tbody tr')
    .filter({ has: page.getByRole('cell', { name: ticker, exact: true }) });
}

/** The value element under a header <Stat label="..."> block (e.g. "Cash", "Portfolio Value"). */
export function headerStat(page: Page, label: string) {
  return page
    .locator('header')
    .getByText(label, { exact: true })
    .locator('xpath=following-sibling::div[1]');
}

/** Waits until the price cell for `ticker` renders a non-placeholder numeric value. */
export async function waitForPrice(page: Page, ticker: string) {
  const cell = page.getByTestId(`price-${ticker}`);
  await expect(cell).not.toHaveText('--', { timeout: 20_000 });
  return cell;
}

export async function tradeViaBar(page: Page, ticker: string, quantity: number, side: 'buy' | 'sell') {
  await page.getByLabel('Trade ticker').fill(ticker);
  await page.getByLabel('Trade quantity').fill(String(quantity));
  await page.getByRole('button', { name: side === 'buy' ? 'Buy' : 'Sell', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: new RegExp(`${side.toUpperCase()} ${quantity} ${ticker}`, 'i') })).toBeVisible({
    timeout: 15_000,
  });
}

export async function sendChatMessage(page: Page, text: string) {
  await page.getByLabel('Chat message').fill(text);
  await page.getByRole('button', { name: 'Send' }).click();
}
