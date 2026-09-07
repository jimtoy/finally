import { describe, expect, it } from 'vitest';
import { parsePriceEvent, parseSnapshotEvent } from '@/lib/usePriceStream';
import { formatClock, tickTimeMs } from '@/lib/format';

// Exact wire shapes emitted by backend/app/market/stream.py and PriceUpdate.to_dict().
const AAPL = {
  ticker: 'AAPL',
  price: 190.5,
  previous_price: 190.25,
  opening_price: 189,
  timestamp: 1788000000.123,
  change: 0.25,
  change_percent: 0.1314,
  direction: 'up',
};
const GOOGL = { ...AAPL, ticker: 'GOOGL', price: 175.1, direction: 'down' };

describe('parseSnapshotEvent', () => {
  it('expands the ticker-keyed snapshot object into ticks', () => {
    const ticks = parseSnapshotEvent(JSON.stringify({ AAPL, GOOGL }));

    expect(ticks.map((tick) => tick.ticker)).toEqual(['AAPL', 'GOOGL']);
    expect(ticks[0].price).toBe(190.5);
    expect(ticks[1].opening_price).toBe(189);
  });

  it('ignores malformed entries instead of dropping the whole snapshot', () => {
    const ticks = parseSnapshotEvent(JSON.stringify({ AAPL, BAD: { ticker: 'BAD' }, NULL: null }));
    expect(ticks.map((tick) => tick.ticker)).toEqual(['AAPL']);
  });

  it('returns nothing for an empty snapshot', () => {
    expect(parseSnapshotEvent('{}')).toEqual([]);
  });
});

describe('parsePriceEvent', () => {
  it('reads the single tick object of a price event', () => {
    expect(parsePriceEvent(JSON.stringify(AAPL))).toEqual([expect.objectContaining({ ticker: 'AAPL', price: 190.5 })]);
  });

  it('rejects a payload that is not a tick', () => {
    expect(parsePriceEvent(JSON.stringify({ hello: 'world' }))).toEqual([]);
  });
});

describe('tickTimeMs', () => {
  it('converts the stream Unix seconds to the milliseconds Date expects', () => {
    expect(tickTimeMs(AAPL.timestamp)).toBe(1788000000123);
    expect(new Date(tickTimeMs(AAPL.timestamp)).getUTCFullYear()).toBe(2026);
  });

  it('keeps real gaps between consecutive ticks', () => {
    expect(tickTimeMs(1788000000.5) - tickTimeMs(1788000000)).toBe(500);
  });

  it('formats a converted tick as a wall clock time, not the epoch', () => {
    expect(formatClock(tickTimeMs(AAPL.timestamp))).toMatch(/^\d{2}:\d{2}:\d{2}$/);
  });
});
