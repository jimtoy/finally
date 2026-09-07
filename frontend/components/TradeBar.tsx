'use client';

import { useEffect, useState } from 'react';
import { formatCurrency, formatPrice } from '@/lib/format';
import { normalizeTicker } from '@/lib/api';
import { TradeSide } from '@/lib/types';
import { PriceMap } from '@/lib/usePriceStream';

interface TradeBarProps {
  selectedTicker: string | null;
  prices: PriceMap;
  onTrade: (ticker: string, quantity: number, side: TradeSide) => Promise<void>;
}

export function TradeBar({ selectedTicker, prices, onTrade }: TradeBarProps) {
  const [ticker, setTicker] = useState(selectedTicker ?? '');
  const [quantity, setQuantity] = useState('1');
  const [pending, setPending] = useState<TradeSide | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);

  useEffect(() => {
    if (selectedTicker) setTicker(selectedTicker);
  }, [selectedTicker]);

  const normalized = normalizeTicker(ticker);
  const shares = Number.parseInt(quantity, 10);
  const price = prices[normalized]?.price ?? null;
  const valid = normalized.length > 0 && Number.isInteger(shares) && shares > 0;
  const estimate = valid && price !== null ? shares * price : null;

  const submit = async (side: TradeSide) => {
    if (!valid || pending) return;
    setPending(side);
    setError(null);
    setConfirmation(null);
    try {
      await onTrade(normalized, shares, side);
      setConfirmation(`${side.toUpperCase()} ${shares} ${normalized} filled`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Trade failed');
    } finally {
      setPending(null);
    }
  };

  return (
    <section className="panel" aria-label="Trade">
      <div className="panel-header">
        <h2 className="panel-title">Market Order</h2>
        <span className="text-2xs uppercase tracking-widest text-terminal-muted">
          {price !== null ? `Last ${formatPrice(price)}` : 'no price'}
        </span>
      </div>

      <form
        className="flex flex-wrap items-end gap-2 p-3"
        onSubmit={(event) => {
          event.preventDefault();
          void submit('buy');
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="text-2xs uppercase tracking-widest text-terminal-muted">Ticker</span>
          <input
            aria-label="Trade ticker"
            value={ticker}
            onChange={(event) => setTicker(event.target.value.toUpperCase())}
            className="field w-24 uppercase"
            maxLength={12}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-2xs uppercase tracking-widest text-terminal-muted">Shares</span>
          <input
            aria-label="Trade quantity"
            type="number"
            min={1}
            step={1}
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            className="field w-24 tabular-nums"
          />
        </label>

        <button type="submit" className="btn-submit" disabled={!valid || pending !== null}>
          {pending === 'buy' ? '…' : 'Buy'}
        </button>
        <button
          type="button"
          onClick={() => void submit('sell')}
          className="btn-submit border border-accent-purple bg-transparent text-accent-yellow"
          disabled={!valid || pending !== null}
        >
          {pending === 'sell' ? '…' : 'Sell'}
        </button>

        <div className="ml-auto text-right text-2xs">
          <div className="uppercase tracking-widest text-terminal-muted">Est. Notional</div>
          <div className="text-sm tabular-nums">{estimate === null ? '--' : formatCurrency(estimate)}</div>
        </div>
      </form>

      {(error || confirmation) && (
        <p
          role={error ? 'alert' : 'status'}
          className={`px-3 pb-2 text-2xs ${error ? 'text-tick-down' : 'text-tick-up'}`}
        >
          {error ?? confirmation}
        </p>
      )}
    </section>
  );
}
