"""Prompt construction for the chat assistant (PLAN.md sec 9)."""

from __future__ import annotations

import sqlite3

from app.api.schemas import PortfolioOut, WatchlistItemOut
from app.db import repository as repo
from app.market import PriceCache
from app.services import portfolio as portfolio_service
from app.services import watchlist as watchlist_service

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated \
trading workstation. The portfolio is virtual money, so trades you request are executed \
immediately without confirmation.

Your job:
- Analyze portfolio composition, risk concentration, and P&L.
- Suggest trades with concrete reasoning grounded in the data you are given.
- Execute trades when the user asks for them or agrees to a suggestion.
- Manage the watchlist proactively when a ticker comes up in conversation.
- Be concise and data-driven. No filler, no disclaimers about not being a financial advisor.

Rules for the actions you request:
- Only share quantities are supported. Dollar/notional orders do not exist.
- At most 10 actions per response, and at most one action per ticker per array.
- Buys need enough cash; sells need enough shares. If you are unsure, ask instead of guessing.
- Always respond with valid JSON matching the required schema. `trades` and \
`watchlist_changes` may be omitted or empty when no action is needed."""


def _format_portfolio(portfolio: PortfolioOut) -> str:
    lines = [
        f"Cash: ${portfolio.cash_balance:,.2f}",
        f"Total portfolio value: ${portfolio.total_value:,.2f}",
        f"Total unrealized P&L: ${portfolio.unrealized_pnl:,.2f}",
    ]
    if not portfolio.positions:
        lines.append("Positions: none (all cash).")
        return "\n".join(lines)

    lines.append("Positions:")
    lines.extend(
        f"  {p.ticker}: {p.quantity:g} sh @ avg ${p.average_cost:,.2f}, "
        f"last ${p.current_price:,.2f}, value ${p.market_value:,.2f}, "
        f"P&L ${p.unrealized_pnl:,.2f} ({p.percent_change:+.2f}%)"
        for p in portfolio.positions
    )
    return "\n".join(lines)


def _format_watchlist(items: list[WatchlistItemOut]) -> str:
    if not items:
        return "Watchlist: empty."
    lines = ["Watchlist:"]
    for item in items:
        if item.price is None:
            lines.append(f"  {item.ticker}: no price yet")
        else:
            lines.append(
                f"  {item.ticker}: ${item.price:,.2f} ({item.change_percent:+.2f}% today)"
            )
    return "\n".join(lines)


def build_context(conn: sqlite3.Connection, cache: PriceCache) -> str:
    """Portfolio + watchlist snapshot injected into every chat prompt."""
    portfolio = portfolio_service.build_portfolio(conn, cache)
    watchlist = watchlist_service.list_watchlist(conn, cache)
    return f"{_format_portfolio(portfolio)}\n\n{_format_watchlist(watchlist)}"


def build_messages(conn: sqlite3.Connection, cache: PriceCache, message: str) -> list[dict]:
    """System + context + one prior message + the new user message (PLAN.md sec 9)."""
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current account state:\n\n{build_context(conn, cache)}"},
    ]

    prior = repo.get_most_recent_chat_message(conn)
    if prior is not None:
        messages.append({"role": prior.role, "content": prior.content})

    messages.append({"role": "user", "content": message})
    return messages


def build_corrective_messages(
    base_messages: list[dict], output_message: str, errors: list[str]
) -> list[dict]:
    """One follow-up turn telling the model which of its actions were rejected.

    The failures are deliberately never persisted to `chat_messages` — they only
    live in this prompt so the model can revise its wording for the user.
    """
    failures = "\n".join(f"- {error}" for error in errors)
    return [
        *base_messages,
        {"role": "assistant", "content": output_message},
        {
            "role": "system",
            "content": (
                "Some of the actions you requested were rejected and will NOT be retried:\n"
                f"{failures}\n\n"
                "Rewrite your `message` so the user knows what did not happen and why. "
                "Return empty `trades` and `watchlist_changes` — any actions you include "
                "now are ignored."
            ),
        },
    ]
