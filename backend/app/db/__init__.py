"""Database layer for FinAlly.

Public API:
    get_connection, get_db_path - Open/locate the SQLite database
    init_db                     - Create schema and seed default data (idempotent)
    Data models: UserProfile, WatchlistEntry, Position, Trade,
                 PortfolioSnapshot, ChatMessage
    Data-access helpers: see repository.py (get_cash_balance_cents,
                 get_watchlist, add_watchlist_entry, remove_watchlist_entry,
                 get_positions, get_position, upsert_position, delete_position,
                 insert_trade, get_trades, insert_portfolio_snapshot,
                 get_portfolio_history, insert_chat_message,
                 get_most_recent_chat_message, get_chat_messages)
"""

from .connection import get_connection, get_db_path
from .init_db import init_db
from .models import ChatMessage, PortfolioSnapshot, Position, Trade, UserProfile, WatchlistEntry
from .repository import (
    add_watchlist_entry,
    delete_position,
    get_cash_balance_cents,
    get_chat_messages,
    get_most_recent_chat_message,
    get_portfolio_history,
    get_position,
    get_positions,
    get_trades,
    get_user_profile,
    get_watchlist,
    get_watchlist_entry,
    insert_chat_message,
    insert_portfolio_snapshot,
    insert_trade,
    remove_watchlist_entry,
    update_cash_balance_cents,
    upsert_position,
)
from .seed_data import DEFAULT_CASH_BALANCE_CENTS, DEFAULT_USER_ID, DEFAULT_WATCHLIST_TICKERS

__all__ = [
    "get_connection",
    "get_db_path",
    "init_db",
    "UserProfile",
    "WatchlistEntry",
    "Position",
    "Trade",
    "PortfolioSnapshot",
    "ChatMessage",
    "DEFAULT_USER_ID",
    "DEFAULT_CASH_BALANCE_CENTS",
    "DEFAULT_WATCHLIST_TICKERS",
    "get_user_profile",
    "get_cash_balance_cents",
    "update_cash_balance_cents",
    "get_watchlist",
    "get_watchlist_entry",
    "add_watchlist_entry",
    "remove_watchlist_entry",
    "get_positions",
    "get_position",
    "upsert_position",
    "delete_position",
    "insert_trade",
    "get_trades",
    "insert_portfolio_snapshot",
    "get_portfolio_history",
    "insert_chat_message",
    "get_most_recent_chat_message",
    "get_chat_messages",
]
