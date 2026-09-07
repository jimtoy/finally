"""Watchlist reads and mutations, kept in sync with the market data source."""

from __future__ import annotations

import sqlite3

from app.api.schemas import WatchlistItemOut
from app.db import repository as repo
from app.market import PriceCache
from app.runtime import get_market_source


def _to_item(ticker: str, added_at: str, cache: PriceCache) -> WatchlistItemOut:
    update = cache.get(ticker)
    if update is None:
        return WatchlistItemOut(ticker=ticker, added_at=added_at)

    opening = update.opening_price
    session_change = round(update.price - opening, 2)
    session_percent = round((update.price - opening) / opening * 100, 2) if opening else 0.0
    return WatchlistItemOut(
        ticker=ticker,
        added_at=added_at,
        price=update.price,
        opening_price=opening,
        change=session_change,
        change_percent=session_percent,
        direction=update.direction,
    )


def list_watchlist(conn: sqlite3.Connection, cache: PriceCache) -> list[WatchlistItemOut]:
    return [_to_item(entry.ticker, entry.added_at, cache) for entry in repo.get_watchlist(conn)]


async def add_ticker(
    conn: sqlite3.Connection, cache: PriceCache, ticker: str
) -> tuple[WatchlistItemOut, bool]:
    """Add a ticker and make sure it is priced before it is exposed to callers."""
    source = get_market_source()
    if source is not None and ticker not in cache:
        await source.add_ticker(ticker)

    entry, created = repo.add_watchlist_entry(conn, ticker)
    return _to_item(entry.ticker, entry.added_at, cache), created


async def remove_ticker(conn: sqlite3.Connection, ticker: str) -> None:
    """Remove a ticker. A ticker that is still held keeps being priced (PLAN.md sec 6)."""
    repo.remove_watchlist_entry(conn, ticker)

    source = get_market_source()
    if source is not None and repo.get_position(conn, ticker) is None:
        await source.remove_ticker(ticker)
