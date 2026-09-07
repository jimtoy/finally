"""Shared fixtures for db tests."""

from __future__ import annotations

import sqlite3

import pytest

from app.db.init_db import init_db


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An isolated in-memory SQLite connection, schema created but not seeded."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


@pytest.fixture
def seeded_conn(conn: sqlite3.Connection) -> sqlite3.Connection:
    """An isolated in-memory SQLite connection with schema created and seeded."""
    init_db(conn)
    return conn
