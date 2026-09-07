"""Pydantic request/response models for the FinAlly API (PLAN.md sec 8).

Money crosses the API boundary as decimal dollars; it is stored and calculated
in integer cents everywhere behind it.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _normalize_ticker(value: object) -> object:
    """Trim and uppercase tickers at every API boundary (PLAN.md sec 6)."""
    return value.strip().upper() if isinstance(value, str) else value


Ticker = Annotated[str, BeforeValidator(_normalize_ticker), Field(min_length=1, max_length=16)]
Side = Literal["buy", "sell"]


class PositionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    quantity: float
    average_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    percent_change: float


class PortfolioOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_balance: float
    total_value: float
    unrealized_pnl: float
    positions: list[PositionOut]


class TradeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker
    quantity: float = Field(gt=0)
    side: Side


class TradeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ticker: str
    side: Side
    quantity: float
    price: float
    executed_at: str


class TradeExecutionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade: TradeOut
    portfolio: PortfolioOut


class HistoryPointOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded_at: str
    total_value: float


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    added_at: str
    price: float | None = None
    opening_price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    direction: Literal["up", "down", "flat"] | None = None


class WatchlistAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)


class ChatActionOut(BaseModel):
    """Confirmation for one auto-executed LLM action (PLAN.md sec 8/9)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["trade", "watchlist_add", "watchlist_remove"]
    ticker: str
    success: bool
    error: str | None = None
    trade: TradeOut | None = None
    watchlist_entry: WatchlistItemOut | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    executed_actions: list[ChatActionOut] = Field(default_factory=list)


class HealthOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: str
    db: str
