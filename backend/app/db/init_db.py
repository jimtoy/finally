"""Database startup routine: create schema and seed default data.

Safe to call on every app startup — table creation uses CREATE TABLE IF NOT
EXISTS, and seeding checks for existing rows before inserting.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from .schema import create_tables
from .seed_data import (
    DEFAULT_CASH_BALANCE_CENTS,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST_TICKERS,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _seed_user_profile(conn: sqlite3.Connection, user_id: str) -> None:
    existing = conn.execute(
        "SELECT 1 FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    if existing is not None:
        return
    conn.execute(
        "INSERT INTO users_profile (id, cash_balance_cents, created_at) VALUES (?, ?, ?)",
        (user_id, DEFAULT_CASH_BALANCE_CENTS, _now_iso()),
    )


def _seed_watchlist(conn: sqlite3.Connection, user_id: str) -> None:
    existing = conn.execute(
        "SELECT 1 FROM watchlist WHERE user_id = ? LIMIT 1", (user_id,)
    ).fetchone()
    if existing is not None:
        return
    now = _now_iso()
    conn.executemany(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        [(str(uuid.uuid4()), user_id, ticker, now) for ticker in DEFAULT_WATCHLIST_TICKERS],
    )


def _seed_initial_snapshot(conn: sqlite3.Connection, user_id: str) -> None:
    existing = conn.execute(
        "SELECT 1 FROM portfolio_snapshots WHERE user_id = ? LIMIT 1", (user_id,)
    ).fetchone()
    if existing is not None:
        return
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value_cents, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, DEFAULT_CASH_BALANCE_CENTS, _now_iso()),
    )


def init_db(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> None:
    """Create tables if missing and seed default data if empty. Idempotent."""
    create_tables(conn)
    with conn:
        _seed_user_profile(conn, user_id)
        _seed_watchlist(conn, user_id)
        _seed_initial_snapshot(conn, user_id)
