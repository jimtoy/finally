"""Data models for the database layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserProfile:
    """A user's cash balance. Single hardcoded row for this single-user demo."""

    id: str
    cash_balance_cents: int
    created_at: str  # ISO timestamp


@dataclass(frozen=True, slots=True)
class WatchlistEntry:
    """A ticker the user is watching."""

    id: str
    user_id: str
    ticker: str
    added_at: str  # ISO timestamp


@dataclass(frozen=True, slots=True)
class Position:
    """A current holding: one row per ticker per user."""

    id: str
    user_id: str
    ticker: str
    quantity: float
    avg_cost_cents: int
    updated_at: str  # ISO timestamp


@dataclass(frozen=True, slots=True)
class Trade:
    """An executed trade (append-only log)."""

    id: str
    user_id: str
    ticker: str
    side: str  # "buy" or "sell"
    quantity: float
    price_cents: int
    executed_at: str  # ISO timestamp


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Total portfolio value at a point in time (for the P&L chart)."""

    id: str
    user_id: str
    total_value_cents: int
    recorded_at: str  # ISO timestamp


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A message in the conversation history with the LLM."""

    id: str
    user_id: str
    role: str  # "user" or "assistant"
    content: str
    actions: str | None  # JSON string; null for user messages
    created_at: str  # ISO timestamp
