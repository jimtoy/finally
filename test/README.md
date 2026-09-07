# FinAlly E2E Tests

Playwright test suite covering PLAN.md §12 "E2E Tests". Runs against the real
production Docker image (built from the repo root `Dockerfile`) plus a
separate Playwright container, so browser dependencies never end up in the
app image.

## Layout

- `docker-compose.test.yml` — isolated test harness: the `app` service (built
  from `..`, `LLM_MOCK=true`, a disposable `finally-test-data` volume) and a
  `playwright` service that runs the suite against it over the docker network
  (`http://app:8000`).
- `e2e/` — the Playwright project (`package.json`, `playwright.config.ts`,
  `tests/*.spec.ts`, `Dockerfile` for the runner image).

## Running locally

```bash
docker compose -f test/docker-compose.test.yml up --build -d app
docker compose -f test/docker-compose.test.yml run --rm --build playwright
status=$?
docker compose -f test/docker-compose.test.yml down -v
exit $status
```

Deliberately **not** `up --abort-on-container-exit`: the database-persistence
test (`07-persistence.spec.ts`) restarts the `app` service mid-run, and
`--abort-on-container-exit` tears down the whole stack (including the still-
running `playwright` container) the instant any container exits — even for
an intentional restart. `run --rm` runs the test container to completion and
hands back its real exit code regardless of what happens to `app` along the
way. `down -v` removes the disposable `finally-test-data` volume so the next
run starts from a clean seeded database.

A Playwright HTML report and trace/screenshot artifacts on failure are
written to `test/e2e/playwright-report/` and `test/e2e/test-results/` on the
host (bind-mounted from the container).

### Running the tests outside Docker (fastest local iteration)

You need Node 18+ and a running app on some port:

```bash
cd test/e2e
npm install
npx playwright install --with-deps chromium
PLAYWRIGHT_BASE_URL=http://localhost:8000 npx playwright test
```

Note: the database-persistence test (`07-persistence.spec.ts`) needs
`RESTART_CMD` set to something that restarts the app under test (e.g.
`docker restart finally-app` if you're running the app via the root
`docker-compose.yml`). Without it, that one test is skipped rather than
failing.

## In CI

Run the same commands used locally:

```yaml
- name: E2E tests
  run: |
    docker compose -f test/docker-compose.test.yml up --build -d app
    docker compose -f test/docker-compose.test.yml run --rm playwright
    status=$?
    docker compose -f test/docker-compose.test.yml down -v
    exit $status
- name: Upload Playwright report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: playwright-report
    path: test/e2e/playwright-report/
```

The suite requires the CI runner to expose the docker socket to containers it
starts (true for GitHub-hosted runners) — that's what lets the persistence
test restart the `app` service from inside the `playwright` container. If
your CI environment doesn't allow socket access, unset `RESTART_CMD` in
`docker-compose.test.yml`; that one test will skip instead of failing.

## Test order and shared state

There's a single `default` user and no per-test database reset, so the spec
files are numbered (`01-...` through `07-...`) and run sequentially
(`workers: 1`, `fullyParallel: false`) — each one either cleans up after
itself (watchlist add/remove) or leaves state the next file expects (the
trading test buys then fully sells AAPL; the visualization test buys GOOGL
and leaves it open for the heatmap/P&L chart; the chat test buys MSFT via the
mock grammar). The persistence test runs last because it restarts the shared
app container.

## Determinism

The market simulator (`backend/app/market/simulator.py`) has no seed
override — it's `numpy`/`random` driven with no way to inject a fixed seed
via environment variable. Tests that depend on price movement (fresh-start
streaming check) don't assert exact values; they watch several volatile
tickers and pass as soon as any one of them visibly changes. Everything else
either uses the deterministic mock chat grammar (`LLM_MOCK=true`) or asserts
on portfolio/position state that trade execution controls exactly (cash
deltas, position presence), not on simulated price values.
