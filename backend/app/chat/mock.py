"""Deterministic stand-in for the LLM when `LLM_MOCK=true` (PLAN.md sec 5/9).

The same user message always produces the same structured output, and no network
call is made. A tiny command grammar lets E2E tests drive real trades and
watchlist changes through the chat endpoint:

    "buy 5 AAPL" / "sell 2.5 shares of TSLA"   -> a trade action
    "watch PYPL" / "unwatch NFLX"              -> a watchlist action

Anything else yields a canned analysis reply with no actions.
"""

from __future__ import annotations

import re

from .schemas import LlmChatOutput, LlmTrade, LlmWatchlistChange

_TRADE_RE = re.compile(
    r"\b(buy|sell)\s+(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?([A-Za-z]{1,16})\b", re.IGNORECASE
)
_WATCHLIST_RE = re.compile(r"\b(unwatch|watch)\s+([A-Za-z]{1,16})\b", re.IGNORECASE)

NO_ACTION_MESSAGE = (
    "Mock mode is enabled, so this is a canned response. Your portfolio looks balanced; "
    "ask me to buy or sell shares and I will execute it."
)


def mock_response(message: str) -> LlmChatOutput:
    trades = [
        LlmTrade(ticker=ticker, side=side.lower(), quantity=float(quantity))
        for side, quantity, ticker in _TRADE_RE.findall(message)
    ]
    changes = [
        LlmWatchlistChange(ticker=ticker, action="remove" if verb.lower() == "unwatch" else "add")
        for verb, ticker in _WATCHLIST_RE.findall(message)
    ]

    if not trades and not changes:
        return LlmChatOutput(message=NO_ACTION_MESSAGE)

    described = [f"{t.side} {t.quantity:g} {t.ticker}" for t in trades]
    described += [f"{c.action} {c.ticker} on the watchlist" for c in changes]
    return LlmChatOutput(
        message="Done: " + ", ".join(described) + ".",
        trades=trades,
        watchlist_changes=changes,
    )


def mock_corrective_message(errors: list[str]) -> str:
    return "I could not complete every action: " + " ".join(errors)
