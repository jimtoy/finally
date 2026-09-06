# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course.

## Status

Under active development. Only the **market data simulator** is complete (see `planning/MARKET_DATA_SUMMARY.md`). The API, database, frontend, LLM chat, and Docker packaging described below are still to be built — see `planning/PLAN.md` for the full spec.

## Planned Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — heatmap (treemap), P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture (Target)

Single Docker container serving everything on port 8000:

- **Frontend**: Next.js (static export) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python/uv) with SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM → OpenRouter directly with structured outputs
- **Market data**: Built-in GBM simulator (done); Massive API is an out-of-scope future enhancement

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |

`MASSIVE_API_KEY` is reserved for a future enhancement and currently has no effect — the simulator is the only market data source.

## Project Structure

```
finally/
├── backend/     # FastAPI uv project (market data simulator implemented)
└── planning/    # Project documentation and agent contracts
```

`frontend/`, `test/`, `scripts/`, and Docker packaging do not exist yet.

## License

See [LICENSE](LICENSE).
