"""SQLite connection management.

The database file path is configurable via the FINALLY_DB_PATH environment
variable so it can point at /app/db/finally.db in Docker. When unset, it
defaults to the project's top-level db/finally.db (see PLAN.md sec 4), resolved
relative to this file so it works regardless of the current working directory.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# backend/app/db/connection.py -> parents[2] is backend/, parents[3] is the repo root.
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "db" / "finally.db"

DB_PATH_ENV_VAR = "FINALLY_DB_PATH"


def get_db_path() -> Path:
    """Return the configured database file path, creating its parent dir if needed."""
    raw_path = os.environ.get(DB_PATH_ENV_VAR, "").strip()
    path = Path(raw_path) if raw_path else _DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a new SQLite connection with sensible defaults.

    Each call returns a new connection — sqlite3 connections are not
    thread-safe for concurrent use, so callers should open one per request/task
    (or per thread) rather than sharing a single connection.
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
