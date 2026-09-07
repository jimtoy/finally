"""Process-wide market data runtime.

The price cache is a singleton because a single simulator task writes to it and
every reader (SSE stream, portfolio valuation, trade execution) must see the
same prices. Holding it here keeps route modules free of import-time wiring.
"""

from __future__ import annotations

from app.market import MarketDataSource, PriceCache

_price_cache = PriceCache()
_market_source: MarketDataSource | None = None


def get_price_cache() -> PriceCache:
    return _price_cache


def get_market_source() -> MarketDataSource | None:
    """The running data source, or None when the app was started without one."""
    return _market_source


def set_market_source(source: MarketDataSource | None) -> None:
    global _market_source
    _market_source = source
