"""Health, chat stub, SSE wiring, and static-fallback tests."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi.testclient import TestClient

from app import main
from app.main import record_snapshot_now
from app.market import PriceCache


class TestHealth:
    def test_reports_app_and_db_ok(self, client: TestClient):
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"app": "ok", "db": "ok"}

    def test_reports_db_error_when_unreachable(self, client: TestClient, monkeypatch, tmp_path):
        from app.db.connection import DB_PATH_ENV_VAR

        monkeypatch.setenv(DB_PATH_ENV_VAR, str(tmp_path / "missing" / "empty.db"))

        response = client.get("/api/health")

        assert response.status_code == 500
        assert response.json() == {"app": "ok", "db": "error"}


class TestChat:
    def test_reports_unconfigured_without_a_key(self, client: TestClient, monkeypatch):
        from app.chat.service import UNAVAILABLE_MESSAGE

        monkeypatch.delenv("LLM_MOCK", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        response = client.post("/api/chat", json={"message": "how am I doing?"})

        assert response.status_code == 200
        assert response.json() == {"message": UNAVAILABLE_MESSAGE, "executed_actions": []}

    def test_mock_mode_executes_a_trade(self, priced_client: TestClient, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")

        response = priced_client.post("/api/chat", json={"message": "buy 2 AAPL"})

        assert response.status_code == 200
        actions = response.json()["executed_actions"]
        assert [(a["type"], a["ticker"], a["success"]) for a in actions] == [
            ("trade", "AAPL", True)
        ]

    def test_empty_message_is_422(self, client: TestClient):
        assert client.post("/api/chat", json={"message": ""}).status_code == 422


class TestPriceStream:
    # The event generator itself is covered in tests/market/test_stream.py; a
    # live request here would never finish, since TestClient never disconnects.
    def test_stream_route_is_registered(self, client: TestClient):
        paths = {route.path for route in client.app.routes}

        assert "/api/stream/prices" in paths

    def test_stream_reads_the_shared_cache(self, cache: PriceCache):
        from app.runtime import get_price_cache

        cache.update("AAPL", 190.00)

        assert get_price_cache().get_price("AAPL") == 190.0


class TestSnapshotLoop:
    async def test_records_a_snapshot_from_a_worker_thread(
        self, client: TestClient, cache: PriceCache
    ):
        # Touch the DB from the event-loop thread first: the periodic loop used
        # to hand that connection to a worker thread, which sqlite3 rejects.
        cache.update("AAPL", 100.00)
        before = len(client.get("/api/portfolio/history").json())

        await asyncio.to_thread(record_snapshot_now)

        assert len(client.get("/api/portfolio/history").json()) == before + 1

    async def test_loop_keeps_recording(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(main, "SNAPSHOT_INTERVAL_SECONDS", 0.01)
        before = len(client.get("/api/portfolio/history").json())

        task = asyncio.create_task(main._snapshot_loop())
        await asyncio.sleep(0.1)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        assert len(client.get("/api/portfolio/history").json()) > before


class TestStaticFallback:
    def test_unknown_route_returns_json_404_without_a_build(self, client: TestClient):
        response = client.get("/some/frontend/route")

        assert response.status_code == 404
        assert response.json()["code"] == "not_found"

    def test_serves_the_index_when_a_build_exists(self, client: TestClient, monkeypatch, tmp_path):
        from app.main import STATIC_DIR_ENV_VAR

        (tmp_path / "index.html").write_text("<html>FinAlly</html>", encoding="utf-8")
        monkeypatch.setenv(STATIC_DIR_ENV_VAR, str(tmp_path))

        response = client.get("/some/frontend/route")

        assert response.status_code == 200
        assert "FinAlly" in response.text

    def test_api_routes_are_not_shadowed_by_static(self, client: TestClient, monkeypatch, tmp_path):
        from app.main import STATIC_DIR_ENV_VAR

        (tmp_path / "index.html").write_text("<html>FinAlly</html>", encoding="utf-8")
        monkeypatch.setenv(STATIC_DIR_ENV_VAR, str(tmp_path))

        assert client.get("/api/health").json() == {"app": "ok", "db": "ok"}
