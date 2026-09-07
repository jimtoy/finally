"""FinAlly FastAPI application (PLAN.md sec 3, 8, 11)."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from app.api.errors import register_error_handlers
from app.api.routes import router as api_router
from app.db import get_connection, init_db
from app.db import repository as repo
from app.market import create_market_data_source, create_stream_router
from app.runtime import get_price_cache, set_market_source
from app.services import portfolio as portfolio_service

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 30
STATIC_DIR_ENV_VAR = "FINALLY_STATIC_DIR"
_DEFAULT_STATIC_DIR = Path(__file__).resolve().parent / "static"


def get_static_dir() -> Path:
    raw = os.environ.get(STATIC_DIR_ENV_VAR, "").strip()
    return Path(raw) if raw else _DEFAULT_STATIC_DIR


def record_snapshot_now() -> None:
    """Record one portfolio snapshot, opening its own connection.

    Runs in a worker thread, so the connection must be created here: a sqlite3
    connection may only be used on the thread that created it.
    """
    conn = get_connection()
    try:
        portfolio_service.record_snapshot(conn, get_price_cache())
    finally:
        conn.close()


async def _snapshot_loop() -> None:
    """Record the portfolio's total value every 30 seconds (PLAN.md sec 7)."""
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(record_snapshot_now)
        except Exception:
            logger.exception("Portfolio snapshot failed")


def _startup_tickers() -> list[str]:
    conn = get_connection()
    try:
        init_db(conn)
        watched = [entry.ticker for entry in repo.get_watchlist(conn)]
        held = [position.ticker for position in repo.get_positions(conn)]
    finally:
        conn.close()
    # The cache covers the union of the watchlist and any held ticker (PLAN.md sec 6).
    return sorted(set(watched) | set(held))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    tickers = _startup_tickers()

    cache = get_price_cache()
    source = create_market_data_source(cache)
    await source.start(tickers)
    set_market_source(source)

    snapshot_task = asyncio.create_task(_snapshot_loop(), name="portfolio-snapshots")
    try:
        yield
    finally:
        snapshot_task.cancel()
        with suppress(asyncio.CancelledError):
            await snapshot_task
        await source.stop()
        set_market_source(None)


def create_app(*, use_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title="FinAlly",
        description="AI Trading Workstation API",
        version="0.1.0",
        lifespan=lifespan if use_lifespan else None,
    )

    register_error_handlers(app)
    app.include_router(api_router)
    app.include_router(create_stream_router(get_price_cache()))

    _mount_static(app)
    return app


def _resolve_static_file(full_path: str) -> Path | None:
    """Map a request path to a file inside the static dir, or None."""
    static_dir = get_static_dir()
    if not static_dir.is_dir():
        return None

    root = static_dir.resolve()
    candidates = [full_path, f"{full_path}.html", f"{full_path}/index.html"] if full_path else []
    for candidate in [*candidates, "index.html"]:
        target = (root / candidate).resolve()
        if target.is_relative_to(root) and target.is_file():
            return target
    return None


def _mount_static(app: FastAPI) -> None:
    """Serve the Next.js export, falling back to its index for frontend routes.

    Registered after the API routes so /api/* always wins. The build output does
    not exist during backend development or in tests, so a missing static dir
    just yields a JSON 404 instead of a server error (PLAN.md sec 11).
    """

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def serve_frontend(full_path: str) -> FileResponse | JSONResponse:
        target = _resolve_static_file(full_path)
        if target is not None:
            return FileResponse(target)
        return JSONResponse(
            status_code=404,
            content={"detail": "Frontend build not available.", "code": "not_found"},
        )


app = create_app()
