import { test, expect } from '@playwright/test';

/**
 * True server-kill-mid-test resilience isn't practical here: the app container
 * is shared by every test file in this suite (single compose stack, sequential
 * run), so restarting or killing it mid-test would break the tests that run
 * after it. Instead this exercises the same recovery path EventSource itself
 * uses — dropping the browser's connection to the stream and confirming the
 * UI both notices (indicator leaves "Live") and recovers (indicator returns to
 * "Live" and prices keep updating) once the connection is restored.
 *
 * Limitation: this proves the frontend's reconnect handling and the
 * connection-status indicator work, but does not prove server-side behavior
 * (e.g. the backend cleaning up a dead client) — that would need a real
 * mid-test server restart, out of scope for this shared-stack suite.
 */
test.describe('SSE resilience', () => {
  test('connection indicator recovers after the stream is interrupted', async ({ page, context }) => {
    await page.goto('/');

    const dot = page.getByTestId('connection-dot');
    await expect(page.getByRole('status', { name: /Live/ })).toBeVisible();

    // Simulate a network drop: block the SSE endpoint, forcing EventSource
    // into its native retry loop, then verify the header reflects that.
    await context.route('**/api/stream/prices', (route) => route.abort());

    // Force a fresh EventSource attempt against the blocked route.
    await page.reload();
    await expect(page.getByRole('status', { name: /Reconnecting|Connecting|Disconnected/ })).toBeVisible({
      timeout: 15_000,
    });

    // Restore connectivity and confirm the client recovers on its own
    // (EventSource retries automatically; PLAN.md sec 6).
    await context.unroute('**/api/stream/prices');
    await expect(page.getByRole('status', { name: /Live/ })).toBeVisible({ timeout: 20_000 });
    await expect(dot).toHaveClass(/bg-tick-up/);
  });
});
