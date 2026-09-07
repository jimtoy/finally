'use client';

import { formatCurrency, formatPercent, formatSignedCurrency, pnlColor } from '@/lib/format';
import { ConnectionStatus } from '@/lib/usePriceStream';

const STATUS_STYLE: Record<ConnectionStatus, { dot: string; label: string }> = {
  connecting: { dot: 'bg-accent-yellow', label: 'Connecting' },
  connected: { dot: 'bg-tick-up', label: 'Live' },
  reconnecting: { dot: 'bg-accent-yellow', label: 'Reconnecting' },
  disconnected: { dot: 'bg-tick-down', label: 'Disconnected' },
};

interface HeaderProps {
  totalValue: number;
  cashBalance: number;
  unrealizedPnl: number;
  status: ConnectionStatus;
}

export function Header({ totalValue, cashBalance, unrealizedPnl, status }: HeaderProps) {
  const style = STATUS_STYLE[status];
  const investedBasis = totalValue - unrealizedPnl;
  const pnlPercent = investedBasis > 0 ? (unrealizedPnl / investedBasis) * 100 : 0;

  return (
    <header className="flex shrink-0 items-center justify-between border-b border-terminal-border bg-terminal-raised px-4 py-2">
      <div className="flex items-baseline gap-2">
        <span className="text-base font-bold tracking-[0.2em] text-accent-yellow">FINALLY</span>
        <span className="text-2xs uppercase tracking-widest text-terminal-muted">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-6">
        <Stat label="Portfolio Value" value={formatCurrency(totalValue)} className="text-accent-blue" />
        <Stat label="Cash" value={formatCurrency(cashBalance)} />
        <Stat
          label="Unrealized P&L"
          value={`${formatSignedCurrency(unrealizedPnl)} (${formatPercent(pnlPercent)})`}
          className={pnlColor(unrealizedPnl)}
        />
        <div className="flex items-center gap-2" role="status" aria-label={`Stream ${style.label}`}>
          <span data-testid="connection-dot" className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
          <span className="text-2xs uppercase tracking-widest text-terminal-muted">{style.label}</span>
        </div>
      </div>
    </header>
  );
}

function Stat({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="text-right">
      <div className="text-2xs uppercase tracking-widest text-terminal-muted">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${className}`}>{value}</div>
    </div>
  );
}
