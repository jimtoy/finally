"""Data-access helper functions.

Plain CRUD over the schema defined in schema.py — no business logic (trade
validation, P&L math, etc. belong to callers). Every function takes an open
sqlite3.Connection as its first argument so callers control transaction/commit
scope.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

from .models import ChatMessage, PortfolioSnapshot, Position, Trade, UserProfile, WatchlistEntry
from .seed_data import DEFAULT_USER_ID

# Snapshots older than this are downsampled in get_portfolio_history().
_FULL_CADENCE_WINDOW = timedelta(hours=24)
_DOWNSAMPLE_BUCKET = timedelta(minutes=5)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_user_profile(row: sqlite3.Row) -> UserProfile:
    return UserProfile(id=row["id"], cash_balance_cents=row["cash_balance_cents"],
                        created_at=row["created_at"])


def _row_to_watchlist_entry(row: sqlite3.Row) -> WatchlistEntry:
    return WatchlistEntry(id=row["id"], user_id=row["user_id"], ticker=row["ticker"],
                           added_at=row["added_at"])


def _row_to_position(row: sqlite3.Row) -> Position:
    return Position(id=row["id"], user_id=row["user_id"], ticker=row["ticker"],
                     quantity=row["quantity"], avg_cost_cents=row["avg_cost_cents"],
                     updated_at=row["updated_at"])


def _row_to_trade(row: sqlite3.Row) -> Trade:
    return Trade(id=row["id"], user_id=row["user_id"], ticker=row["ticker"],
                 side=row["side"], quantity=row["quantity"], price_cents=row["price_cents"],
                 executed_at=row["executed_at"])


def _row_to_snapshot(row: sqlite3.Row) -> PortfolioSnapshot:
    return PortfolioSnapshot(id=row["id"], user_id=row["user_id"],
                              total_value_cents=row["total_value_cents"],
                              recorded_at=row["recorded_at"])


def _row_to_chat_message(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(id=row["id"], user_id=row["user_id"], role=row["role"],
                        content=row["content"], actions=row["actions"],
                        created_at=row["created_at"])


# --- users_profile ---------------------------------------------------------


def get_user_profile(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> UserProfile | None:
    row = conn.execute("SELECT * FROM users_profile WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user_profile(row) if row else None


def get_cash_balance_cents(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> int:
    row = conn.execute(
        "SELECT cash_balance_cents FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"No users_profile row for user_id={user_id!r}")
    return row["cash_balance_cents"]


def update_cash_balance_cents(
    conn: sqlite3.Connection, cash_balance_cents: int, user_id: str = DEFAULT_USER_ID
) -> None:
    with conn:
        conn.execute(
            "UPDATE users_profile SET cash_balance_cents = ? WHERE id = ?",
            (cash_balance_cents, user_id),
        )


# --- watchlist ---------------------------------------------------------


def get_watchlist(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[WatchlistEntry]:
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at ASC", (user_id,)
    ).fetchall()
    return [_row_to_watchlist_entry(row) for row in rows]


def get_watchlist_entry(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> WatchlistEntry | None:
    row = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    ).fetchone()
    return _row_to_watchlist_entry(row) if row else None


def add_watchlist_entry(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> tuple[WatchlistEntry, bool]:
    """Insert a watchlist entry. Returns (entry, created) — created is False if
    the ticker was already watched, in which case the existing entry is returned."""
    existing = get_watchlist_entry(conn, ticker, user_id)
    if existing is not None:
        return existing, False
    entry_id = _new_id()
    added_at = _now_iso()
    with conn:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (entry_id, user_id, ticker, added_at),
        )
    return WatchlistEntry(id=entry_id, user_id=user_id, ticker=ticker, added_at=added_at), True


def remove_watchlist_entry(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> None:
    """Idempotent: no error if the ticker wasn't watched."""
    with conn:
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )


# --- positions ---------------------------------------------------------


def get_positions(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[Position]:
    rows = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? ORDER BY ticker ASC", (user_id,)
    ).fetchall()
    return [_row_to_position(row) for row in rows]


def get_position(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> Position | None:
    row = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    ).fetchone()
    return _row_to_position(row) if row else None


def upsert_position(
    conn: sqlite3.Connection,
    ticker: str,
    quantity: float,
    avg_cost_cents: int,
    user_id: str = DEFAULT_USER_ID,
) -> Position:
    """Replace the position's quantity/avg_cost, creating it if it doesn't exist."""
    existing = get_position(conn, ticker, user_id)
    updated_at = _now_iso()
    position_id = existing.id if existing else _new_id()
    with conn:
        conn.execute(
            """
            INSERT INTO positions (id, user_id, ticker, quantity, avg_cost_cents, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, ticker) DO UPDATE SET
                quantity = excluded.quantity,
                avg_cost_cents = excluded.avg_cost_cents,
                updated_at = excluded.updated_at
            """,
            (position_id, user_id, ticker, quantity, avg_cost_cents, updated_at),
        )
    return Position(id=position_id, user_id=user_id, ticker=ticker, quantity=quantity,
                     avg_cost_cents=avg_cost_cents, updated_at=updated_at)


def delete_position(conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Idempotent: no error if there was no such position."""
    with conn:
        conn.execute("DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker))


# --- trades ---------------------------------------------------------


def insert_trade(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price_cents: int,
    user_id: str = DEFAULT_USER_ID,
) -> Trade:
    trade_id = _new_id()
    executed_at = _now_iso()
    with conn:
        conn.execute(
            """
            INSERT INTO trades (id, user_id, ticker, side, quantity, price_cents, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (trade_id, user_id, ticker, side, quantity, price_cents, executed_at),
        )
    return Trade(id=trade_id, user_id=user_id, ticker=ticker, side=side, quantity=quantity,
                 price_cents=price_cents, executed_at=executed_at)


def get_trades(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID, limit: int | None = None
) -> list[Trade]:
    """Trades in descending (most recent first) order, optionally limited."""
    query = "SELECT * FROM trades WHERE user_id = ? ORDER BY executed_at DESC"
    params: tuple = (user_id,)
    if limit is not None:
        query += " LIMIT ?"
        params = (user_id, limit)
    rows = conn.execute(query, params).fetchall()
    return [_row_to_trade(row) for row in rows]


# --- portfolio_snapshots ---------------------------------------------------------


def insert_portfolio_snapshot(
    conn: sqlite3.Connection,
    total_value_cents: int,
    user_id: str = DEFAULT_USER_ID,
    recorded_at: str | None = None,
) -> PortfolioSnapshot:
    snapshot_id = _new_id()
    recorded_at = recorded_at or _now_iso()
    with conn:
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (id, user_id, total_value_cents, recorded_at)
            VALUES (?, ?, ?, ?)
            """,
            (snapshot_id, user_id, total_value_cents, recorded_at),
        )
    return PortfolioSnapshot(id=snapshot_id, user_id=user_id, total_value_cents=total_value_cents,
                              recorded_at=recorded_at)


def _bucket_key(recorded_at: str, bucket: timedelta) -> int:
    dt = datetime.fromisoformat(recorded_at)
    return int(dt.timestamp() // bucket.total_seconds())


def get_portfolio_history(
    conn: sqlite3.Connection,
    user_id: str = DEFAULT_USER_ID,
    since: str | None = None,
    now: datetime | None = None,
) -> list[PortfolioSnapshot]:
    """Ascending snapshots for the P&L chart.

    The most recent 24 hours are returned at full cadence. Anything older
    (only reachable by passing a `since` further back than 24h) is downsampled
    to one point per 5-minute bucket (the last snapshot in each bucket), per
    PLAN.md sec 7.
    """
    now = now or datetime.now(UTC)
    full_cadence_cutoff = now - _FULL_CADENCE_WINDOW

    rows = conn.execute(
        "SELECT * FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at ASC",
        (user_id,),
    ).fetchall()
    snapshots = [_row_to_snapshot(row) for row in rows]

    if since is not None:
        snapshots = [s for s in snapshots if s.recorded_at >= since]

    cutoff_iso = full_cadence_cutoff.isoformat()
    older = [s for s in snapshots if s.recorded_at < cutoff_iso]
    recent = [s for s in snapshots if s.recorded_at >= cutoff_iso]

    downsampled: dict[int, PortfolioSnapshot] = {}
    for snapshot in older:
        bucket = _bucket_key(snapshot.recorded_at, _DOWNSAMPLE_BUCKET)
        downsampled[bucket] = snapshot  # last write per bucket wins (ascending input)

    result = sorted(downsampled.values(), key=lambda s: s.recorded_at) + recent
    return result


# --- chat_messages ---------------------------------------------------------


def insert_chat_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    actions: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> ChatMessage:
    message_id = _new_id()
    created_at = _now_iso()
    with conn:
        conn.execute(
            """
            INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, user_id, role, content, actions, created_at),
        )
    return ChatMessage(id=message_id, user_id=user_id, role=role, content=content,
                        actions=actions, created_at=created_at)


def get_most_recent_chat_message(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> ChatMessage | None:
    row = conn.execute(
        "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return _row_to_chat_message(row) if row else None


def get_chat_messages(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID, limit: int | None = None
) -> list[ChatMessage]:
    """Chat messages in ascending (chronological) order, optionally limited to
    the most recent `limit` messages."""
    query = "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC"
    params: tuple = (user_id,)
    if limit is not None:
        query += " LIMIT ?"
        params = (user_id, limit)
    rows = conn.execute(query, params).fetchall()
    return [_row_to_chat_message(row) for row in reversed(rows)]
