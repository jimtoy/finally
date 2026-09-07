"""Tests for data-access helper functions."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app.db import repository as repo

# --- users_profile ---------------------------------------------------------


def test_get_cash_balance_cents(seeded_conn: sqlite3.Connection) -> None:
    assert repo.get_cash_balance_cents(seeded_conn) == 1_000_000


def test_update_cash_balance_cents(seeded_conn: sqlite3.Connection) -> None:
    repo.update_cash_balance_cents(seeded_conn, 750_000)
    assert repo.get_cash_balance_cents(seeded_conn) == 750_000


def test_get_cash_balance_cents_missing_user_raises(conn: sqlite3.Connection) -> None:
    from app.db.schema import create_tables

    create_tables(conn)
    with pytest.raises(LookupError):
        repo.get_cash_balance_cents(conn, "nobody")


# --- watchlist ---------------------------------------------------------


def test_get_watchlist_returns_seeded_tickers(seeded_conn: sqlite3.Connection) -> None:
    entries = repo.get_watchlist(seeded_conn)
    assert len(entries) == 10
    assert {e.ticker for e in entries} == {
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
    }


def test_add_watchlist_entry_new_ticker(seeded_conn: sqlite3.Connection) -> None:
    entry, created = repo.add_watchlist_entry(seeded_conn, "PYPL")
    assert created is True
    assert entry.ticker == "PYPL"
    assert repo.get_watchlist_entry(seeded_conn, "PYPL") is not None


def test_add_watchlist_entry_existing_ticker_returns_existing(
    seeded_conn: sqlite3.Connection,
) -> None:
    entry, created = repo.add_watchlist_entry(seeded_conn, "AAPL")
    assert created is False
    assert entry.ticker == "AAPL"
    assert len(repo.get_watchlist(seeded_conn)) == 10  # unchanged


def test_remove_watchlist_entry(seeded_conn: sqlite3.Connection) -> None:
    repo.remove_watchlist_entry(seeded_conn, "AAPL")
    assert repo.get_watchlist_entry(seeded_conn, "AAPL") is None
    assert len(repo.get_watchlist(seeded_conn)) == 9


def test_remove_watchlist_entry_idempotent(seeded_conn: sqlite3.Connection) -> None:
    repo.remove_watchlist_entry(seeded_conn, "NOTREAL")  # should not raise
    assert len(repo.get_watchlist(seeded_conn)) == 10


# --- positions ---------------------------------------------------------


def test_upsert_position_creates_new(seeded_conn: sqlite3.Connection) -> None:
    position = repo.upsert_position(seeded_conn, "AAPL", 10.0, 19000)
    assert position.ticker == "AAPL"
    assert position.quantity == 10.0
    assert position.avg_cost_cents == 19000


def test_upsert_position_updates_existing(seeded_conn: sqlite3.Connection) -> None:
    first = repo.upsert_position(seeded_conn, "AAPL", 10.0, 19000)
    second = repo.upsert_position(seeded_conn, "AAPL", 15.0, 19500)
    assert second.id == first.id  # same row, not a new one
    assert second.quantity == 15.0
    assert second.avg_cost_cents == 19500
    assert len(repo.get_positions(seeded_conn)) == 1


def test_delete_position(seeded_conn: sqlite3.Connection) -> None:
    repo.upsert_position(seeded_conn, "AAPL", 10.0, 19000)
    repo.delete_position(seeded_conn, "AAPL")
    assert repo.get_position(seeded_conn, "AAPL") is None


def test_delete_position_idempotent(seeded_conn: sqlite3.Connection) -> None:
    repo.delete_position(seeded_conn, "NOTHELD")  # should not raise


# --- trades ---------------------------------------------------------


def test_insert_trade_and_get_trades(seeded_conn: sqlite3.Connection) -> None:
    repo.insert_trade(seeded_conn, "AAPL", "buy", 10.0, 19000)
    repo.insert_trade(seeded_conn, "AAPL", "sell", 5.0, 19500)
    trades = repo.get_trades(seeded_conn)
    assert len(trades) == 2
    # descending (most recent first)
    assert trades[0].side == "sell"
    assert trades[1].side == "buy"


def test_get_trades_limit(seeded_conn: sqlite3.Connection) -> None:
    for i in range(5):
        repo.insert_trade(seeded_conn, "AAPL", "buy", 1.0, 19000 + i)
    trades = repo.get_trades(seeded_conn, limit=2)
    assert len(trades) == 2


# --- portfolio_snapshots ---------------------------------------------------------


def test_insert_and_get_portfolio_history_ascending(seeded_conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC)
    repo.insert_portfolio_snapshot(
        seeded_conn, 1_010_000, recorded_at=(now - timedelta(minutes=10)).isoformat()
    )
    repo.insert_portfolio_snapshot(
        seeded_conn, 1_020_000, recorded_at=(now - timedelta(minutes=5)).isoformat()
    )
    history = repo.get_portfolio_history(seeded_conn, now=now)
    # seed snapshot + the two inserted above, ascending by recorded_at
    recorded_ats = [s.recorded_at for s in history]
    assert recorded_ats == sorted(recorded_ats)
    values = [s.total_value_cents for s in history]
    assert 1_010_000 in values
    assert 1_020_000 in values
    assert values.index(1_010_000) < values.index(1_020_000)


def test_get_portfolio_history_full_cadence_within_24h(seeded_conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC)
    for minutes_ago in [1, 2, 3, 4, 5]:
        repo.insert_portfolio_snapshot(
            seeded_conn,
            1_000_000 + minutes_ago,
            recorded_at=(now - timedelta(minutes=minutes_ago)).isoformat(),
        )
    history = repo.get_portfolio_history(seeded_conn, now=now)
    # seed snapshot (at ~now) + 5 inserted = 6, all within last 24h, no downsampling
    assert len(history) == 6


def test_get_portfolio_history_downsamples_older_than_24h(seeded_conn: sqlite3.Connection) -> None:
    # Fixed reference time (rather than datetime.now(UTC)) so the 5-minute
    # bucket boundaries below don't depend on the wall-clock second the test
    # happens to run at.
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    base = (now - timedelta(hours=30)).replace(minute=0, second=0, microsecond=0)
    # 6 snapshots within the same 5-minute bucket, all older than 24h
    for i in range(6):
        repo.insert_portfolio_snapshot(
            seeded_conn,
            3_000_000 + i,
            recorded_at=(base + timedelta(seconds=i * 10)).isoformat(),
        )
    # one snapshot in a distinct, later bucket, still older than 24h
    repo.insert_portfolio_snapshot(
        seeded_conn, 4_000_000, recorded_at=(base + timedelta(minutes=10)).isoformat()
    )

    history = repo.get_portfolio_history(
        seeded_conn, since=(base - timedelta(minutes=1)).isoformat(), now=now
    )

    # the 6 same-bucket snapshots collapse to 1 (the last one), plus the
    # distinct-bucket snapshot, plus the seed snapshot (within last 24h) = 3
    assert len(history) == 3
    values = [s.total_value_cents for s in history]
    assert 3_000_005 in values  # last of the collapsed bucket survives
    assert 3_000_000 not in values
    assert 4_000_000 in values


def test_get_portfolio_history_ordering_with_downsampling(seeded_conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC)
    history = repo.get_portfolio_history(seeded_conn, now=now)
    recorded_ats = [s.recorded_at for s in history]
    assert recorded_ats == sorted(recorded_ats)


# --- chat_messages ---------------------------------------------------------


def test_insert_and_get_most_recent_chat_message(seeded_conn: sqlite3.Connection) -> None:
    repo.insert_chat_message(seeded_conn, "user", "hello")
    repo.insert_chat_message(seeded_conn, "assistant", "hi there", actions='[{"type": "trade"}]')
    most_recent = repo.get_most_recent_chat_message(seeded_conn)
    assert most_recent is not None
    assert most_recent.role == "assistant"
    assert most_recent.content == "hi there"
    assert most_recent.actions == '[{"type": "trade"}]'


def test_get_most_recent_chat_message_none_when_empty(seeded_conn: sqlite3.Connection) -> None:
    assert repo.get_most_recent_chat_message(seeded_conn) is None


def test_get_chat_messages_ascending_order(seeded_conn: sqlite3.Connection) -> None:
    repo.insert_chat_message(seeded_conn, "user", "first")
    repo.insert_chat_message(seeded_conn, "assistant", "second")
    repo.insert_chat_message(seeded_conn, "user", "third")
    messages = repo.get_chat_messages(seeded_conn)
    assert [m.content for m in messages] == ["first", "second", "third"]


def test_get_chat_messages_limit_keeps_most_recent(seeded_conn: sqlite3.Connection) -> None:
    repo.insert_chat_message(seeded_conn, "user", "first")
    repo.insert_chat_message(seeded_conn, "assistant", "second")
    repo.insert_chat_message(seeded_conn, "user", "third")
    messages = repo.get_chat_messages(seeded_conn, limit=2)
    assert [m.content for m in messages] == ["second", "third"]
