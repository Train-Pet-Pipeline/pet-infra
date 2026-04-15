"""Database access base class for all pet-pipeline repos.

Usage:
    from pet_infra.store import BaseStore

    class MyStore(BaseStore):
        def _init_schema(self) -> None:
            self._conn.execute("CREATE TABLE IF NOT EXISTS ...")
            self._conn.commit()

    with MyStore(db_path="data.db") as store:
        store.execute_commit("INSERT INTO ...", (val,))
        row = store.fetch_one("SELECT ...", (key,))
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class BaseStore:
    """SQLite base store with WAL mode, foreign keys, and transaction support.

    Subclasses must implement _init_schema() to create their tables.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """Initialize the store.

        Args:
            db_path: Path to SQLite file, or ":memory:" for in-memory DB.
        """
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=wal")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables and apply migrations. Subclasses must override."""
        raise NotImplementedError

    def __enter__(self) -> BaseStore:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and close connection."""
        self.close()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Context manager for explicit transactions with rollback on error."""
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def execute_commit(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute SQL and immediately commit.

        Args:
            sql: SQL statement.
            params: Query parameters.

        Returns:
            The cursor after execution.
        """
        cursor = self._conn.execute(sql, params)
        self._conn.commit()
        return cursor

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Execute SQL and return the first row as a dict, or None.

        Args:
            sql: SELECT statement.
            params: Query parameters.
        """
        row = self._conn.execute(sql, params).fetchone()
        if row is None:
            return None
        return dict(row)

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Execute SQL and return all rows as list of dicts.

        Args:
            sql: SELECT statement.
            params: Query parameters.
        """
        return [dict(row) for row in self._conn.execute(sql, params).fetchall()]
