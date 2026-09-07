"""Tests for the startup init/seed routine."""

from __future__ import annotations

import sqlite3

from app.db.init_db import init_db
from app.db.seed_data import (
    DEFAULT_CASH_BALANCE_CENTS,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST_TICKERS,
)


def test_init_db_seeds_user_profile(conn: sqlite3.Connection) -> None:
    init_db(conn)
    row = conn.execute(
        "SELECT * FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    ).fetchone()
    assert row is not None
    assert row["cash_balance_cents"] == DEFAULT_CASH_BALANCE_CENTS


def test_init_db_seeds_default_watchlist(conn: sqlite3.Connection) -> None:
    init_db(conn)
    rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ?", (DEFAULT_USER_ID,)
    ).fetchall()
    tickers = {row["ticker"] for row in rows}
    assert tickers == set(DEFAULT_WATCHLIST_TICKERS)
    assert len(rows) == len(DEFAULT_WATCHLIST_TICKERS)


def test_init_db_seeds_initial_snapshot(conn: sqlite3.Connection) -> None:
    init_db(conn)
    rows = conn.execute(
        "SELECT * FROM portfolio_snapshots WHERE user_id = ?", (DEFAULT_USER_ID,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["total_value_cents"] == DEFAULT_CASH_BALANCE_CENTS


def test_init_db_is_idempotent(conn: sqlite3.Connection) -> None:
    init_db(conn)
    init_db(conn)
    init_db(conn)

    user_rows = conn.execute("SELECT * FROM users_profile").fetchall()
    watchlist_rows = conn.execute("SELECT * FROM watchlist").fetchall()
    snapshot_rows = conn.execute("SELECT * FROM portfolio_snapshots").fetchall()

    assert len(user_rows) == 1
    assert len(watchlist_rows) == len(DEFAULT_WATCHLIST_TICKERS)
    assert len(snapshot_rows) == 1


def test_init_db_preserves_existing_cash_balance(conn: sqlite3.Connection) -> None:
    init_db(conn)
    with conn:
        conn.execute(
            "UPDATE users_profile SET cash_balance_cents = 500000 WHERE id = ?",
            (DEFAULT_USER_ID,),
        )
    init_db(conn)  # should not reset the balance back to the default
    row = conn.execute(
        "SELECT cash_balance_cents FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    ).fetchone()
    assert row["cash_balance_cents"] == 500000
