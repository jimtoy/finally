import { test, expect } from '@playwright/test';
import { positionRow, sendChatMessage } from './helpers';

test.describe('AI chat (mocked)', () => {
  test('a mock-grammar trade message executes a real trade and shows an inline confirmation', async ({ page }) => {
    await page.goto('/');

    const chat = page.locator('section[aria-label="AI assistant"]');
    await sendChatMessage(page, 'buy 3 MSFT');

    await expect(chat.getByText('buy 3 MSFT', { exact: true })).toBeVisible(); // echoed user message

    const confirmation = chat.getByText(/BUY 3 MSFT @/);
    await expect(confirmation).toBeVisible({ timeout: 15_000 });

    await expect(positionRow(page, 'MSFT')).toBeVisible();
  });

  test('a message outside the mock grammar gets the canned analysis reply with no actions', async ({ page }) => {
    await page.goto('/');

    const chat = page.locator('section[aria-label="AI assistant"]');
    await sendChatMessage(page, 'how is my portfolio doing?');

    await expect(chat.getByText(/canned response/)).toBeVisible({ timeout: 15_000 });
  });
});
