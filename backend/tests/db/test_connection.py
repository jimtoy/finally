"""Tests for connection/path configuration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db.connection import DB_PATH_ENV_VAR, get_connection, get_db_path


def test_get_db_path_defaults_under_repo_db_dir(monkeypatch) -> None:
    monkeypatch.delenv(DB_PATH_ENV_VAR, raising=False)
    path = get_db_path()
    assert path.name == "finally.db"
    assert path.parent.name == "db"


def test_get_db_path_respects_env_var(monkeypatch, tmp_path: Path) -> None:
    custom_path = tmp_path / "custom" / "test.db"
    monkeypatch.setenv(DB_PATH_ENV_VAR, str(custom_path))
    path = get_db_path()
    assert path == custom_path
    assert custom_path.parent.is_dir()  # parent dirs created


def test_get_connection_creates_working_connection(tmp_path: Path) -> None:
    db_file = tmp_path / "sub" / "finally.db"
    conn = get_connection(db_file)
    try:
        assert isinstance(conn, sqlite3.Connection)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        row = conn.execute("SELECT * FROM t").fetchone()
        assert row["id"] == 1
        assert db_file.exists()
    finally:
        conn.close()


def test_get_connection_uses_row_factory(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "finally.db")
    try:
        assert conn.row_factory is sqlite3.Row
    finally:
        conn.close()
