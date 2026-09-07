"""Fixtures for chat tests: isolated DB, deterministic prices, no network.

`no_network` is autouse so a stray real completion fails loudly instead of
hitting OpenRouter, whatever LLM_MOCK/OPENROUTER_API_KEY are set to locally.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.chat import llm
from app.db import get_connection, init_db
from app.db.connection import DB_PATH_ENV_VAR
from app.market import PriceCache
from app.runtime import set_market_source


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    set_market_source(None)

    async def _blocked(messages: list[dict]) -> None:
        raise AssertionError("Unexpected LLM call in tests")

    monkeypatch.setattr(llm, "complete", _blocked)
    monkeypatch.setattr("app.chat.service.complete", _blocked)


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sqlite3.Connection]:
    monkeypatch.setenv(DB_PATH_ENV_VAR, str(tmp_path / "finally.db"))
    connection = get_connection()
    init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def cache() -> PriceCache:
    price_cache = PriceCache()
    price_cache.update("AAPL", 100.00)
    price_cache.update("MSFT", 200.00)
    return price_cache
