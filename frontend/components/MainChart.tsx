'use client';

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ClientOnly } from './ClientOnly';
import { formatClock, formatPercent, formatPrice, pnlColor, sessionChangePercent, tickTimeMs } from '@/lib/format';
import { PriceTick } from '@/lib/types';
import { PricePoint } from '@/lib/usePriceStream';

interface MainChartProps {
  ticker: string | null;
  tick: PriceTick | undefined;
  points: PricePoint[] | undefined;
}

export function MainChart({ ticker, tick, points }: MainChartProps) {
  const changePercent = sessionChangePercent(tick?.price ?? null, tick?.opening_price ?? null);
  const rising = (changePercent ?? 0) >= 0;
  const stroke = rising ? '#2ecc71' : '#ff5c5c';
  const data = points ?? [];

  return (
    <section className="panel" aria-label="Price chart">
      <div className="panel-header">
        <div className="flex min-w-0 items-baseline gap-3 overflow-hidden">
          <h2 className="panel-title">{ticker ?? 'No Selection'}</h2>
          {tick && (
            <>
              <span className="text-lg font-semibold tabular-nums">{formatPrice(tick.price)}</span>
              <span className={`text-xs tabular-nums ${pnlColor(changePercent)}`}>{formatPercent(changePercent)}</span>
            </>
          )}
        </div>
        <span className="ml-4 shrink-0 text-2xs uppercase tracking-widest text-terminal-muted">
          {tick ? formatClock(tickTimeMs(tick.timestamp)) : 'awaiting stream'}
        </span>
      </div>

      <div className="panel-body p-2">
        <ClientOnly fallback={<ChartPlaceholder message="Loading chart" />}>
          {data.length < 2 ? (
            <ChartPlaceholder message={ticker ? `Collecting ${ticker} price history…` : 'Select a ticker'} />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                  </linearGradient>
                </defs>
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
                  domain={['dataMin - 0.2', 'dataMax + 0.2']}
                  tickFormatter={(value: number) => value.toFixed(2)}
                  stroke="#8b98a8"
                  fontSize={10}
                  width={56}
                />
                <Tooltip
                  contentStyle={{ background: '#131a23', border: '1px solid #2a3441', fontSize: 11 }}
                  labelFormatter={(value) => formatClock(Number(value))}
                  formatter={(value: number) => [formatPrice(value), 'Price']}
                />
                <Area
                  type="monotone"
                  dataKey="price"
                  stroke={stroke}
                  strokeWidth={1.5}
                  fill="url(#priceFill)"
                  isAnimationActive={false}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ClientOnly>
      </div>
    </section>
  );
}

function ChartPlaceholder({ message }: { message: string }) {
  return (
    <div className="flex h-full min-h-[160px] items-center justify-center text-2xs uppercase tracking-widest text-terminal-muted">
      {message}
    </div>
  );
}
