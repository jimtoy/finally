'use client';

import { PricePoint } from '@/lib/usePriceStream';

interface SparklineProps {
  points: PricePoint[] | undefined;
  width?: number;
  height?: number;
}

/**
 * Hand-rolled inline SVG rather than a chart library: one of these renders per
 * watchlist row and updates twice a second.
 */
export function Sparkline({ points, width = 84, height = 22 }: SparklineProps) {
  if (!points || points.length < 2) {
    return (
      <svg width={width} height={height} role="img" aria-label="Sparkline collecting data" className="opacity-40">
        <line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke="#2a3441" strokeWidth={1} />
      </svg>
    );
  }

  const values = points.map((p) => p.price);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (points.length - 1);
  const path = values
    .map((value, index) => {
      const x = index * stepX;
      const y = height - 1 - ((value - min) / span) * (height - 2);
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  const rising = values[values.length - 1] >= values[0];

  return (
    <svg width={width} height={height} role="img" aria-label="Price sparkline" className="overflow-visible">
      <path d={path} fill="none" stroke={rising ? '#2ecc71' : '#ff5c5c'} strokeWidth={1.25} />
    </svg>
  );
}
