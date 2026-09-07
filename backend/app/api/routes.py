"""REST routes for portfolio, watchlist, chat, and health (PLAN.md sec 8)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse

from app.chat.service import handle_chat_message
from app.db import get_connection
from app.runtime import get_price_cache
from app.services import portfolio as portfolio_service
from app.services import watchlist as watchlist_service

from .deps import get_db
from .schemas import (
    ChatRequest,
    ChatResponse,
    HealthOut,
    HistoryPointOut,
    PortfolioOut,
    TradeExecutionOut,
    TradeRequest,
    WatchlistAddRequest,
    WatchlistItemOut,
)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthOut)
async def health() -> Response:
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1 FROM users_profile LIMIT 1").fetchone()
        finally:
            conn.close()
        db_status = "ok"
    except Exception:
        db_status = "error"

    body = {"app": "ok", "db": db_status}
    code = status.HTTP_200_OK if db_status == "ok" else status.HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(status_code=code, content=body)


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(conn: sqlite3.Connection = Depends(get_db)) -> PortfolioOut:
    return portfolio_service.build_portfolio(conn, get_price_cache())


@router.post("/portfolio/trade", response_model=TradeExecutionOut)
async def post_trade(
    body: TradeRequest, conn: sqlite3.Connection = Depends(get_db)
) -> TradeExecutionOut:
    cache = get_price_cache()
    trade = portfolio_service.execute_trade(conn, cache, body.ticker, body.side, body.quantity)
    return TradeExecutionOut(trade=trade, portfolio=portfolio_service.build_portfolio(conn, cache))


@router.get("/portfolio/history", response_model=list[HistoryPointOut])
async def get_history(conn: sqlite3.Connection = Depends(get_db)) -> list[HistoryPointOut]:
    return [
        HistoryPointOut(
            recorded_at=snapshot.recorded_at,
            total_value=round(snapshot.total_value_cents / 100, 2),
        )
        for snapshot in portfolio_service.get_history(conn)
    ]


@router.get("/watchlist", response_model=list[WatchlistItemOut])
async def get_watchlist(conn: sqlite3.Connection = Depends(get_db)) -> list[WatchlistItemOut]:
    return watchlist_service.list_watchlist(conn, get_price_cache())


@router.post("/watchlist", response_model=WatchlistItemOut)
async def post_watchlist(
    body: WatchlistAddRequest, response: Response, conn: sqlite3.Connection = Depends(get_db)
) -> WatchlistItemOut:
    item, created = await watchlist_service.add_ticker(conn, get_price_cache(), body.ticker)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return item


@router.delete("/watchlist/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(ticker: str, conn: sqlite3.Connection = Depends(get_db)) -> Response:
    await watchlist_service.remove_ticker(conn, ticker.strip().upper())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/chat", response_model=ChatResponse)
async def post_chat(body: ChatRequest, conn: sqlite3.Connection = Depends(get_db)) -> ChatResponse:
    return await handle_chat_message(conn, get_price_cache(), body.message)
