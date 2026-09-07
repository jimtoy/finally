import { describe, expect, it } from 'vitest';
import { derivePortfolio } from '@/lib/portfolio';
import { appendPoint, MAX_HISTORY_POINTS } from '@/lib/usePriceStream';
import { sessionChangePercent } from '@/lib/format';
import { Portfolio, PriceTick } from '@/lib/types';

const tick = (ticker: string, price: number): PriceTick => ({
  ticker,
  price,
  previous_price: price,
  opening_price: price,
  timestamp: 1788000000,
  direction: 'flat',
});

const portfolio: Portfolio = {
  cash_balance: 5000,
  total_value: 0,
  unrealized_pnl: 0,
  positions: [
    { ticker: 'AAPL', quantity: 10, average_cost: 190, current_price: 190, unrealized_pnl: 0, percent_change: 0 },
    { ticker: 'NVDA', quantity: 5, average_cost: 100, current_price: 100, unrealized_pnl: 0, percent_change: 0 },
  ],
};

describe('derivePortfolio', () => {
  it('reprices positions from the live stream and totals cash plus market value', () => {
    const derived = derivePortfolio(portfolio, { AAPL: tick('AAPL', 200), NVDA: tick('NVDA', 90) });

    const [aapl, nvda] = derived.positions;
    expect(aapl.market_value).toBe(2000);
    expect(aapl.unrealized_pnl).toBeCloseTo(100);
    expect(aapl.percent_change).toBeCloseTo(5.263, 3);
    expect(nvda.unrealized_pnl).toBeCloseTo(-50);
    expect(derived.total_value).toBe(5000 + 2000 + 450);
    expect(derived.unrealized_pnl).toBeCloseTo(50);
  });

  it('weights positions by share of invested value', () => {
    const derived = derivePortfolio(portfolio, { AAPL: tick('AAPL', 200), NVDA: tick('NVDA', 100) });
    expect(derived.positions[0].weight).toBeCloseTo(2000 / 2500);
    expect(derived.positions[1].weight).toBeCloseTo(500 / 2500);
  });

  it('falls back to the server price when the stream has no tick yet', () => {
    const derived = derivePortfolio(portfolio, {});
    expect(derived.positions[0].current_price).toBe(190);
    expect(derived.total_value).toBe(5000 + 1900 + 500);
  });

  it('returns an empty shell before the portfolio loads', () => {
    expect(derivePortfolio(null, {})).toMatchObject({ total_value: 0, positions: [] });
  });
});

describe('sessionChangePercent', () => {
  it('measures the move against the opening price', () => {
    expect(sessionChangePercent(105, 100)).toBeCloseTo(5);
    expect(sessionChangePercent(95, 100)).toBeCloseTo(-5);
  });

  it('returns null without an opening price', () => {
    expect(sessionChangePercent(105, null)).toBeNull();
  });
});

describe('appendPoint', () => {
  it('caps the per-ticker history buffer', () => {
    let points = [] as ReturnType<typeof appendPoint>;
    for (let i = 0; i < MAX_HISTORY_POINTS + 50; i += 1) {
      points = appendPoint(points, { time: i, price: i });
    }
    expect(points).toHaveLength(MAX_HISTORY_POINTS);
    expect(points[points.length - 1].price).toBe(MAX_HISTORY_POINTS + 49);
  });
});
