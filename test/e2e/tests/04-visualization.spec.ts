import { test, expect } from '@playwright/test';
import { positionRow, tradeViaBar } from './helpers';

test.describe('Portfolio visualization', () => {
  test('heatmap renders a position rectangle and the P&L chart gets a data point', async ({ page }) => {
    await page.goto('/');

    await tradeViaBar(page, 'GOOGL', 3, 'buy');
    await expect(positionRow(page, 'GOOGL')).toBeVisible();

    const heatmap = page.locator('section[aria-label="Portfolio heatmap"]');
    await expect(heatmap.getByText('Buy a position to populate')).toHaveCount(0);
    // Recharts draws each treemap cell as an <svg><rect>; a GOOGL label proves
    // the position rendered as a sized/colored rectangle, not just the legend.
    await expect(heatmap.locator('svg rect')).not.toHaveCount(0);
    await expect(heatmap.getByText('GOOGL')).toBeVisible();

    const pnlChart = page.locator('section[aria-label="Portfolio value history"]');
    // A trade immediately records a snapshot (PLAN.md sec 7), so the chart
    // should have moved off its "Awaiting snapshots" placeholder.
    await expect(pnlChart.getByText('Awaiting snapshots')).toHaveCount(0);
    await expect(pnlChart.locator('svg .recharts-line')).toBeVisible();
  });
});
