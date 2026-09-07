'use client';

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ClientOnly } from './ClientOnly';
import { formatClock, formatCurrency } from '@/lib/format';
import { HistoryPoint } from '@/lib/types';

interface PnlChartProps {
  history: HistoryPoint[];
  liveValue: number | null;
}

export function PnlChart({ history, liveValue }: PnlChartProps) {
  const data = history.map((point) => ({
    time: new Date(point.recorded_at).getTime(),
    value: point.total_value,
  }));

  // Extend the server-side snapshot series with the live total so the line tracks the stream.
  if (liveValue !== null && data.length > 0) {
    data.push({ time: Date.now(), value: liveValue });
  }

  const first = data[0]?.value ?? 0;
  const last = data[data.length - 1]?.value ?? 0;
  const stroke = last >= first ? '#2ecc71' : '#ff5c5c';

  return (
    <section className="panel" aria-label="Portfolio value history">
      <div className="panel-header">
        <h2 className="panel-title">P&amp;L</h2>
        <span className="text-2xs uppercase tracking-widest text-terminal-muted">total value</span>
      </div>
      <div className="panel-body p-2">
        <ClientOnly fallback={<Placeholder />}>
          {data.length < 2 ? (
            <Placeholder message="Awaiting snapshots" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#2a3441" strokeDasharray="2 4" vertical={false} />
                <XAxis
                  dataKey="time"
                  type="number"
                  domain={['dataMin', 'dataMax']}
                  tickFormatter={(value: number) => formatClock(value)}
                  stroke="#8b98a8"
                  fontSize={10}
                  minTickGap={40}
                />
                <YAxis
                  domain={['dataMin - 10', 'dataMax + 10']}
                  tickFormatter={(value: number) => `$${Math.round(value)}`}
                  stroke="#8b98a8"
                  fontSize={10}
                  width={64}
                />
                <Tooltip
                  contentStyle={{ background: '#131a23', border: '1px solid #2a3441', fontSize: 11 }}
                  labelFormatter={(value) => formatClock(Number(value))}
                  formatter={(value: number) => [formatCurrency(value), 'Total Value']}
                />
                <Line type="monotone" dataKey="value" stroke={stroke} strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ClientOnly>
      </div>
    </section>
  );
}

function Placeholder({ message = 'Loading' }: { message?: string }) {
  return (
    <div className="flex h-full min-h-[120px] items-center justify-center text-2xs uppercase tracking-widest text-terminal-muted">
      {message}
    </div>
  );
}
