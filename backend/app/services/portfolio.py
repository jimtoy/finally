"""Portfolio valuation and trade execution.

Rounding rule for money: all persisted amounts are integer cents. A leg's
notional is `round(price_cents * quantity)` and a position's weighted average
cost is `round(total_cost_cents / quantity)` — both banker's-rounded once, at
the point of persistence, so fractional-share trades never accumulate drift in
the stored values.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from app.api.errors import ApiError
from app.api.schemas import PortfolioOut, PositionOut, TradeOut
from app.db import models as db_models
from app.db import repository as repo
from app.market import PriceCache

_HISTORY_WINDOW = timedelta(hours=24)


class _JoinedConnection:
    """Connection proxy whose `with` block is a no-op.

    Repository helpers each wrap their write in `with conn:`, which commits on
    exit. Passing this proxy instead lets several of them run inside one
    caller-controlled transaction so a trade commits all-or-nothing.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __enter__(self) -> _JoinedConnection:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def __getattr__(self, name: str) -> object:
        return getattr(self._conn, name)


def _to_dollars(cents: int) -> float:
    return round(cents / 100, 2)


def _to_cents(dollars: float) -> int:
    return round(dollars * 100)


def _price_cents(cache: PriceCache, ticker: str) -> int | None:
    price = cache.get_price(ticker)
    return None if price is None else _to_cents(price)


def build_portfolio(conn: sqlite3.Connection, cache: PriceCache) -> PortfolioOut:
    """Current portfolio state, priced from the market cache."""
    cash_cents = repo.get_cash_balance_cents(conn)
    positions_out: list[PositionOut] = []
    holdings_cents = 0
    unrealized_cents = 0

    for position in repo.get_positions(conn):
        # A held ticker should always be priced; fall back to cost basis so a
        # gap in the cache reads as flat rather than erasing the position.
        current_cents = _price_cents(cache, position.ticker) or position.avg_cost_cents
        market_value_cents = round(current_cents * position.quantity)
        cost_basis_cents = round(position.avg_cost_cents * position.quantity)
        pnl_cents = market_value_cents - cost_basis_cents

        holdings_cents += market_value_cents
        unrealized_cents += pnl_cents

        percent_change = (
            round((current_cents - position.avg_cost_cents) / position.avg_cost_cents * 100, 2)
            if position.avg_cost_cents
            else 0.0
        )
        positions_out.append(
            PositionOut(
                ticker=position.ticker,
                quantity=position.quantity,
                average_cost=_to_dollars(position.avg_cost_cents),
                current_price=_to_dollars(current_cents),
                market_value=_to_dollars(market_value_cents),
                unrealized_pnl=_to_dollars(pnl_cents),
                percent_change=percent_change,
            )
        )

    return PortfolioOut(
        cash_balance=_to_dollars(cash_cents),
        total_value=_to_dollars(cash_cents + holdings_cents),
        unrealized_pnl=_to_dollars(unrealized_cents),
        positions=positions_out,
    )


def total_value_cents(conn: sqlite3.Connection, cache: PriceCache) -> int:
    """Cash plus the market value of every holding, in cents."""
    total = repo.get_cash_balance_cents(conn)
    for position in repo.get_positions(conn):
        current_cents = _price_cents(cache, position.ticker) or position.avg_cost_cents
        total += round(current_cents * position.quantity)
    return total


def record_snapshot(conn: sqlite3.Connection, cache: PriceCache) -> db_models.PortfolioSnapshot:
    return repo.insert_portfolio_snapshot(conn, total_value_cents(conn, cache))


def get_history(conn: sqlite3.Connection) -> list[db_models.PortfolioSnapshot]:
    since = (datetime.now(UTC) - _HISTORY_WINDOW).isoformat()
    return repo.get_portfolio_history(conn, since=since)


def execute_trade(
    conn: sqlite3.Connection,
    cache: PriceCache,
    ticker: str,
    side: str,
    quantity: float,
) -> TradeOut:
    """Validate and atomically execute a market order at the current cache price."""
    if quantity <= 0:
        raise ApiError("Quantity must be greater than zero.", "invalid_quantity")

    price_cents = _price_cents(cache, ticker)
    if price_cents is None:
        raise ApiError(f"No current price available for {ticker}.", "price_unavailable")

    notional_cents = round(price_cents * quantity)
    position = repo.get_position(conn, ticker)
    cash_cents = repo.get_cash_balance_cents(conn)

    if side == "buy":
        if notional_cents > cash_cents:
            raise ApiError(
                f"Insufficient funds: {ticker} costs "
                f"${_to_dollars(notional_cents):,.2f} but only "
                f"${_to_dollars(cash_cents):,.2f} is available.",
                "insufficient_funds",
            )
        new_cash_cents = cash_cents - notional_cents
        new_quantity = (position.quantity if position else 0.0) + quantity
        prior_cost_cents = round(position.avg_cost_cents * position.quantity) if position else 0
        new_avg_cost_cents = round((prior_cost_cents + notional_cents) / new_quantity)
    else:
        held = position.quantity if position else 0.0
        if quantity > held:
            raise ApiError(
                f"Insufficient shares: cannot sell {quantity} {ticker}, only {held} held.",
                "insufficient_shares",
            )
        new_cash_cents = cash_cents + notional_cents
        new_quantity = held - quantity
        new_avg_cost_cents = position.avg_cost_cents if position else 0

    joined = _JoinedConnection(conn)
    try:
        repo.update_cash_balance_cents(joined, new_cash_cents)
        if new_quantity > 0:
            repo.upsert_position(joined, ticker, new_quantity, new_avg_cost_cents)
        else:
            repo.delete_position(joined, ticker)
        trade = repo.insert_trade(joined, ticker, side, quantity, price_cents)
        repo.insert_portfolio_snapshot(joined, total_value_cents(joined, cache))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return TradeOut(
        id=trade.id,
        ticker=trade.ticker,
        side=trade.side,
        quantity=trade.quantity,
        price=_to_dollars(trade.price_cents),
        executed_at=trade.executed_at,
    )
