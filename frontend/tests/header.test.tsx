import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Header } from '@/components/Header';
import { heatColor } from '@/components/PortfolioHeatmap';
import { ConnectionStatus } from '@/lib/usePriceStream';

const renderHeader = (status: ConnectionStatus) =>
  render(<Header totalValue={12345.67} cashBalance={5000} unrealizedPnl={345.67} status={status} />);

describe('Header', () => {
  it('shows portfolio value, cash, and signed P&L', () => {
    renderHeader('connected');
    expect(screen.getByText('$12,345.67')).toBeInTheDocument();
    expect(screen.getByText('$5,000.00')).toBeInTheDocument();
    expect(screen.getByText(/\+\$345\.67/)).toBeInTheDocument();
  });

  it.each([
    ['connected', 'bg-tick-up', 'Live'],
    ['reconnecting', 'bg-accent-yellow', 'Reconnecting'],
    ['disconnected', 'bg-tick-down', 'Disconnected'],
  ] as const)('colors the %s indicator', (status, expectedClass, label) => {
    renderHeader(status);
    expect(screen.getByTestId('connection-dot')).toHaveClass(expectedClass);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});

describe('heatColor', () => {
  it('greens gains and reds losses, deepening with magnitude', () => {
    expect(heatColor(3)).toContain('46, 204, 113');
    expect(heatColor(-3)).toContain('255, 92, 92');

    const faint = Number(heatColor(0.5).match(/([\d.]+)\)$/)![1]);
    const strong = Number(heatColor(5).match(/([\d.]+)\)$/)![1]);
    expect(strong).toBeGreaterThan(faint);
  });
});
