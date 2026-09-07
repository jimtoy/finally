# FinAlly Frontend

Next.js + TypeScript trading workstation UI, built as a **static export** (`output: 'export'`) and served
by the FastAPI backend as static files from the same origin. See `planning/PLAN.md` §3, §10, and §11.

## Commands

```bash
npm install
npm run dev     # http://localhost:3000
npm run build   # static export -> out/
npm test        # vitest + React Testing Library
```

## Backend

All data comes from the backend at the **same origin** under `/api/*` — there is no CORS config and no
API base URL to set. `lib/api.ts` is the single place every REST call is defined, mirroring the contract
in `planning/PLAN.md` §8; `lib/usePriceStream.ts` owns the `EventSource` connection to
`/api/stream/prices`.

In development the app is served by Next on port 3000, so `next.config.mjs` proxies `/api/*` to
`http://localhost:8000` (override with `NEXT_PUBLIC_DEV_API_ORIGIN`). The rewrite is dev-only and is not
part of the export.

> Note: Next's dev proxy buffers Server-Sent Events, so live prices will not tick through `npm run dev`
> against a separate backend. To exercise streaming, build and let the backend serve `out/` on port 8000 —
> the production topology.

## Layout

```
app/page.tsx          Composition root: data fetching, polling, and shared state
components/           Header, WatchlistPanel, MainChart, PortfolioHeatmap, PnlChart,
                      PositionsTable, TradeBar, ChatPanel, Sparkline
lib/api.ts            REST client (the only place endpoints are named)
lib/usePriceStream.ts EventSource subscription + bounded per-ticker history
lib/portfolio.ts      Re-prices server positions against the live price cache
lib/format.ts         Currency / percent / clock formatting
tests/                Vitest + React Testing Library
```

Charts use **Recharts**; watchlist sparklines are hand-rolled inline SVG because one renders per row and
updates twice a second.

Sparkline and main-chart history is accumulated client-side from the SSE stream since page load — nothing
historical is fetched — and each ticker's buffer is capped at `MAX_HISTORY_POINTS`. Chat history is
session-only: it is never reloaded from the server after a refresh.
