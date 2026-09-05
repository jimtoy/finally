# PLAN Review

## Summary

The product scope and user experience are clear, and the simulator-first decision makes the core demo achievable. Before implementation, resolve the contracts and contradictions below; they otherwise create avoidable integration and test failures.

## Blocking / high-priority items

1. **Docker persistence description conflicts.** Section 4 says the target is a named volume at `/app/db`, while Section 11 says the repository `db/` directory maps to `/app/db`. The provided `docker run` example uses a named volume. Choose the named-volume design, remove the bind-mount claim, and specify the image/container name, container name, and how the start scripts handle an existing container.
ANSWER: agree used named volume

2. **The price model cannot currently provide “daily change %.”** The cache only defines latest and previous-tick prices. Add a session/open reference price (or explicitly relabel the UI metric as interval change) and define when it resets. Also define how a new simulated ticker gets an initial price before its first update.
ANSWER: agree with suggestions, add to implmentation

3. **Trade execution needs an atomic transaction contract.** Define a single transaction that reads the current cached price, validates cash/holdings, updates cash and position, appends the trade, and writes the immediate snapshot. Specify rounding/precision (prefer integer money units or `Decimal`, not SQLite `REAL` for cash/cost), ticker normalization, position deletion at zero, and an explicit behavior for a price unavailable from the cache.
ANSWER: use money units


5. **Chat persistence is incomplete.** The UI needs existing conversation after reload, but no `GET /api/chat` endpoint exists. Add it (with ordering and pagination/limit), or state that chat is deliberately session-only and should not be reloaded. Define the returned action-confirmation format as well.
ANSWER: limit chat to session only

6. **The LLM action protocol has gaps.** The example “buy $500 of AAPL” is not representable by the stated `quantity`-only schema. Either keep shares-only LLM orders or add a mutually exclusive notional field and deterministic conversion rules. Define maximum actions, duplicate/conflicting actions, execution ordering, malformed/unknown fields, LLM timeout/provider failure, and what happens when the corrective second call fails. Ensure only successfully executed actions are persisted and returned.
ANSWER:  keep shares-only LLM orders.  as this is a poc use sensible defaults

## Important consistency and delivery concerns

- The testing plan still requires Massive parsing and both provider implementations, even though Massive is explicitly out of scope. Remove those tests or move them to the future enhancement acceptance criteria.
ANSWER: MASSIVE is optional, flag that.  It will not be implemented as part of this demo
- Define simulator lifecycle and deterministic controls: seeded RNG configuration for tests, update task startup/shutdown, event bounds/no-negative-price guarantees, and safe broadcast behavior for slow/disconnected SSE clients. SSE should send an initial full snapshot so a newly connected client renders immediately.
ANSWER: I will accept sensible defaults for this based on real world scenarios 
- 
- Clarify multi-client semantics. The app is presently a shared hardcoded `default` user, so every browser shares cash, portfolio, watchlist, chat, and simulator. That is acceptable for a local demo but should be stated prominently, especially since the plan mentions multi-user readiness.
  ANSWER: this is a local demo only
- Add an initial portfolio snapshot during seeding/startup and specify retention/downsampling for periodic snapshots, otherwise the P&L chart has no baseline and the table grows indefinitely.
  ANSWER: seeding can be fake data based on real word scenarios
- The FastAPI static-file setup needs SPA fallback behavior and API-route precedence documented. A Next static export with browser navigation to a client-side route otherwise risks a 404; alternatively keep the app strictly at `/`.
 ANSWER: define a fallback with error trapping to defined error landing location
 

- Define behavior when `.env` or `OPENROUTER_API_KEY` is absent: the rest of the workstation should start, while chat returns a clear capability/error state. Do not make local development depend on a secret when mock mode is available.
  ANSWER: spec a mock harness if .env doesnt exist 

- Include operational acceptance checks: image build succeeds from a clean checkout, container health check, static UI loads, DB survives stop/start, and E2E environment uses an isolated disposable named volume.
 ANSWER: spec sensible defaults

## Suggested implementation order

1. Finalize API/SSE/data precision contracts and acceptance criteria.
2. Build backend schema, simulator/cache, portfolio service, and API tests.
3. Build the frontend against mock fixtures, then connect it to the agreed API/SSE contract.
4. Add LLM mock and real-provider adapter with failure handling.
5. Add Docker/scripts and run the isolated E2E suite against the container.

## Smaller edits

- State a single canonical DB path (`/app/db/finally.db`) and correspond it to the named volume.
- The plan says initialization happens “on startup (or first request)” and “lazily initializes on first request”; choose one lifecycle.
- Give `ticker`, quantity, and timestamp constraints/formats. Uppercasing and trimming tickers at all boundaries will avoid duplicate symbols.
- Specify whether deleting a watchlist ticker that is held is idempotent and whether it remains visible somewhere outside Positions.
- `docker-compose.yml` is described as optional while the test compose file is required; identify their intended commands and ownership.
