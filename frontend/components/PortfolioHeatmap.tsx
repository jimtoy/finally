'use client';

import { ResponsiveContainer, Treemap } from 'recharts';
import { ClientOnly } from './ClientOnly';
import { formatPercent } from '@/lib/format';
import { DerivedPosition } from '@/lib/portfolio';

/** Saturates at +/-5% so typical intraday moves still show a readable gradient. */
const FULL_SCALE_PERCENT = 5;

export function heatColor(percentChange: number): string {
  const intensity = Math.min(Math.abs(percentChange) / FULL_SCALE_PERCENT, 1);
  const alpha = 0.15 + intensity * 0.7;
  return percentChange >= 0 ? `rgba(46, 204, 113, ${alpha})` : `rgba(255, 92, 92, ${alpha})`;
}

interface PortfolioHeatmapProps {
  positions: DerivedPosition[];
  onSelect: (ticker: string) => void;
}

export function PortfolioHeatmap({ positions, onSelect }: PortfolioHeatmapProps) {
  const data = positions
    .filter((position) => position.market_value > 0)
    .map((position) => ({
      name: position.ticker,
      size: position.market_value,
      percentChange: position.percent_change,
      weight: position.weight,
    }));

  return (
    <section className="panel" aria-label="Portfolio heatmap">
      <div className="panel-header">
        <h2 className="panel-title">Heatmap</h2>
        <span className="text-2xs uppercase tracking-widest text-terminal-muted">weight × p&amp;l</span>
      </div>
      <div className="panel-body p-1">
        <ClientOnly fallback={<Placeholder />}>
          {data.length === 0 ? (
            <Placeholder message="Buy a position to populate" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <Treemap
                data={data}
                dataKey="size"
                stroke="#0d1117"
                isAnimationActive={false}
                content={<HeatCell onSelect={onSelect} />}
              />
            </ResponsiveContainer>
          )}
        </ClientOnly>
      </div>
    </section>
  );
}

interface HeatCellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  percentChange?: number;
  onSelect?: (ticker: string) => void;
}

function HeatCell({ x = 0, y = 0, width = 0, height = 0, name, percentChange = 0, onSelect }: HeatCellProps) {
  if (!name || width <= 0 || height <= 0) return null;
  const showLabel = width > 46 && height > 28;

  return (
    <g onClick={() => onSelect?.(name)} className="cursor-pointer">
      <rect x={x} y={y} width={width} height={height} fill={heatColor(percentChange)} stroke="#0d1117" strokeWidth={2} />
      {showLabel && (
        // A dark outline painted under the glyphs keeps labels legible over any fill intensity.
        <g stroke="#0d1117" strokeWidth={3} paintOrder="stroke" fill="#f2f6fa">
          <text x={x + width / 2} y={y + height / 2 - 4} textAnchor="middle" fontSize={11} fontWeight={700}>
            {name}
          </text>
          <text x={x + width / 2} y={y + height / 2 + 10} textAnchor="middle" fontSize={10}>
            {formatPercent(percentChange)}
          </text>
        </g>
      )}
    </g>
  );
}

function Placeholder({ message = 'Loading heatmap' }: { message?: string }) {
  return (
    <div className="flex h-full min-h-[120px] items-center justify-center text-2xs uppercase tracking-widest text-terminal-muted">
      {message}
    </div>
  );
}
