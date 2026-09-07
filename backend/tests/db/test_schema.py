"""Tests for schema creation."""

from __future__ import annotations

import sqlite3

from app.db.schema import ALL_TABLES, create_tables

EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def test_create_tables_creates_all_expected_tables(conn: sqlite3.Connection) -> None:
    create_tables(conn)
    assert EXPECTED_TABLES <= _table_names(conn)


def test_create_tables_is_idempotent(conn: sqlite3.Connection) -> None:
    create_tables(conn)
    create_tables(conn)  # should not raise
    assert EXPECTED_TABLES <= _table_names(conn)


def test_all_tables_list_matches_expected_count() -> None:
    assert len(ALL_TABLES) == len(EXPECTED_TABLES)


def test_watchlist_unique_constraint(conn: sqlite3.Connection) -> None:
    create_tables(conn)
    conn.execute(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES ('1', 'default', 'AAPL', 't')"
    )
    try:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) "
            "VALUES ('2', 'default', 'AAPL', 't')"
        )
        assert False, "expected UNIQUE constraint violation"
    except sqlite3.IntegrityError:
        pass


def test_positions_unique_constraint(conn: sqlite3.Connection) -> None:
    create_tables(conn)
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost_cents, updated_at) "
        "VALUES ('1', 'default', 'AAPL', 10, 19000, 't')"
    )
    try:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost_cents, updated_at) "
            "VALUES ('2', 'default', 'AAPL', 5, 19000, 't')"
        )
        assert False, "expected UNIQUE constraint violation"
    except sqlite3.IntegrityError:
        pass
