"""Structured-output schema the LLM must respond with (PLAN.md sec 9).

Kept separate from `app.api.schemas` because this is the model→backend contract,
not the backend→browser one. `extra="forbid"` is what rejects unknown fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import Side, Ticker


class LlmTrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker
    side: Side
    quantity: float


class LlmWatchlistChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker
    action: Literal["add", "remove"]


class LlmChatOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    trades: list[LlmTrade] = Field(default_factory=list)
    watchlist_changes: list[LlmWatchlistChange] = Field(default_factory=list)
