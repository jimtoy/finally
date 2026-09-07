"""Watchlist endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.market import PriceCache


class TestGetWatchlist:
    def test_returns_seeded_tickers(self, client: TestClient):
        body = client.get("/api/watchlist").json()

        assert [item["ticker"] for item in body][:3] == ["AAPL", "GOOGL", "MSFT"]

    def test_includes_session_change_from_the_cache(self, client: TestClient, cache: PriceCache):
        cache.update("AAPL", 100.00)  # opening price
        cache.update("AAPL", 105.00)

        item = next(i for i in client.get("/api/watchlist").json() if i["ticker"] == "AAPL")

        assert item["price"] == 105.0
        assert item["opening_price"] == 100.0
        assert item["change"] == 5.0
        assert item["change_percent"] == 5.0
        assert item["direction"] == "up"

    def test_unpriced_ticker_has_null_price(self, client: TestClient):
        item = next(i for i in client.get("/api/watchlist").json() if i["ticker"] == "AAPL")

        assert item["price"] is None


class TestAddTicker:
    def test_new_ticker_returns_201(self, client: TestClient):
        response = client.post("/api/watchlist", json={"ticker": "PYPL"})

        assert response.status_code == 201
        assert response.json()["ticker"] == "PYPL"

    def test_existing_ticker_returns_200(self, client: TestClient):
        client.post("/api/watchlist", json={"ticker": "PYPL"})

        response = client.post("/api/watchlist", json={"ticker": "PYPL"})

        assert response.status_code == 200

    def test_ticker_is_normalized(self, client: TestClient):
        response = client.post("/api/watchlist", json={"ticker": "  pypl  "})

        assert response.json()["ticker"] == "PYPL"
        assert "PYPL" in [item["ticker"] for item in client.get("/api/watchlist").json()]

    def test_blank_ticker_is_422(self, client: TestClient):
        response = client.post("/api/watchlist", json={"ticker": "  "})

        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"


class TestRemoveTicker:
    def test_removes_the_ticker(self, client: TestClient):
        response = client.delete("/api/watchlist/AAPL")

        assert response.status_code == 204
        assert "AAPL" not in [item["ticker"] for item in client.get("/api/watchlist").json()]

    def test_is_idempotent(self, client: TestClient):
        client.delete("/api/watchlist/AAPL")

        assert client.delete("/api/watchlist/AAPL").status_code == 204

    def test_unknown_ticker_returns_204(self, client: TestClient):
        assert client.delete("/api/watchlist/ZZZZ").status_code == 204

    def test_held_ticker_stays_priced(self, priced_client: TestClient, cache: PriceCache):
        priced_client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"}
        )

        priced_client.delete("/api/watchlist/AAPL")

        assert cache.get_price("AAPL") == 100.0
        position = priced_client.get("/api/portfolio").json()["positions"][0]
        assert position["current_price"] == 100.0
