# Market Data Backend — Detailed Design

Implementation-ready design for the FinAlly market data subsystem, aligned with the current `planning/PLAN.md` (§6, §8, §14). Covers the unified `MarketDataSource` interface, the thread-safe price cache, the GBM simulator, the SSE streaming endpoint, and FastAPI lifecycle wiring.

Everything below lives under `backend/app/market/`.

**Relationship to prior work**: `backend/app/market/` already exists and is summarized as complete in `planning/MARKET_DATA_SUMMARY.md`, with an earlier design in `planning/archive/MARKET_DATA_DESIGN.md`. This document is not a rewrite from scratch — it re-specifies the same architecture but closes one real gap between the shipped code and the current PLAN.md: **session/opening price is not implemented today**, and PLAN.md requires it (§6, §8). Section 15 spells out exactly what changes versus the code as it stands; everything else here matches the existing implementation and is included for completeness so this is a single, self-contained reference.

---

## Table of Contents

1. [File Structure](#1-file-structure)
2. [Data Model — `models.py`](#2-data-model)
3. [Price Cache — `cache.py`](#3-price-cache)
4. [Abstract Interface — `interface.py`](#4-abstract-interface)
5. [Seed Prices & Ticker Parameters — `seed_prices.py`](#5-seed-prices--ticker-parameters)
6. [GBM Simulator — `simulator.py`](#6-gbm-simulator)
7. [Massive API — Interface-Compatible, Out of Scope](#7-massive-api--interface-compatible-out-of-scope)
8. [Factory — `factory.py`](#8-factory)
9. [SSE Streaming Endpoint — `stream.py`](#9-sse-streaming-endpoint)
10. [FastAPI Lifecycle Integration](#10-fastapi-lifecycle-integration)
11. [Watchlist Coordination & Ticker Validation](#11-watchlist-coordination--ticker-validation)
12. [Testing Strategy](#12-testing-strategy)
13. [Error Handling & Edge Cases](#13-error-handling--edge-cases)
14. [Configuration Summary](#14-configuration-summary)
15. [Delta vs. the Existing Implementation](#15-delta-vs-the-existing-implementation)

---

## 1. File Structure

```
backend/
  app/
    market/
      __init__.py             # Re-exports: PriceUpdate, PriceCache, MarketDataSource, create_market_data_source, create_stream_router
      models.py                # PriceUpdate dataclass
      cache.py                 # PriceCache (thread-safe in-memory store)
      interface.py              # MarketDataSource ABC
      seed_prices.py             # SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS, CORRELATION_GROUPS
      simulator.py               # GBMSimulator + SimulatorDataSource
      massive_client.py           # MassiveDataSource (reserved, not wired by default — see §7)
      factory.py                  # create_market_data_source()
      stream.py                    # SSE endpoint (FastAPI router)
```

Each file has a single responsibility. `__init__.py` re-exports the public API so the rest of the backend imports from `app.market` without reaching into submodules.

---

## 2. Data Model

**File: `backend/app/market/models.py`**

`PriceUpdate` is the only data structure that leaves the market data layer. Every downstream consumer — SSE streaming, watchlist responses, portfolio valuation, trade execution — works exclusively with this type.

Per PLAN.md §6/§8, every price carries **two** notions of change:

- **Tick change** (`change`, `change_percent`, `direction`) — vs. the previous update, for the watchlist's per-update flash animation.
- **Session change** (`session_change`, `session_change_percent`) — vs. the ticker's opening price for this simulator run, for the daily % shown next to each ticker. PLAN.md: *"the UI's daily change percentage is `(latest - opening) / opening`; it resets when the simulator process starts."*

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    opening_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute tick-over-tick price change."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Tick-over-tick percentage change."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def session_change(self) -> float:
        """Absolute change from the session/opening price."""
        return round(self.price - self.opening_price, 4)

    @property
    def session_change_percent(self) -> float:
        """Daily/session percentage change: (latest - opening) / opening."""
        if self.opening_price == 0:
            return 0.0
        return round((self.price - self.opening_price) / self.opening_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat', relative to the previous tick."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission. Matches the PLAN.md §6 SSE payload."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "opening_price": self.opening_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "session_change": self.session_change,
            "session_change_percent": self.session_change_percent,
            "direction": self.direction,
        }
```

### Design decisions

- **`frozen=True, slots=True`**: immutable, low-overhead value objects — many are created per second across all tickers.
- **Computed properties**: `change`/`direction`/`session_change_percent` are derived from stored fields, so they can never drift out of sync with `price`, `previous_price`, and `opening_price`.
- **`opening_price` is a stored field, not derived** — it must persist across many `PriceUpdate` instances for the same ticker (each update replaces the previous one in the cache), so it has to be threaded through by whoever constructs the next `PriceUpdate`. That's `PriceCache.update()` (§3).
- **`to_dict()`** is the single serialization point used by the SSE endpoint and any REST route that echoes a live price.

---

## 3. Price Cache

**File: `backend/app/market/cache.py`**

The price cache is the central hub: data sources write to it, everything else reads from it. It must be thread-safe because a future poll-based source (Massive) would run its synchronous HTTP call via `asyncio.to_thread`, a real OS thread, while SSE reads happen on the event loop.

The cache — not the simulator or any data source — owns opening-price bookkeeping. This keeps "what is today's open" a cache concern (state about a ticker's lifetime in the cache) rather than a simulator concern (state about a random walk), and it means the rule applies uniformly to any current or future `MarketDataSource` implementation without each one re-implementing it.

```python
from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource (or a future MassiveDataSource) — one at a time.
    Readers: SSE streaming endpoint, watchlist/portfolio routes, trade execution.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker. Returns the created PriceUpdate.

        Automatically computes direction/change from the previous price. The
        *first* update a ticker ever receives in this cache's lifetime fixes
        its `opening_price` for as long as the ticker stays in the cache —
        every later call carries that same opening_price forward. This is
        what gives "opening price" its two required behaviors from PLAN.md:

        - It resets whenever the process restarts (a fresh PriceCache has no
          history, so the first tick of the new run becomes the new open).
        - It resets when a ticker is re-added after being removed (`remove()`
          drops the cache entry, so the next `update()` is treated as a first
          update again and re-seeds the opening price).
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price
            opening_price = prev.opening_price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                opening_price=round(opening_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest price for a single ticker, or None if unknown."""
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: get just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def get_opening_price(self, ticker: str) -> float | None:
        """Convenience: get just the session opening price, or None."""
        update = self.get(ticker)
        return update.opening_price if update else None

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (e.g., when removed from watchlist
        with no open position — see §11). The next update() for this ticker
        will be treated as a fresh session and set a new opening price.
        """
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Current version counter. Used for SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

### Why a version counter?

The SSE loop polls the cache every ~500ms. Without a version counter it would re-serialize and resend every price on every tick even when nothing changed (irrelevant for the simulator, which always changes something, but essential once a slower poll-based source exists). The SSE loop skips sends when nothing is new:

```python
last_version = -1
while True:
    if price_cache.version != last_version:
        last_version = price_cache.version
        yield format_sse(price_cache.get_all())
    await asyncio.sleep(0.5)
```

### Thread safety rationale

`threading.Lock` (not `asyncio.Lock`) is used because a future synchronous poller would run via `asyncio.to_thread()`, which executes in a real OS thread — `asyncio.Lock` would not protect against that. `threading.Lock` works correctly from both sync threads and the async event loop, and the critical section (dict read/write) is small enough that contention is a non-issue at this scale (10–50 tickers, sub-millisecond hold time).

### Why opening price lives in the cache, not the simulator

An alternative design would have `GBMSimulator` track its own "day 1 price" per ticker and pass it to `cache.update()`. That's strictly more code for the same result, and it would need re-deriving for a future Massive source (which has its own, better notion of "opening" — the exchange's actual previous close, see §7). Deriving it once, in the cache, from "first write this ticker has ever received" keeps the rule source-agnostic and gives every current and future `MarketDataSource` the same semantics for free — no changes needed to `simulator.py` or a future `massive_client.py` beyond calling `cache.update(ticker, price)` as they already do.

---

## 4. Abstract Interface

**File: `backend/app/market/interface.py`**

Unchanged from the existing implementation — no opening-price plumbing is needed here since the cache derives it from the update stream.

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never calls the data source directly for prices —
    it reads from the cache.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        # ... app runs ...
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        # ... app shutting down ...
        await source.stop()
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.

        Starts a background task that periodically writes to the PriceCache.
        Must be called exactly once. Calling start() twice is undefined behavior.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources.

        Safe to call multiple times. After stop(), the source will not write
        to the cache again.
        """

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present.

        The next update cycle will include this ticker, seeded with an
        immediate price (see §6) so it never appears priceless to a client.
        """

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set. No-op if not present.

        Also removes the ticker from the PriceCache.
        """

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of actively tracked tickers."""
```

### Why the source writes to the cache instead of returning prices

This push model decouples timing. The simulator ticks at 500ms; a future poll-based source might poll every 15s; SSE always reads from the cache at its own 500ms cadence regardless of which source is active. The SSE layer never needs to know the active source's update interval.

---

## 5. Seed Prices & Ticker Parameters

**File: `backend/app/market/seed_prices.py`**

Constants only — no logic, no imports beyond stdlib.

```python
"""Seed prices and per-ticker parameters for the market simulator."""

# Realistic starting prices for the default watchlist (as of project creation)
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
    "META": 500.00,
    "JPM": 195.00,
    "V": 280.00,
    "NFLX": 600.00,
}

# Per-ticker GBM parameters
# sigma: annualized volatility (higher = more price movement)
# mu: annualized drift / expected return
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},   # High volatility
    "NVDA":  {"sigma": 0.40, "mu": 0.08},   # High volatility, strong drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},   # Low volatility (bank)
    "V":     {"sigma": 0.17, "mu": 0.04},   # Low volatility (payments)
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

# Default parameters for tickers not in the list above (dynamically added)
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

# Correlation groups for the simulator's Cholesky decomposition
# Tickers in the same group have higher intra-group correlation
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

# Correlation coefficients
INTRA_TECH_CORR = 0.6       # Tech stocks move together
INTRA_FINANCE_CORR = 0.5    # Finance stocks move together
CROSS_GROUP_CORR = 0.3      # Between sectors / unknown tickers
TSLA_CORR = 0.3             # TSLA does its own thing
```

Ticker validation per PLAN.md §6: any symbol is accepted. A ticker not in `SEED_PRICES`/`TICKER_PARAMS` gets a random seed price in `[50, 300]` and `DEFAULT_PARAMS` (see `GBMSimulator._add_ticker_internal` in §6) — the simulator synthesizes a plausible series for it "as if it were a real (fake) company." Callers normalize tickers to uppercase, trimmed, before they ever reach this layer (§11).

---

## 6. GBM Simulator

**File: `backend/app/market/simulator.py`**

Two classes:
- `GBMSimulator`: pure math engine. Stateful — holds current prices, advances one step at a time. **Unchanged by the opening-price work** — it has no notion of "opening price" at all; that's entirely a cache concern (§3).
- `SimulatorDataSource`: the `MarketDataSource` implementation that wraps `GBMSimulator` in an async loop and writes to the `PriceCache`.

### 6.1 GBMSimulator — The Math Engine

```python
from __future__ import annotations

import asyncio
import logging
import math
import random

import numpy as np

from .cache import PriceCache
from .interface import MarketDataSource
from .seed_prices import (
    CORRELATION_GROUPS,
    CROSS_GROUP_CORR,
    DEFAULT_PARAMS,
    INTRA_FINANCE_CORR,
    INTRA_TECH_CORR,
    SEED_PRICES,
    TICKER_PARAMS,
    TSLA_CORR,
)

logger = logging.getLogger(__name__)


class GBMSimulator:
    """Geometric Brownian Motion simulator for correlated stock prices.

    Math:
        S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)

    Where:
        S(t)   = current price
        mu     = annualized drift (expected return)
        sigma  = annualized volatility
        dt     = time step as fraction of a trading year
        Z      = correlated standard normal random variable

    The tiny dt (~8.5e-8 for 500ms ticks over 252 trading days * 6.5h/day)
    produces sub-cent moves per tick that accumulate naturally over time.
    """

    # 500ms expressed as a fraction of a trading year
    # 252 trading days * 6.5 hours/day * 3600 seconds/hour = 5,896,800 seconds
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability

        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    # --- Public API ---

    def step(self) -> dict[str, float]:
        """Advance all tickers by one time step. Returns {ticker: new_price}.

        This is the hot path — called every 500ms. Keep it fast.
        """
        n = len(self._tickers)
        if n == 0:
            return {}

        z_independent = np.random.standard_normal(n)
        z_correlated = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            params = self._params[ticker]
            mu = params["mu"]
            sigma = params["sigma"]

            drift = (mu - 0.5 * sigma ** 2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # Random event: ~0.1% chance per tick per ticker
            if random.random() < self._event_prob:
                shock_magnitude = random.uniform(0.02, 0.05)
                shock_sign = random.choice([-1, 1])
                self._prices[ticker] *= 1 + shock_magnitude * shock_sign
                logger.debug(
                    "Random event on %s: %.1f%% %s",
                    ticker, shock_magnitude * 100, "up" if shock_sign > 0 else "down",
                )

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the simulation. Rebuilds the correlation matrix."""
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the simulation. Rebuilds the correlation matrix."""
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        """Current price for a ticker, or None if not tracked."""
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        """Return the list of currently tracked tickers."""
        return list(self._tickers)

    # --- Internals ---

    def _add_ticker_internal(self, ticker: str) -> None:
        """Add a ticker without rebuilding Cholesky (for batch initialization).

        Unknown tickers get a plausible random seed price in [$50, $300] and
        default GBM params — this is what lets any symbol be added to the
        watchlist per PLAN.md §6 ("Ticker Validation") with no whitelist.
        """
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        """Rebuild the Cholesky decomposition of the ticker correlation matrix.

        Called whenever tickers are added or removed. O(n^2) but n < 50.
        """
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return

        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = rho
                corr[j, i] = rho

        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        """Determine correlation between two tickers based on sector grouping."""
        tech = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]

        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

### 6.2 SimulatorDataSource — Async Wrapper

```python
class SimulatorDataSource(MarketDataSource):
    """MarketDataSource backed by the GBM simulator.

    Runs a background asyncio task that calls GBMSimulator.step() every
    `update_interval` seconds and writes results to the PriceCache.
    """

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)
        # Seed the cache with initial prices immediately. This is also the
        # moment each ticker's opening_price is fixed for the run (§3) —
        # PriceCache.update() treats a ticker's first-ever write as its open.
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
        logger.info("Simulator started with %d tickers", len(tickers))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Simulator stopped")

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            # Seed cache immediately — this also fixes the new ticker's
            # opening_price at the price it was added with.
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
            logger.info("Simulator: added ticker %s", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)
        logger.info("Simulator: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        """Core loop: step the simulation, write to cache, sleep."""
        while True:
            try:
                if self._sim:
                    prices = self._sim.step()
                    for ticker, price in prices.items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

### Key behaviors

- **Immediate seeding**: `start()` populates the cache with seed prices *before* the loop begins, so the SSE endpoint has data on its very first tick — no blank-screen delay, and every ticker's `opening_price` is correctly set from that first write.
- **Graceful cancellation**: `stop()` cancels the task and awaits it, catching `CancelledError`, for clean shutdown during FastAPI lifespan teardown.
- **Exception resilience**: the loop catches exceptions per-step so a single bad tick doesn't kill the entire feed.
- **Reset semantics come for free**: because opening price is derived by the cache from "first write for this ticker," a full process restart (fresh `PriceCache`) or an add-after-remove cycle both produce the correct reset behavior with zero extra code in this file.

---

## 7. Massive API — Interface-Compatible, Out of Scope

Per PLAN.md §3/§6, real market data via Massive (Polygon.io) is **explicitly out of scope for this build**. The simulator is the only market data source that ships. This section exists so a future contributor knows where the seam is and doesn't need to touch anything in §1–§6 to add it later.

- The `MarketDataSource` ABC (§4) is source-agnostic by design — `start`/`stop`/`add_ticker`/`remove_ticker`/`get_tickers`, all pushing into the same `PriceCache`. A `MassiveDataSource` implementing that same contract can be dropped in without changing `cache.py`, `stream.py`, or any downstream route.
- `backend/app/market/massive_client.py` already contains a working REST-polling implementation from earlier work (see `planning/archive/MASSIVE_API.md` for the Massive API reference and `planning/archive/MARKET_DATA_DESIGN.md` §7 for the full client code) — it polls `get_snapshot_all()` on an interval and writes `snap.last_trade.price` into the cache via `to_thread`.
- **One adjustment that implementation would need** to satisfy PLAN.md's opening-price requirement precisely: Massive's snapshot response includes `day.previous_close`, which is the *real* session open — better than "first write this process happened to see." A future `MassiveDataSource` should seed the cache's opening price from `day.previous_close` on its first poll for a ticker rather than relying on `PriceCache`'s generic "first write wins" rule. That's a small, source-specific addition (e.g., a `cache.set_opening(ticker, price)` method) and does not require changing the generic `update()` behavior the simulator relies on.
- The factory (§8) already treats `MASSIVE_API_KEY` as the switch — wiring it up for real is future work, not part of this build.

No code changes to this file are proposed as part of this design; it is scoped out.

---

## 8. Factory

**File: `backend/app/market/factory.py`**

```python
from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Create the appropriate market data source based on environment variables.

    - MASSIVE_API_KEY set and non-empty -> MassiveDataSource (reserved; not part
      of this build's supported path, see §7)
    - Otherwise -> SimulatorDataSource (the only source this build ships)

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

### Usage at app startup

```python
price_cache = PriceCache()
source = create_market_data_source(price_cache)
await source.start(initial_tickers)  # e.g., ["AAPL", "GOOGL", ...]
```

---

## 9. SSE Streaming Endpoint

**File: `backend/app/market/stream.py`**

Unchanged from the existing implementation — `to_dict()` already carries whatever fields `PriceUpdate` defines, so adding `opening_price`/`session_change`/`session_change_percent` in §2 flows through automatically with no edits here.

```python
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create the SSE streaming router with a reference to the price cache."""

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        """SSE endpoint for live price updates.

        Sends a full snapshot immediately on connect, then incremental
        updates whenever the cache version changes (~500ms cadence).
        """
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted price events.

    Sends all prices every `interval` seconds when the cache has changed.
    Stops when the client disconnects (detected via request.is_disconnected()).
    """
    yield "retry: 1000\n\n"

    last_version = -1
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            current_version = price_cache.version
            if current_version != last_version:
                last_version = current_version
                prices = price_cache.get_all()

                if prices:
                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
                    yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
```

PLAN.md §6 distinguishes an initial `snapshot` event from subsequent `price` events. The route above sends one combined payload per tick containing every cached ticker, which satisfies "sends a `snapshot` event immediately, then `price` events" functionally (first send = snapshot of everything, later sends = the current state again, filtered by the version check to avoid redundant work) without requiring the client to reconcile two different event shapes. If the frontend needs the two event *names* (`event: snapshot` / `event: price`) to differ literally on the wire, add an `event:` line keyed off whether this is the connection's first send:

```python
    first_send = True
    ...
    if current_version != last_version:
        ...
        if prices:
            event_name = "snapshot" if first_send else "price"
            yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
            first_send = False
```

### Wire format

```
event: snapshot
data: {"AAPL":{"ticker":"AAPL","price":190.50,"previous_price":190.42,"opening_price":190.00,"timestamp":1707580800.5,"change":0.08,"change_percent":0.042,"session_change":0.50,"session_change_percent":0.263,"direction":"up"},"GOOGL":{...}}

event: price
data: {"AAPL":{...},"GOOGL":{...}}

```

Client:

```javascript
const eventSource = new EventSource('/api/stream/prices');
eventSource.onmessage = (event) => {
    const prices = JSON.parse(event.data); // { "AAPL": { ticker, price, opening_price, ... }, ... }
};
```

### Why poll-and-push instead of event-driven

The endpoint polls the cache on a fixed interval rather than being notified by the data source. This produces predictable, evenly-spaced updates, which matters for the frontend's sparkline accumulation (PLAN.md §2/§10) — regular spacing keeps the charts visually clean regardless of which source is active underneath.

---

## 10. FastAPI Lifecycle Integration

The market data system starts and stops with the FastAPI application via the `lifespan` context manager.

**In `backend/app/main.py`:**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.interface import MarketDataSource
from app.market.stream import create_stream_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of background services."""

    # --- STARTUP ---
    price_cache = PriceCache()
    app.state.price_cache = price_cache

    source = create_market_data_source(price_cache)
    app.state.market_source = source

    initial_tickers = await load_watchlist_tickers()  # union of watchlist + open positions, from SQLite
    await source.start(initial_tickers)

    stream_router = create_stream_router(price_cache)
    app.include_router(stream_router)

    yield  # App is running

    # --- SHUTDOWN ---
    await source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)


def get_price_cache() -> PriceCache:
    return app.state.price_cache


def get_market_source() -> MarketDataSource:
    return app.state.market_source
```

### Accessing market data from other routes

```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api")


@router.post("/portfolio/trade")
async def execute_trade(
    trade: TradeRequest,
    price_cache: PriceCache = Depends(get_price_cache),
):
    current_price = price_cache.get_price(trade.ticker)
    if current_price is None:
        raise HTTPException(400, detail=f"No price available for {trade.ticker}", ...)
    # ... execute trade at current_price ...


@router.get("/watchlist")
async def get_watchlist(price_cache: PriceCache = Depends(get_price_cache)):
    entries = await db.list_watchlist()
    return [
        {
            "ticker": e.ticker,
            "price": (u := price_cache.get(e.ticker)) and u.price,
            "session_change_percent": u and u.session_change_percent,
        }
        for e in entries
    ]


@router.post("/watchlist")
async def add_to_watchlist(
    payload: WatchlistAdd,
    source: MarketDataSource = Depends(get_market_source),
):
    ticker = payload.ticker.strip().upper()
    await db.insert_watchlist_entry(ticker)   # 201 new / 200 already-present per PLAN.md §8
    await source.add_ticker(ticker)           # price available before the response returns
    # ...


@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    source: MarketDataSource = Depends(get_market_source),
):
    ticker = ticker.strip().upper()
    await db.delete_watchlist_entry(ticker)

    # Only stop tracking if there's no open position (see §11)
    position = await db.get_position(ticker)
    if position is None or position.quantity == 0:
        await source.remove_ticker(ticker)

    return Response(status_code=204)
```

---

## 11. Watchlist Coordination & Ticker Validation

### Ticker normalization

Per PLAN.md §6: *"Tickers are trimmed and normalized to uppercase at every API and LLM boundary."* This happens at the route/LLM-action layer (`ticker.strip().upper()`), before `add_ticker`/`remove_ticker`/`get_price` are ever called — the market layer itself treats whatever string it's given as an opaque key and does no normalization of its own. Any symbol is accepted (no whitelist/lookup); the simulator synthesizes a plausible price series for unknown tickers (§6).

### Flow: adding a ticker

```
User (or LLM) -> POST /api/watchlist {ticker: "PYPL"}
  -> normalize to "PYPL"
  -> Insert into watchlist table (SQLite)
  -> await source.add_ticker("PYPL")
       Simulator: adds to GBMSimulator, rebuilds Cholesky, seeds cache
                  (this fixes PYPL's opening_price for the run)
  -> Return success (ticker + current price, now guaranteed available)
```

### Flow: removing a ticker

```
User (or LLM) -> DELETE /api/watchlist/PYPL
  -> Delete from watchlist table (SQLite)
  -> if no open position: await source.remove_ticker("PYPL")
       Simulator: removes from GBMSimulator, rebuilds Cholesky, drops from cache
  -> Return success (204, idempotent)
```

### Edge case: ticker has an open position

Per PLAN.md §6: *"The cache covers the union of the watchlist and any ticker with an open position — a ticker removed from the watchlist while still held keeps receiving price updates so the positions table and heatmap can compute current price/unrealized P&L."* The watchlist route enforces this by checking for an open position before calling `source.remove_ticker()` (shown in §10's `remove_from_watchlist`). This means the *set of tickers the market layer tracks* is not identical to "the watchlist table" — it's `watchlist ∪ {tickers with quantity > 0}`, computed by the caller (backend routes/DB layer), not by anything inside `app/market/`. The market layer only ever sees `add_ticker`/`remove_ticker` calls reflecting that already-computed union; it has no knowledge of positions itself.

At startup, `load_watchlist_tickers()` (§10) must compute this same union so a ticker held from before a restart but no longer on the watchlist still gets priced immediately.

---

## 12. Testing Strategy

### 12.1 GBMSimulator

**File: `backend/tests/market/test_simulator.py`** — unchanged from the existing suite (opening price is not a simulator concept): `step()` returns all tickers, prices stay positive over 10k steps, seed prices match `SEED_PRICES`, add/remove tickers work and are idempotent/no-op on duplicates, unknown tickers get a random seed in `[50, 300]`, Cholesky rebuilds on add (`None` for a single ticker, present for two+).

### 12.2 PriceCache — including the new opening-price behavior

**File: `backend/tests/market/test_cache.py`**

```python
import pytest
from app.market.cache import PriceCache


class TestPriceCache:

    def test_update_and_get(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.ticker == "AAPL"
        assert update.price == 190.50
        assert cache.get("AAPL") == update

    def test_first_update_is_flat_and_sets_opening(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.direction == "flat"
        assert update.previous_price == 190.50
        assert update.opening_price == 190.50
        assert update.session_change_percent == 0.0

    def test_opening_price_persists_across_updates(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)   # opening = 190.00
        cache.update("AAPL", 191.00)
        third = cache.update("AAPL", 189.50)
        assert third.opening_price == 190.00
        assert third.previous_price == 191.00
        assert third.session_change_percent == pytest.approx((189.50 - 190.00) / 190.00 * 100, rel=1e-6)

    def test_direction_up(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 191.00)
        assert update.direction == "up"
        assert update.change == 1.00

    def test_direction_down(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 189.00)
        assert update.direction == "down"
        assert update.change == -1.00

    def test_remove_then_readd_resets_opening_price(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.remove("AAPL")
        update = cache.update("AAPL", 205.00)  # brand-new "session"
        assert update.opening_price == 205.00
        assert update.previous_price == 205.00

    def test_get_all(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)
        assert set(cache.get_all().keys()) == {"AAPL", "GOOGL"}

    def test_version_increments(self):
        cache = PriceCache()
        v0 = cache.version
        cache.update("AAPL", 190.00)
        assert cache.version == v0 + 1

    def test_get_price_and_get_opening_price_convenience(self):
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        cache.update("AAPL", 195.00)
        assert cache.get_price("AAPL") == 195.00
        assert cache.get_opening_price("AAPL") == 190.50
        assert cache.get_price("NOPE") is None
        assert cache.get_opening_price("NOPE") is None
```

### 12.3 Integration: SimulatorDataSource

**File: `backend/tests/market/test_simulator_source.py`**

```python
import asyncio
import pytest
from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource


@pytest.mark.asyncio
class TestSimulatorDataSource:

    async def test_start_populates_cache_with_opening_price(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])

        aapl = cache.get("AAPL")
        assert aapl is not None
        assert aapl.opening_price == aapl.price  # first tick == opening

        await source.stop()

    async def test_prices_update_but_opening_stays_fixed(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
        await source.start(["AAPL"])

        opening = cache.get("AAPL").opening_price
        await asyncio.sleep(0.3)  # several update cycles
        assert cache.get("AAPL").opening_price == opening

        await source.stop()

    async def test_add_ticker_seeds_its_own_opening_price(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])

        await source.add_ticker("TSLA")
        tsla = cache.get("TSLA")
        assert tsla is not None
        assert tsla.opening_price == tsla.price

        await source.stop()

    async def test_remove_then_readd_gets_new_opening_price(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])

        await source.remove_ticker("AAPL")
        assert cache.get("AAPL") is None

        await source.add_ticker("AAPL")
        # New GBMSimulator instance was never recreated — same sim, ticker re-added
        aapl = cache.get("AAPL")
        assert aapl.opening_price == aapl.price

        await source.stop()
```

### 12.4 PriceUpdate model tests

**File: `backend/tests/market/test_models.py`**

```python
from app.market.models import PriceUpdate


def test_session_change_percent():
    u = PriceUpdate(ticker="AAPL", price=195.0, previous_price=194.0, opening_price=190.0)
    assert u.session_change == 5.0
    assert round(u.session_change_percent, 4) == round((195.0 - 190.0) / 190.0 * 100, 4)


def test_to_dict_includes_opening_price_fields():
    u = PriceUpdate(ticker="AAPL", price=195.0, previous_price=194.0, opening_price=190.0)
    d = u.to_dict()
    assert d["opening_price"] == 190.0
    assert "session_change" in d and "session_change_percent" in d


def test_zero_opening_price_does_not_divide_by_zero():
    u = PriceUpdate(ticker="X", price=1.0, previous_price=1.0, opening_price=0.0)
    assert u.session_change_percent == 0.0
```

### 12.5 Massive & SSE

Unchanged from the existing suite: `test_factory.py` (env-var switch), `test_massive.py` (mocked snapshot polling, resilient to malformed data — reserved/not part of this build's supported path per §7). SSE (`stream.py`) remains best tested with an ASGI test client (`httpx.AsyncClient`), asserting the first payload contains every seeded ticker's `opening_price` equal to its `price`.

---

## 13. Error Handling & Edge Cases

### 13.1 Startup: empty watchlist

If the database has no watchlist entries, `start()` receives an empty list. The simulator produces no prices; the SSE endpoint sends nothing until a ticker is added, at which point `add_ticker()` seeds it (and its opening price) immediately.

### 13.2 Price cache miss during trade

```python
price = price_cache.get_price(ticker)
if price is None:
    raise HTTPException(
        status_code=400,
        detail=f"Price not yet available for {ticker}. Please wait a moment and try again.",
    )
```

The simulator avoids this in practice by seeding the cache synchronously inside `add_ticker()`/`start()`, before either returns — by the time a route awaits `source.add_ticker(ticker)`, `price_cache.get(ticker)` is guaranteed non-`None`.

### 13.3 Thread safety under load

`PriceCache` uses `threading.Lock`, a plain mutex. Under normal load (≤50 tickers, 2 updates/sec) contention is negligible — the critical section is a dict lookup plus assignment. Not a concern at this project's scale.

### 13.4 Simulator precision

GBM with a tiny `dt` produces very small per-tick moves. Prices are `round()`ed to 2 decimal places in both `GBMSimulator.step()` and `PriceCache.update()`; the exponential formulation is numerically stable and always positive.

### 13.5 Opening price and negative/degenerate inputs

`session_change_percent` guards `opening_price == 0` the same way `change_percent` guards `previous_price == 0` (§2) — returns `0.0` rather than raising `ZeroDivisionError`. In practice this never triggers: seed prices and randomly generated seeds for unknown tickers are always strictly positive (§5, §6), and GBM's multiplicative update can only produce positive prices, so a real ticker's opening price is never zero. The guard exists purely for the model's own robustness as a value object, independent of how the simulator happens to behave today.

---

## 14. Configuration Summary

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| `MASSIVE_API_KEY` | Environment variable | `""` (empty) | If set, factory returns `MassiveDataSource` (reserved, out of scope — §7); otherwise the simulator |
| `update_interval` | `SimulatorDataSource.__init__` | `0.5` (seconds) | Time between simulator ticks |
| `event_probability` | `GBMSimulator.__init__` | `0.001` | Chance of a random shock event per ticker per tick |
| `dt` | `GBMSimulator.__init__` | `~8.5e-8` | GBM time step (fraction of a trading year) |
| SSE push interval | `_generate_events()` | `0.5` (seconds) | Time between SSE pushes to the client |
| SSE retry directive | `_generate_events()` | `1000` (ms) | Browser `EventSource` reconnection delay |

### Package `__init__.py`

**File: `backend/app/market/__init__.py`** — unchanged; still re-exports `PriceUpdate`, `PriceCache`, `MarketDataSource`, `create_market_data_source`, `create_stream_router`.

---

## 15. Delta vs. the Existing Implementation

`backend/app/market/` as it stands today (per `planning/MARKET_DATA_SUMMARY.md`) implements everything in this document **except opening/session price**. Concretely, against the current code:

| File | Current state | Needed change |
|---|---|---|
| `models.py` | `PriceUpdate` has `ticker, price, previous_price, timestamp` + `change/change_percent/direction` | Add `opening_price: float` field; add `session_change`/`session_change_percent` properties; include both new fields in `to_dict()` (§2) |
| `cache.py` | `update()` tracks `previous_price` only | Also carry `opening_price` forward from the prior `PriceUpdate` (or seed it to `price` on first write) when constructing the new `PriceUpdate`; add `get_opening_price()` convenience (§3) |
| `simulator.py` | No changes needed | None — `GBMSimulator` and `SimulatorDataSource` are already correct once the cache change lands, because they only ever call `cache.update(ticker, price)` |
| `interface.py`, `factory.py`, `stream.py`, `massive_client.py`, `seed_prices.py`, `__init__.py` | No changes needed | None |
| Tests | `test_cache.py`, `test_simulator_source.py`, `test_models.py` don't exercise opening price | Add the cases in §12.2/§12.3/§12.4 |

This is a small, additive change (two files touched for the source, three test files extended) with no impact on the abstract interface, the simulator's math, the SSE wire mechanics, or the Massive path. Everything currently passing (73 tests per `MARKET_DATA_SUMMARY.md`) keeps passing; the new tests are additions, not replacements, since `opening_price` is a new required constructor field on `PriceUpdate` — existing call sites that construct `PriceUpdate` directly (rather than through `PriceCache.update()`) will need one extra argument, but a search of the current codebase shows the only production constructor call is inside `PriceCache.update()` itself, so this is a self-contained change.
