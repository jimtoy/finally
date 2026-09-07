"""FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator

from app.db import get_connection


async def get_db() -> AsyncIterator[sqlite3.Connection]:
    """A fresh connection per request — sqlite3 connections are not thread-safe."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
