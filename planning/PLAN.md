# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `/app/db/finally.db` in a named Docker volume for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → OpenRouter directly, with structured outputs for trade execution
- **Market data**: Built-in simulator only for this build; real data via Massive API is an out-of-scope future enhancement behind the same interface

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Optional convenience wrapper
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend initializes the database during application startup — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is a tracked placeholder only; it is not mounted by the application. The target state (see §11) mounts a named Docker volume (`finally-data`) at `/app/db` in the container. The backend creates `/app/db/finally.db` there, and it persists across container restarts.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# Out of scope for this build — the simulator is the only supported source.
# Reserved for a future, separate enhancement.
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- The built-in market simulator is always used for this build; `MASSIVE_API_KEY` is reserved for a future enhancement and has no effect yet
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- The backend reads `.env` from the project root when present (or receives it through Docker `--env-file`)
- If `LLM_MOCK` is not enabled and `OPENROUTER_API_KEY` is absent, the workstation still starts; chat reports that AI chat is unavailable and gives an actionable configuration message

---

## 6. Market Data

### One Interface, Simulator-Only for Now

Market data is accessed through an abstract interface so downstream code (SSE streaming, price cache, frontend) is agnostic to the source. For this build, the simulator is the only implementation; a Massive client could be added later behind the same interface without touching downstream code (see below).

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Initializes an added ticker with a deterministic plausible price before it is exposed to trades or SSE clients
- Maintains an opening/session price for each ticker so the UI's daily change percentage is `(latest - opening) / opening`; it resets when the simulator process starts
- Runs as an in-process background task — no external dependencies. It starts and stops with the FastAPI lifecycle, uses a configurable seeded RNG in tests, and clamps prices to positive values

### Massive API (Out of Scope for This Build)

Massive integration is **not implemented as part of this core build** — it is an optional, separate future enhancement. The simulator is the only market data source for this project. The abstract interface should still allow a Massive implementation to be dropped in later without touching downstream code, but building/wiring it up is out of scope for now. The notes below describe the intended shape if/when it is implemented:

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Ticker Validation

Since only the simulator is in scope, any ticker symbol added to the watchlist (manually or via the AI chat) is accepted — the simulator synthesizes a plausible price series for it as if it were a real (fake) company. No symbol whitelist/lookup is required. Tickers are trimmed and normalized to uppercase at every API and LLM boundary.

### Shared Price Cache

- A single background task (the simulator) writes to an in-memory price cache
- The cache holds the latest price, previous price, opening/session price, and timestamp for each ticker
- The cache covers the **union of the watchlist and any ticker with an open position** — a ticker removed from the watchlist while still held keeps receiving price updates so the positions table and heatmap can compute current price/unrealized P&L
- SSE streams read from this cache and push updates to connected clients. Each client receives an initial full snapshot on connection, and slow/disconnected clients are cleaned up rather than allowed to block the simulator
- This is a local, single-user demo: every browser instance shares the hardcoded `default` user's portfolio and watchlist. The schema's `user_id` field is only future-proofing, not a current multi-user feature

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- Server pushes price updates at a regular cadence (~500ms) for every ticker in the shared price cache — i.e., the union of the watchlist and any held position, not just the watchlist alone
- Each `price` event contains ticker, price, previous price, opening price, timestamp, and change direction; the initial `snapshot` event contains the same fields for all cached tickers
- Client handles reconnection automatically (EventSource has built-in retry), updates the connection indicator, replaces cached values from the next snapshot, and keeps bounded history buffers for charts/sparklines

---

## 7. Database

### SQLite Initialization

The backend checks for the SQLite database during application startup. If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance_cents` INTEGER (default: `1000000`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost_cents` INTEGER (weighted-average cost per share, rounded to cents)
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price_cents` INTEGER
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). An initial snapshot is recorded at seed/startup, then every 30 seconds by a background task and immediately after each trade execution. Test/demo data may use realistic synthetic historical points when needed to make the chart meaningful on first launch.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value_cents` INTEGER
- `recorded_at` TEXT (ISO timestamp)

Snapshots older than 24 hours are downsampled to one point per five minutes; the most recent 24 hours retain the 30-second cadence. History responses are ordered ascending by `recorded_at` and default to the most recent 24 hours.

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — trades executed, watchlist changes made; null for user messages)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One user profile: `id="default"`, `cash_balance_cents=1000000` ($10,000.00)
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

### Trade Execution Rules

- Quantities are strictly positive. The manual trade bar sends whole-share quantities; LLM orders may use fractional shares.
- Each order executes at the single current cache price. If no current price exists, the order is rejected with a validation error.
- Trade execution is atomic: one database transaction validates cash or holdings, updates cash and the position, appends the trade, and creates the immediate portfolio snapshot. A zero-quantity position is removed.
- API responses display money in decimal dollars but persistence and calculations use integer cents. Fractional-share cost calculations use a documented, consistent rounding rule.

---

## 8. API Endpoints

All JSON errors use `{"detail": "human-readable message", "code": "stable_error_code"}`. Invalid request bodies return `422`; invalid business operations (such as insufficient funds, unavailable price, or overselling) return `400`; missing resources return `404`; and unexpected/provider failures return `502` for chat or `500` otherwise. All successful mutations return their resulting resource state.

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream. Sends a `snapshot` event immediately, then `price` events; price payloads contain `ticker`, `price`, `previous_price`, `opening_price`, `timestamp`, and `direction`. |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Returns `{cash_balance, total_value, unrealized_pnl, positions}`; every position includes ticker, quantity, average_cost, current_price, unrealized_pnl, and percent_change. |
| POST | `/api/portfolio/trade` | Execute `{ticker, quantity, side}`. `quantity` must be strictly positive; returns the executed trade (including id and price) plus the updated portfolio. |
| GET | `/api/portfolio/history` | Returns ascending `{recorded_at, total_value}` snapshots for the P&L chart. |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Returns current watchlist entries with their latest price and daily/session change. |
| POST | `/api/watchlist` | Add `{ticker}`; returns `201` when added and `200` with the existing entry when already watched. |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker; idempotently returns `204` whether or not it was present. Held tickers remain priced and visible in Positions. |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send `{message}` and receive `{message, executed_actions}`. Each action confirmation includes its type, normalized ticker, success state, and resulting trade/watchlist data. |

Chat is session-only in the UI: the frontend does not reload prior messages after a page refresh. The database log remains available to the backend solely for the one-message conversational context described below.

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment). Returns JSON reporting both app health and DB health, e.g. `{"app": "ok", "db": "ok"}` |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use LiteLLM via OpenRouter directly to the `openrouter/openai/gpt-oss-120b` model. Structured Outputs should be used to interpret the results.

When an `OPENROUTER_API_KEY` is available, the backend uses it from `.env` or the container environment. When it is unavailable, `LLM_MOCK=true` remains a supported development/test harness; otherwise chat returns its configured-unavailable response without affecting the rest of the app.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads the most recent message from the `chat_messages` table (this demo only carries one prior message of history, not the full conversation)
3. Constructs a prompt with a system message, portfolio context, prior message, and the user's new message
4. Calls the LLM via LiteLLM → OpenRouter, requesting structured output
5. Parses the complete structured JSON response
6. Auto-executes at most 10 actions in response order using the same validations as manual actions. Unknown fields are rejected by structured-output validation; duplicate/conflicting actions are reported as validation failures and are not retried. Tickers are normalized, and failed actions have no retry. If an action fails validation, its error is **not** persisted to `chat_messages` — it is kept in the in-request context and fed back into one corrective LLM call so the model can revise its `message` to inform the user without retrying the failed action. If that call fails, the backend returns a concise fallback message with the validation error.
7. Stores the (final) message and executed actions in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming — inference is fast enough that a loading indicator is sufficient)

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of share-quantity trades to auto-execute. Notional/dollar orders are intentionally unsupported in this PoC. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

If a trade fails validation (e.g., insufficient cash, non-positive quantity), the error is not stored — it is fed back into a single corrective LLM call (see §9 "How It Works", step 6) so the model can inform the user in its response. Provider timeouts, malformed structured output, and a failed corrective call return a clear fallback assistant message; successfully executed actions remain reported.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), daily change %, and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill. The manual trade bar takes whole-share quantities; fractional shares are primarily an LLM-driven capability. Dollar/notional orders are not supported.
- **AI chat panel** — docked/collapsible sidebar. Message input, session-only scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves API routes before static files on port 8000. It serves the static export's index as a safe fallback for frontend navigation; missing/static errors are trapped and routed to a defined error landing view rather than exposing a server error.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

The project-root `db/` directory is not mounted. The backend writes `finally.db` to the named volume at `/app/db/finally.db`.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Uses a fixed documented image/container name, starts an existing stopped container when appropriate, and replaces only that named container when a rebuild is requested
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

`docker-compose.yml` is an optional local convenience wrapper for the same app and named volume. `test/docker-compose.test.yml` is the required isolated test harness; it owns the disposable test volume and launches the Playwright container.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

**Note:** this project is for demo purposes only and is not intended to go to production in its current state — there is no auth and trades execute with zero confirmation, so any cloud deployment should be treated as a personal/demo instance, not something shared publicly.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid positive prices, GBM math is correct, deterministic seed behavior works, and SSE sends an initial snapshot
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism, use a seeded simulator, and use an isolated disposable named volume.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection
- Operational smoke checks: clean image build, healthy container, static UI load, and database persistence across an app stop/start
