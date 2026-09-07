"""Default seed data for a fresh database (see PLAN.md sec 7)."""

from __future__ import annotations

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE_CENTS = 1_000_000  # $10,000.00

DEFAULT_WATCHLIST_TICKERS: list[str] = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
]
