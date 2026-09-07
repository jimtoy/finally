"""Fixtures for API tests: isolated temp DB and a deterministic price cache."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection, init_db
from app.db.connection import DB_PATH_ENV_VAR
from app.main import app as fastapi_app
from app.market import PriceCache
from app.runtime import get_price_cache, set_market_source


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "finally.db"
    monkeypatch.setenv(DB_PATH_ENV_VAR, str(path))
    conn = get_connection()
    try:
        init_db(conn)
    finally:
        conn.close()
    return path


@pytest.fixture
def cache(db_path: Path) -> Iterator[PriceCache]:
    """The process-wide cache, emptied before and after each test."""
    price_cache = get_price_cache()
    _clear(price_cache)
    set_market_source(None)
    yield price_cache
    _clear(price_cache)


def _clear(price_cache: PriceCache) -> None:
    for ticker in list(price_cache.get_all()):
        price_cache.remove(ticker)


@pytest.fixture
def client(cache: PriceCache) -> TestClient:
    """TestClient used without a `with` block, so lifespan (and therefore the
    simulator and snapshot task) never starts — tests drive the cache directly."""
    return TestClient(fastapi_app)


@pytest.fixture
def priced_client(client: TestClient, cache: PriceCache) -> TestClient:
    cache.update("AAPL", 100.00)
    cache.update("MSFT", 200.00)
    return client
