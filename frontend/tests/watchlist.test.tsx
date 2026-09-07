import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { WatchlistPanel } from '@/components/WatchlistPanel';
import { PriceTick, WatchlistEntry } from '@/lib/types';
import { PriceMap } from '@/lib/usePriceStream';

const entries: WatchlistEntry[] = [
  { ticker: 'AAPL', added_at: '2026-09-07T09:30:00Z', price: 190, opening_price: 190, change: 0, change_percent: 0, direction: 'flat' },
];

const priceMap = (price: number, opening = 190): PriceMap => ({
  AAPL: {
    ticker: 'AAPL',
    price,
    previous_price: opening,
    opening_price: opening,
    timestamp: 1788000000,
    direction: 'flat',
  } satisfies PriceTick,
});

function renderPanel(prices: PriceMap, overrides: Partial<Parameters<typeof WatchlistPanel>[0]> = {}) {
  const props = {
    entries,
    prices,
    history: {},
    selectedTicker: null,
    onSelect: vi.fn(),
    onAdd: vi.fn().mockResolvedValue(undefined),
    onRemove: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  return { props, ...render(<WatchlistPanel {...props} />) };
}

describe('WatchlistPanel', () => {
  it('renders the live price and session change', () => {
    renderPanel(priceMap(199.5, 190));
    expect(screen.getByTestId('price-AAPL')).toHaveTextContent('199.50');
    expect(screen.getByText('+5.00%')).toBeInTheDocument();
  });

  it('flashes green on an uptick and red on a downtick', async () => {
    const { rerender, props } = renderPanel(priceMap(190));
    const cell = screen.getByTestId('price-AAPL');
    expect(cell.className).not.toMatch(/flash/);

    rerender(<WatchlistPanel {...props} prices={priceMap(191)} />);
    await waitFor(() => expect(screen.getByTestId('price-AAPL').className).toMatch(/flash-up/));

    rerender(<WatchlistPanel {...props} prices={priceMap(185)} />);
    await waitFor(() => expect(screen.getByTestId('price-AAPL').className).toMatch(/flash-down/));
  });

  it('adds a normalized ticker and clears the input', async () => {
    const user = userEvent.setup();
    const { props } = renderPanel(priceMap(190));

    await user.type(screen.getByLabelText('Add ticker'), 'pypl');
    await user.click(screen.getByRole('button', { name: 'Add' }));

    expect(props.onAdd).toHaveBeenCalledWith('PYPL');
    await waitFor(() => expect(screen.getByLabelText('Add ticker')).toHaveValue(''));
  });

  it('removes a ticker without selecting the row', async () => {
    const user = userEvent.setup();
    const { props } = renderPanel(priceMap(190));

    await user.click(screen.getByRole('button', { name: 'Remove AAPL' }));

    expect(props.onRemove).toHaveBeenCalledWith('AAPL');
    expect(props.onSelect).not.toHaveBeenCalled();
  });

  it('selects a ticker when its row is clicked', async () => {
    const user = userEvent.setup();
    const { props } = renderPanel(priceMap(190));

    await user.click(screen.getByText('AAPL'));

    expect(props.onSelect).toHaveBeenCalledWith('AAPL');
  });
});
