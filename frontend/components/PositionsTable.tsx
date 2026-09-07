'use client';

import { formatCurrency, formatPercent, formatPrice, formatQuantity, formatSignedCurrency, pnlColor } from '@/lib/format';
import { DerivedPosition } from '@/lib/portfolio';
import { useFlash } from '@/lib/useFlash';

interface PositionsTableProps {
  positions: DerivedPosition[];
  onSelect: (ticker: string) => void;
}

export function PositionsTable({ positions, onSelect }: PositionsTableProps) {
  return (
    <section className="panel" aria-label="Positions">
      <div className="panel-header">
        <h2 className="panel-title">Positions</h2>
        <span className="text-2xs uppercase tracking-widest text-terminal-muted">{positions.length} held</span>
      </div>
      <div className="panel-body">
        {positions.length === 0 ? (
          <p className="p-4 text-2xs uppercase tracking-widest text-terminal-muted">No open positions</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-terminal-panel text-2xs uppercase tracking-widest text-terminal-muted">
              <tr>
                <th className="px-3 py-1.5 text-left font-normal">Symbol</th>
                <th className="px-2 py-1.5 text-right font-normal">Qty</th>
                <th className="px-2 py-1.5 text-right font-normal">Avg Cost</th>
                <th className="px-2 py-1.5 text-right font-normal">Last</th>
                <th className="px-2 py-1.5 text-right font-normal">Mkt Value</th>
                <th className="px-2 py-1.5 text-right font-normal">Unrl P&L</th>
                <th className="px-3 py-1.5 text-right font-normal">%</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <PositionRow key={position.ticker} position={position} onSelect={onSelect} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function PositionRow({ position, onSelect }: { position: DerivedPosition; onSelect: (ticker: string) => void }) {
  const flash = useFlash(position.current_price);

  return (
    <tr
      onClick={() => onSelect(position.ticker)}
      className="cursor-pointer border-b border-terminal-border/50 hover:bg-terminal-raised/60"
    >
      <td className="px-3 py-1.5 font-semibold">{position.ticker}</td>
      <td className="px-2 py-1.5 text-right tabular-nums">{formatQuantity(position.quantity)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums">{formatPrice(position.average_cost)}</td>
      <td className={`px-2 py-1.5 text-right tabular-nums ${flash}`}>{formatPrice(position.current_price)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums">{formatCurrency(position.market_value)}</td>
      <td className={`px-2 py-1.5 text-right tabular-nums ${pnlColor(position.unrealized_pnl)}`}>
        {formatSignedCurrency(position.unrealized_pnl)}
      </td>
      <td className={`px-3 py-1.5 text-right tabular-nums ${pnlColor(position.percent_change)}`}>
        {formatPercent(position.percent_change)}
      </td>
    </tr>
  );
}
