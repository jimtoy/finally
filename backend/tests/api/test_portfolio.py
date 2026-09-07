"""Portfolio, trade execution, and history endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import get_connection
from app.db import repository as repo
from app.market import PriceCache


def _buy(client: TestClient, ticker: str, quantity: float):
    return client.post(
        "/api/portfolio/trade", json={"ticker": ticker, "quantity": quantity, "side": "buy"}
    )


def _sell(client: TestClient, ticker: str, quantity: float):
    return client.post(
        "/api/portfolio/trade", json={"ticker": ticker, "quantity": quantity, "side": "sell"}
    )


class TestGetPortfolio:
    def test_fresh_portfolio_is_all_cash(self, priced_client: TestClient):
        body = priced_client.get("/api/portfolio").json()

        assert body == {
            "cash_balance": 10000.0,
            "total_value": 10000.0,
            "unrealized_pnl": 0.0,
            "positions": [],
        }

    def test_positions_are_priced_from_the_cache(
        self, priced_client: TestClient, cache: PriceCache
    ):
        _buy(priced_client, "AAPL", 10)
        cache.update("AAPL", 110.00)

        position = priced_client.get("/api/portfolio").json()["positions"][0]

        assert position["current_price"] == 110.0
        assert position["unrealized_pnl"] == 100.0
        assert position["percent_change"] == 10.0

    def test_total_value_includes_holdings(self, priced_client: TestClient, cache: PriceCache):
        _buy(priced_client, "AAPL", 10)  # $1,000 of cash becomes 10 shares
        cache.update("AAPL", 150.00)

        body = priced_client.get("/api/portfolio").json()

        assert body["cash_balance"] == 9000.0
        assert body["total_value"] == 10500.0
        assert body["unrealized_pnl"] == 500.0


class TestTradeExecution:
    def test_buy_debits_cash_and_creates_position(self, priced_client: TestClient):
        response = _buy(priced_client, "AAPL", 5)

        assert response.status_code == 200
        body = response.json()
        assert body["trade"]["ticker"] == "AAPL"
        assert body["trade"]["side"] == "buy"
        assert body["trade"]["price"] == 100.0
        assert body["portfolio"]["cash_balance"] == 9500.0
        assert body["portfolio"]["positions"][0]["quantity"] == 5

    def test_ticker_is_normalized(self, priced_client: TestClient):
        response = _buy(priced_client, " aapl ", 1)

        assert response.json()["trade"]["ticker"] == "AAPL"

    def test_sell_credits_cash_and_reduces_position(self, priced_client: TestClient):
        _buy(priced_client, "AAPL", 10)

        body = _sell(priced_client, "AAPL", 4).json()

        assert body["portfolio"]["cash_balance"] == 9400.0
        assert body["portfolio"]["positions"][0]["quantity"] == 6

    def test_selling_entire_position_removes_it(self, priced_client: TestClient):
        _buy(priced_client, "AAPL", 10)

        body = _sell(priced_client, "AAPL", 10).json()

        assert body["portfolio"]["positions"] == []
        assert body["portfolio"]["cash_balance"] == 10000.0

    def test_weighted_average_cost(self, priced_client: TestClient, cache: PriceCache):
        _buy(priced_client, "AAPL", 10)  # 10 @ $100
        cache.update("AAPL", 200.00)
        body = _buy(priced_client, "AAPL", 10)  # 10 @ $200

        position = body.json()["portfolio"]["positions"][0]
        assert position["quantity"] == 20
        assert position["average_cost"] == 150.0

    def test_selling_does_not_change_average_cost(self, priced_client: TestClient,
                                                  cache: PriceCache):
        _buy(priced_client, "AAPL", 10)
        cache.update("AAPL", 250.00)

        position = _sell(priced_client, "AAPL", 5).json()["portfolio"]["positions"][0]
        assert position["average_cost"] == 100.0

    def test_fractional_quantities_supported(self, priced_client: TestClient):
        body = _buy(priced_client, "AAPL", 2.5).json()

        assert body["trade"]["quantity"] == 2.5
        assert body["portfolio"]["cash_balance"] == 9750.0

    def test_insufficient_funds_rejected(self, priced_client: TestClient):
        response = _buy(priced_client, "AAPL", 1000)

        assert response.status_code == 400
        assert response.json()["code"] == "insufficient_funds"

    def test_overselling_rejected(self, priced_client: TestClient):
        _buy(priced_client, "AAPL", 5)

        response = _sell(priced_client, "AAPL", 6)

        assert response.status_code == 400
        assert response.json()["code"] == "insufficient_shares"

    def test_selling_unheld_ticker_rejected(self, priced_client: TestClient):
        response = _sell(priced_client, "MSFT", 1)

        assert response.status_code == 400
        assert response.json()["code"] == "insufficient_shares"

    def test_unpriced_ticker_rejected(self, priced_client: TestClient):
        response = _buy(priced_client, "ZZZZ", 1)

        assert response.status_code == 400
        assert response.json()["code"] == "price_unavailable"

    def test_failed_trade_leaves_state_untouched(self, priced_client: TestClient, db_path):
        _buy(priced_client, "AAPL", 1000)

        conn = get_connection()
        try:
            assert repo.get_cash_balance_cents(conn) == 1_000_000
            assert repo.get_positions(conn) == []
            assert repo.get_trades(conn) == []
        finally:
            conn.close()

    def test_trade_records_a_snapshot(self, priced_client: TestClient, db_path):
        before = len(priced_client.get("/api/portfolio/history").json())

        _buy(priced_client, "AAPL", 1)

        assert len(priced_client.get("/api/portfolio/history").json()) == before + 1


class TestTradeValidation:
    def test_zero_quantity_is_422(self, priced_client: TestClient):
        response = _buy(priced_client, "AAPL", 0)

        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"

    def test_negative_quantity_is_422(self, priced_client: TestClient):
        assert _buy(priced_client, "AAPL", -3).status_code == 422

    def test_unknown_side_is_422(self, priced_client: TestClient):
        response = priced_client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "short"}
        )

        assert response.status_code == 422

    def test_missing_field_is_422(self, priced_client: TestClient):
        assert priced_client.post("/api/portfolio/trade", json={"ticker": "AAPL"}).status_code == 422

    def test_blank_ticker_is_422(self, priced_client: TestClient):
        assert _buy(priced_client, "   ", 1).status_code == 422


class TestHistory:
    def test_seeded_snapshot_is_returned(self, priced_client: TestClient):
        history = priced_client.get("/api/portfolio/history").json()

        assert history[0]["total_value"] == 10000.0
        assert "recorded_at" in history[0]

    def test_history_is_ascending(self, priced_client: TestClient):
        _buy(priced_client, "AAPL", 1)
        _buy(priced_client, "AAPL", 1)

        history = priced_client.get("/api/portfolio/history").json()

        assert history == sorted(history, key=lambda point: point["recorded_at"])
