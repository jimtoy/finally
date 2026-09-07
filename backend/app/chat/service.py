"""Chat request handling (PLAN.md sec 9).

The route calls only `handle_chat_message`. It builds portfolio context, asks the
LLM for a structured response, auto-executes the actions it requested, and
persists the final assistant message.

Two rules are ours to define where the plan leaves them open:

* **Action cap** — trades then watchlist changes, in response order; anything
  past the tenth action is rejected rather than executed.
* **Conflict** — at most one action per ticker per category in a single
  response. The first mention of a ticker executes; later trades for that same
  ticker, or later watchlist changes for it, are rejected as conflicting. This
  catches "buy AAPL then sell AAPL" and "add PYPL then remove PYPL" without
  needing to model intent.

Rejected actions are never persisted. They are fed back into exactly one
corrective LLM call so the assistant can explain itself, and are never retried.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass

from app.api.errors import ApiError
from app.api.schemas import ChatActionOut, ChatResponse
from app.db import repository as repo
from app.market import PriceCache
from app.services import portfolio as portfolio_service
from app.services import watchlist as watchlist_service

from . import mock, prompts
from .llm import LlmError, complete, get_api_key, is_mock_enabled
from .schemas import LlmChatOutput

logger = logging.getLogger(__name__)

MAX_ACTIONS = 10

UNAVAILABLE_MESSAGE = (
    "AI chat is not configured. Set OPENROUTER_API_KEY in your .env file (or set "
    "LLM_MOCK=true for offline mock responses) and restart the app."
)
FALLBACK_MESSAGE = (
    "I could not get a usable response from the AI provider just now. "
    "Everything else in the workstation is still working — please try again."
)


@dataclass(frozen=True)
class _PlannedAction:
    type: str  # "trade" | "watchlist_add" | "watchlist_remove"
    ticker: str
    side: str | None = None
    quantity: float | None = None

    @property
    def category(self) -> str:
        return "trade" if self.type == "trade" else "watchlist"


def _plan(output: LlmChatOutput) -> list[_PlannedAction]:
    actions = [
        _PlannedAction(type="trade", ticker=t.ticker, side=t.side, quantity=t.quantity)
        for t in output.trades
    ]
    actions += [
        _PlannedAction(type=f"watchlist_{c.action}", ticker=c.ticker)
        for c in output.watchlist_changes
    ]
    return actions


def _failed(action: _PlannedAction, error: str) -> ChatActionOut:
    return ChatActionOut(type=action.type, ticker=action.ticker, success=False, error=error)


async def _execute_one(
    conn: sqlite3.Connection, cache: PriceCache, action: _PlannedAction
) -> ChatActionOut:
    try:
        if action.type == "trade":
            trade = portfolio_service.execute_trade(
                conn, cache, action.ticker, action.side, action.quantity
            )
            return ChatActionOut(
                type="trade", ticker=action.ticker, success=True, trade=trade
            )
        if action.type == "watchlist_add":
            entry, _created = await watchlist_service.add_ticker(conn, cache, action.ticker)
            return ChatActionOut(
                type="watchlist_add", ticker=action.ticker, success=True, watchlist_entry=entry
            )
        await watchlist_service.remove_ticker(conn, action.ticker)
        return ChatActionOut(type="watchlist_remove", ticker=action.ticker, success=True)
    except ApiError as exc:
        return _failed(action, exc.detail)


async def _execute_all(
    conn: sqlite3.Connection, cache: PriceCache, output: LlmChatOutput
) -> list[ChatActionOut]:
    results: list[ChatActionOut] = []
    seen: set[tuple[str, str]] = set()

    for index, action in enumerate(_plan(output)):
        if index >= MAX_ACTIONS:
            results.append(
                _failed(
                    action,
                    f"Only the first {MAX_ACTIONS} actions in a response are executed; "
                    f"this {action.type} was skipped.",
                )
            )
            continue

        key = (action.category, action.ticker)
        if key in seen:
            results.append(
                _failed(
                    action,
                    f"Conflicting action: {action.ticker} already has a "
                    f"{action.category} action in this response.",
                )
            )
            continue
        seen.add(key)

        results.append(await _execute_one(conn, cache, action))

    return results


def _describe_failures(actions: list[ChatActionOut]) -> list[str]:
    return [
        f"{action.type} {action.ticker}: {action.error}"
        for action in actions
        if not action.success and action.error
    ]


async def _final_message(
    base_messages: list[dict], output: LlmChatOutput, actions: list[ChatActionOut]
) -> str:
    """The assistant's message, revised once if any action was rejected."""
    errors = _describe_failures(actions)
    if not errors:
        return output.message

    if is_mock_enabled():
        return mock.mock_corrective_message(errors)

    try:
        corrected = await complete(
            prompts.build_corrective_messages(base_messages, output.message, errors)
        )
    except LlmError:
        logger.warning("Corrective LLM call failed; using deterministic fallback message")
        return output.message + " However, some actions could not be completed: " + " ".join(errors)
    return corrected.message


def _persist(
    conn: sqlite3.Connection, message: str, reply: str, actions: list[ChatActionOut]
) -> None:
    succeeded = [action for action in actions if action.success]
    payload = (
        json.dumps([action.model_dump(mode="json") for action in succeeded]) if succeeded else None
    )
    repo.insert_chat_message(conn, "user", message)
    repo.insert_chat_message(conn, "assistant", reply, actions=payload)


async def handle_chat_message(
    conn: sqlite3.Connection, cache: PriceCache, message: str
) -> ChatResponse:
    """Produce the assistant's reply and the actions executed on the user's behalf."""
    mock_mode = is_mock_enabled()
    if not mock_mode and not get_api_key():
        return ChatResponse(message=UNAVAILABLE_MESSAGE, executed_actions=[])

    try:
        base_messages = prompts.build_messages(conn, cache, message)

        if mock_mode:
            output = mock.mock_response(message)
        else:
            try:
                output = await complete(base_messages)
            except LlmError:
                logger.warning("Chat completion failed", exc_info=True)
                _persist(conn, message, FALLBACK_MESSAGE, [])
                return ChatResponse(message=FALLBACK_MESSAGE, executed_actions=[])

        actions = await _execute_all(conn, cache, output)
        reply = await _final_message(base_messages, output, actions)
        _persist(conn, message, reply, actions)
        return ChatResponse(message=reply, executed_actions=actions)
    except Exception as exc:  # noqa: BLE001 - PLAN.md sec 8: chat failures surface as 502
        logger.exception("Unexpected failure handling chat message")
        raise ApiError(
            "The AI assistant failed to handle that message.", "chat_failed", 502
        ) from exc
