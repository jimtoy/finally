"""Tests for the SSE price stream generator."""

import json
from types import SimpleNamespace

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class FakeRequest:
    """Minimal stand-in for a FastAPI Request, driving disconnects on demand."""

    def __init__(self, on_check=None):
        self.client = SimpleNamespace(host="127.0.0.1")
        self._on_check = on_check
        self.calls = 0

    async def is_disconnected(self) -> bool:
        self.calls += 1
        if self._on_check is not None:
            return self._on_check(self.calls)
        return False


@pytest.mark.asyncio
class TestGenerateEvents:
    """Unit tests for _generate_events."""

    async def test_retry_directive_sent_first(self):
        """First yielded chunk is always the SSE retry directive."""
        cache = PriceCache()
        request = FakeRequest(on_check=lambda n: True)  # disconnect immediately

        events = [event async for event in _generate_events(cache, request, interval=0)]

        assert events[0] == "retry: 1000\n\n"

    async def test_snapshot_sent_on_connect(self):
        """A snapshot event with all cached tickers is sent immediately."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)
        request = FakeRequest(on_check=lambda n: True)  # disconnect right after snapshot

        events = [event async for event in _generate_events(cache, request, interval=0)]

        snapshot_events = [e for e in events if e.startswith("event: snapshot")]
        assert len(snapshot_events) == 1

        payload = json.loads(snapshot_events[0].split("data: ", 1)[1])
        assert set(payload.keys()) == {"AAPL", "GOOGL"}
        assert payload["AAPL"]["price"] == 190.00
        assert payload["AAPL"]["opening_price"] == 190.00

    async def test_no_snapshot_event_when_cache_empty(self):
        """No snapshot event is sent when nothing is cached yet."""
        cache = PriceCache()
        request = FakeRequest(on_check=lambda n: True)

        events = [event async for event in _generate_events(cache, request, interval=0)]

        assert not any(e.startswith("event: snapshot") for e in events)

    async def test_price_event_emitted_on_change(self):
        """A per-ticker price event is emitted when its price changes."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        def on_check(n: int) -> bool:
            if n == 1:
                cache.update("AAPL", 191.00)
                return False
            return True  # disconnect on the second check

        request = FakeRequest(on_check=on_check)
        events = [event async for event in _generate_events(cache, request, interval=0)]

        price_events = [e for e in events if e.startswith("event: price")]
        assert len(price_events) == 1

        payload = json.loads(price_events[0].split("data: ", 1)[1])
        assert payload["ticker"] == "AAPL"
        assert payload["price"] == 191.00
        assert payload["previous_price"] == 190.00
        assert payload["opening_price"] == 190.00
        assert payload["direction"] == "up"

    async def test_no_price_event_when_unchanged(self):
        """No price event is emitted if no ticker's price actually changed."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        request = FakeRequest(on_check=lambda n: n > 2)  # a couple of idle checks first
        events = [event async for event in _generate_events(cache, request, interval=0)]

        assert not any(e.startswith("event: price") for e in events)

    async def test_stops_on_disconnect(self):
        """The generator stops yielding once the client disconnects."""
        cache = PriceCache()
        request = FakeRequest(on_check=lambda n: n > 1)

        events = [event async for event in _generate_events(cache, request, interval=0)]

        # Exactly one disconnect check happened before it broke out (n=2 -> True)
        assert request.calls == 2
        assert len(events) >= 1


class TestCreateStreamRouter:
    """Sanity checks for the router factory."""

    def test_registers_prices_route(self):
        """The factory registers a GET /api/stream/prices route."""
        cache = PriceCache()
        router = create_stream_router(cache)

        paths = {route.path for route in router.routes}
        assert "/api/stream/prices" in paths
