'use client';

import { FormEvent, useState } from 'react';
import { Sparkline } from './Sparkline';
import { formatPercent, formatPrice, pnlColor, sessionChangePercent } from '@/lib/format';
import { useFlash } from '@/lib/useFlash';
import { HistoryMap, PriceMap } from '@/lib/usePriceStream';
import { WatchlistEntry } from '@/lib/types';

interface WatchlistPanelProps {
  entries: WatchlistEntry[];
  prices: PriceMap;
  history: HistoryMap;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}

export function WatchlistPanel({
  entries,
  prices,
  history,
  selectedTicker,
  onSelect,
  onAdd,
  onRemove,
}: WatchlistPanelProps) {
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const ticker = draft.trim();
    if (!ticker || busy) return;
    setBusy(true);
    try {
      await onAdd(ticker);
      setDraft('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-label="Watchlist">
      <div className="panel-header">
        <h2 className="panel-title">Watchlist</h2>
        <form onSubmit={submit} className="flex items-center gap-1">
          <input
            aria-label="Add ticker"
            placeholder="ADD"
            value={draft}
            onChange={(event) => setDraft(event.target.value.toUpperCase())}
            className="field w-20 py-1 text-2xs uppercase"
            maxLength={12}
          />
          <button type="submit" className="btn-submit px-2 py-1 text-2xs" disabled={busy || !draft.trim()}>
            Add
          </button>
        </form>
      </div>

      <div className="panel-body">
        {entries.length === 0 ? (
          <p className="p-4 text-2xs uppercase tracking-widest text-terminal-muted">Watchlist empty</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-terminal-panel text-2xs uppercase tracking-widest text-terminal-muted">
              <tr>
                <th className="px-3 py-1.5 text-left font-normal">Symbol</th>
                <th className="px-2 py-1.5 text-right font-normal">Last</th>
                <th className="px-2 py-1.5 text-right font-normal">Chg %</th>
                <th className="px-2 py-1.5 text-right font-normal">Trend</th>
                <th className="w-6" />
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <WatchlistRow
                  key={entry.ticker}
                  entry={entry}
                  price={prices[entry.ticker]?.price ?? entry.price ?? null}
                  openingPrice={prices[entry.ticker]?.opening_price ?? entry.opening_price ?? null}
                  points={history[entry.ticker]}
                  selected={selectedTicker === entry.ticker}
                  onSelect={onSelect}
                  onRemove={onRemove}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

interface WatchlistRowProps {
  entry: WatchlistEntry;
  price: number | null;
  openingPrice: number | null;
  points: HistoryMap[string] | undefined;
  selected: boolean;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => Promise<void>;
}

function WatchlistRow({ entry, price, openingPrice, points, selected, onSelect, onRemove }: WatchlistRowProps) {
  const flash = useFlash(price);
  const changePercent = sessionChangePercent(price, openingPrice) ?? entry.change_percent ?? null;

  return (
    <tr
      onClick={() => onSelect(entry.ticker)}
      aria-selected={selected}
      className={`cursor-pointer border-b border-terminal-border/50 hover:bg-terminal-raised/60 ${
        selected ? 'bg-terminal-raised' : ''
      }`}
    >
      <td className="px-3 py-1.5 font-semibold">
        <span className={selected ? 'text-accent-blue' : ''}>{entry.ticker}</span>
      </td>
      <td
        data-testid={`price-${entry.ticker}`}
        className={`px-2 py-1.5 text-right tabular-nums ${flash}`}
      >
        {formatPrice(price)}
      </td>
      <td className={`px-2 py-1.5 text-right tabular-nums ${pnlColor(changePercent)}`}>
        {formatPercent(changePercent)}
      </td>
      <td className="px-2 py-1.5">
        <div className="flex justify-end">
          <Sparkline points={points} />
        </div>
      </td>
      <td className="pr-2">
        <button
          type="button"
          aria-label={`Remove ${entry.ticker}`}
          onClick={(event) => {
            event.stopPropagation();
            void onRemove(entry.ticker);
          }}
          className="text-terminal-muted transition-colors hover:text-tick-down"
        >
          ×
        </button>
      </td>
    </tr>
  );
}
