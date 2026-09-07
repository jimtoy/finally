"""Chat orchestration: mock mode, action execution, corrective flow, persistence."""

from __future__ import annotations

import json
import sqlite3

import pytest

from app.api.errors import ApiError
from app.chat import service
from app.chat.llm import LlmError
from app.chat.schemas import LlmChatOutput
from app.chat.service import handle_chat_message
from app.db import repository as repo
from app.market import PriceCache


def _stub_completion(monkeypatch: pytest.MonkeyPatch, *outputs: LlmChatOutput | Exception):
    """Queue the responses successive LLM calls return, and record the prompts."""
    calls: list[list[dict]] = []
    queue = list(outputs)

    async def _complete(messages: list[dict]) -> LlmChatOutput:
        calls.append(messages)
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(service, "complete", _complete)
    return calls


@pytest.fixture
def live_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


# --- configuration paths ---------------------------------------------------


async def test_missing_api_key_returns_unavailable(conn: sqlite3.Connection, cache: PriceCache):
    response = await handle_chat_message(conn, cache, "how am I doing?")

    assert response.message == service.UNAVAILABLE_MESSAGE
    assert response.executed_actions == []
    assert repo.get_chat_messages(conn) == []


async def test_mock_mode_needs_no_api_key(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("LLM_MOCK", "true")

    response = await handle_chat_message(conn, cache, "how am I doing?")

    assert response.message != service.UNAVAILABLE_MESSAGE
    assert response.executed_actions == []


async def test_mock_mode_is_deterministic(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("LLM_MOCK", "1")

    first = await handle_chat_message(conn, cache, "what should I do?")
    second = await handle_chat_message(conn, cache, "what should I do?")

    assert first.message == second.message


async def test_mock_mode_executes_parsed_commands(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("LLM_MOCK", "true")

    response = await handle_chat_message(conn, cache, "please buy 5 aapl and watch pypl")

    assert [(a.type, a.ticker, a.success) for a in response.executed_actions] == [
        ("trade", "AAPL", True),
        ("watchlist_add", "PYPL", True),
    ]
    assert repo.get_position(conn, "AAPL").quantity == 5
    assert repo.get_watchlist_entry(conn, "PYPL") is not None


# --- structured output parsing ---------------------------------------------


async def test_valid_structured_output_executes_actions(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate(
            {
                "message": "Bought some Apple.",
                "trades": [{"ticker": " aapl ", "side": "buy", "quantity": 2}],
                "watchlist_changes": [{"ticker": "pypl", "action": "add"}],
            }
        ),
    )

    response = await handle_chat_message(conn, cache, "buy apple")

    assert response.message == "Bought some Apple."
    trade_action, watch_action = response.executed_actions
    assert trade_action.ticker == "AAPL"
    assert trade_action.trade.price == 100.0
    assert watch_action.type == "watchlist_add"
    assert watch_action.watchlist_entry.ticker == "PYPL"


async def test_output_without_action_arrays_is_valid():
    output = LlmChatOutput.model_validate({"message": "Just chatting."})

    assert output.trades == []
    assert output.watchlist_changes == []


async def test_unknown_fields_are_rejected():
    with pytest.raises(Exception):
        LlmChatOutput.model_validate({"message": "hi", "orders": []})


async def test_provider_failure_returns_fallback_message(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    _stub_completion(monkeypatch, LlmError("boom"))

    response = await handle_chat_message(conn, cache, "hello")

    assert response.message == service.FALLBACK_MESSAGE
    assert response.executed_actions == []
    assert repo.get_most_recent_chat_message(conn).content == service.FALLBACK_MESSAGE


# --- corrective call --------------------------------------------------------


async def test_failed_trade_triggers_one_corrective_call(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    calls = _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate(
            {
                "message": "Buying 1000 Apple.",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1000}],
            }
        ),
        LlmChatOutput(message="You do not have enough cash for 1000 AAPL."),
    )

    response = await handle_chat_message(conn, cache, "buy 1000 apple")

    assert len(calls) == 2
    assert "insufficient" in calls[1][-1]["content"].lower()
    assert response.message == "You do not have enough cash for 1000 AAPL."
    assert response.executed_actions[0].success is False
    assert repo.get_position(conn, "AAPL") is None


async def test_failed_corrective_call_falls_back_deterministically(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate(
            {
                "message": "Selling Tesla.",
                "trades": [{"ticker": "TSLA", "side": "sell", "quantity": 1}],
            }
        ),
        LlmError("provider down"),
    )

    response = await handle_chat_message(conn, cache, "sell tesla")

    assert response.message.startswith("Selling Tesla.")
    assert "could not be completed" in response.message
    assert response.executed_actions[0].error


async def test_no_corrective_call_when_everything_succeeds(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    calls = _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate(
            {
                "message": "Done.",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}],
            }
        ),
    )

    await handle_chat_message(conn, cache, "buy apple")

    assert len(calls) == 1


# --- caps and conflicts -----------------------------------------------------


async def test_actions_past_the_cap_are_rejected(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    changes = [{"ticker": f"TK{i}", "action": "add"} for i in range(12)]
    _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate({"message": "Adding a lot.", "watchlist_changes": changes}),
        LlmChatOutput(message="I could only add ten."),
    )

    response = await handle_chat_message(conn, cache, "add twelve tickers")

    assert len(response.executed_actions) == 12
    assert all(a.success for a in response.executed_actions[:10])
    assert [a.success for a in response.executed_actions[10:]] == [False, False]
    assert repo.get_watchlist_entry(conn, "TK11") is None


async def test_conflicting_trades_for_one_ticker_are_rejected(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate(
            {
                "message": "Round trip.",
                "trades": [
                    {"ticker": "AAPL", "side": "buy", "quantity": 1},
                    {"ticker": "AAPL", "side": "sell", "quantity": 1},
                ],
            }
        ),
        LlmChatOutput(message="Only the buy went through."),
    )

    response = await handle_chat_message(conn, cache, "round trip apple")

    first, second = response.executed_actions
    assert first.success is True
    assert second.success is False
    assert "Conflicting action" in second.error
    assert repo.get_position(conn, "AAPL").quantity == 1


async def test_conflicting_watchlist_changes_are_rejected(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate(
            {
                "message": "Toggling.",
                "watchlist_changes": [
                    {"ticker": "PYPL", "action": "add"},
                    {"ticker": "PYPL", "action": "remove"},
                ],
            }
        ),
        LlmChatOutput(message="Added PYPL only."),
    )

    response = await handle_chat_message(conn, cache, "toggle pypl")

    assert [a.success for a in response.executed_actions] == [True, False]
    assert repo.get_watchlist_entry(conn, "PYPL") is not None


async def test_trade_and_watchlist_for_same_ticker_do_not_conflict(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate(
            {
                "message": "Buying and watching.",
                "trades": [{"ticker": "MSFT", "side": "buy", "quantity": 1}],
                "watchlist_changes": [{"ticker": "MSFT", "action": "add"}],
            }
        ),
    )

    response = await handle_chat_message(conn, cache, "buy and watch msft")

    assert all(a.success for a in response.executed_actions)


# --- persistence ------------------------------------------------------------


async def test_successful_actions_are_persisted_and_failures_are_not(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    _stub_completion(
        monkeypatch,
        LlmChatOutput.model_validate(
            {
                "message": "Two orders.",
                "trades": [
                    {"ticker": "AAPL", "side": "buy", "quantity": 1},
                    {"ticker": "MSFT", "side": "sell", "quantity": 5},
                ],
            }
        ),
        LlmChatOutput(message="Bought AAPL; the MSFT sell failed."),
    )

    await handle_chat_message(conn, cache, "buy apple and sell microsoft")

    user_message, assistant_message = repo.get_chat_messages(conn)
    assert user_message.role == "user"
    assert user_message.actions is None
    assert assistant_message.content == "Bought AAPL; the MSFT sell failed."

    persisted = json.loads(assistant_message.actions)
    assert [action["ticker"] for action in persisted] == ["AAPL"]
    assert all(action["success"] for action in persisted)


async def test_prior_message_is_included_in_the_prompt(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    repo.insert_chat_message(conn, "assistant", "Earlier reply about NVDA.")
    calls = _stub_completion(monkeypatch, LlmChatOutput(message="Sure."))

    await handle_chat_message(conn, cache, "and now?")

    assert calls[0][-2]["content"] == "Earlier reply about NVDA."
    assert calls[0][-1]["content"] == "and now?"


async def test_unexpected_failure_surfaces_as_502(
    conn: sqlite3.Connection, cache: PriceCache, monkeypatch: pytest.MonkeyPatch, live_key: None
):
    def _broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("context builder exploded")

    monkeypatch.setattr(service.prompts, "build_messages", _broken)

    with pytest.raises(ApiError) as excinfo:
        await handle_chat_message(conn, cache, "hello")

    assert excinfo.value.status_code == 502
    assert excinfo.value.code == "chat_failed"
