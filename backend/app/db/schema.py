"""SQL DDL for the FinAlly database schema."""

from __future__ import annotations

import sqlite3

CREATE_USERS_PROFILE = """
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY,
    cash_balance_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_WATCHLIST = """
CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (user_id, ticker)
)
"""

CREATE_POSITIONS = """
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_cost_cents INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, ticker)
)
"""

CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price_cents INTEGER NOT NULL,
    executed_at TEXT NOT NULL
)
"""

CREATE_PORTFOLIO_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value_cents INTEGER NOT NULL,
    recorded_at TEXT NOT NULL
)
"""

CREATE_CHAT_MESSAGES = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL
)
"""

# Indexes to keep the common lookups (by user_id, and time-ordered scans) fast.
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_positions_user ON positions (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_trades_user_executed ON trades (user_id, executed_at)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_user_recorded "
    "ON portfolio_snapshots (user_id, recorded_at)",
    "CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created "
    "ON chat_messages (user_id, created_at)",
]

ALL_TABLES = [
    CREATE_USERS_PROFILE,
    CREATE_WATCHLIST,
    CREATE_POSITIONS,
    CREATE_TRADES,
    CREATE_PORTFOLIO_SNAPSHOTS,
    CREATE_CHAT_MESSAGES,
]


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't already exist."""
    with conn:
        for statement in ALL_TABLES:
            conn.execute(statement)
        for statement in CREATE_INDEXES:
            conn.execute(statement)
