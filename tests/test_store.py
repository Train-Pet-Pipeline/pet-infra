"""Tests for pet_infra.store module."""

from pathlib import Path

import pytest

from pet_infra.store import BaseStore


class ConcreteStore(BaseStore):
    """Test implementation of BaseStore."""

    def _init_schema(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS items ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  name TEXT NOT NULL,"
            "  value REAL"
            ")"
        )
        self._conn.commit()


class TestBaseStoreInit:
    def test_in_memory_connection(self):
        store = ConcreteStore(db_path=":memory:")
        assert store._conn is not None
        store.close()

    def test_file_connection(self, tmp_path: Path):
        db_file = tmp_path / "test.db"
        store = ConcreteStore(db_path=str(db_file))
        assert db_file.exists()
        store.close()

    def test_wal_mode_enabled(self, tmp_path: Path):
        # WAL mode requires a file-based DB; in-memory DBs stay in 'memory' mode.
        db_file = tmp_path / "wal_test.db"
        store = ConcreteStore(db_path=str(db_file))
        mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        store.close()

    def test_foreign_keys_enabled(self):
        store = ConcreteStore(db_path=":memory:")
        fk = store._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        store.close()


class TestBaseStoreContextManager:
    def test_context_manager_enter_exit(self):
        with ConcreteStore(db_path=":memory:") as store:
            assert store._conn is not None

    def test_context_manager_closes_on_exit(self):
        store = ConcreteStore(db_path=":memory:")
        with store:
            conn = store._conn
        with pytest.raises(Exception):
            conn.execute("SELECT 1")


class TestBaseStoreTransactions:
    def test_execute_with_commit(self):
        with ConcreteStore(db_path=":memory:") as store:
            store.execute_commit(
                "INSERT INTO items (name, value) VALUES (?, ?)", ("test", 1.0)
            )
            row = store._conn.execute(
                "SELECT name, value FROM items WHERE name = ?", ("test",)
            ).fetchone()
            assert row["name"] == "test"
            assert row["value"] == 1.0

    def test_transaction_rollback_on_error(self):
        with ConcreteStore(db_path=":memory:") as store:
            store.execute_commit(
                "INSERT INTO items (name, value) VALUES (?, ?)", ("keep", 1.0)
            )
            with pytest.raises(ValueError):
                with store.transaction():
                    store._conn.execute(
                        "INSERT INTO items (name, value) VALUES (?, ?)", ("discard", 2.0)
                    )
                    raise ValueError("force rollback")
            rows = store._conn.execute("SELECT name FROM items").fetchall()
            names = [r["name"] for r in rows]
            assert "keep" in names
            assert "discard" not in names

    def test_transaction_commits_on_success(self):
        with ConcreteStore(db_path=":memory:") as store:
            with store.transaction():
                store._conn.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)", ("committed", 3.0)
                )
            row = store._conn.execute(
                "SELECT name FROM items WHERE name = ?", ("committed",)
            ).fetchone()
            assert row is not None


class TestBaseStoreQuery:
    def test_fetch_one(self):
        with ConcreteStore(db_path=":memory:") as store:
            store.execute_commit(
                "INSERT INTO items (name, value) VALUES (?, ?)", ("x", 10.0)
            )
            row = store.fetch_one("SELECT name, value FROM items WHERE name = ?", ("x",))
            assert row is not None
            assert row["name"] == "x"

    def test_fetch_one_returns_none(self):
        with ConcreteStore(db_path=":memory:") as store:
            row = store.fetch_one("SELECT * FROM items WHERE name = ?", ("nope",))
            assert row is None

    def test_fetch_all(self):
        with ConcreteStore(db_path=":memory:") as store:
            store.execute_commit("INSERT INTO items (name, value) VALUES (?, ?)", ("a", 1.0))
            store.execute_commit("INSERT INTO items (name, value) VALUES (?, ?)", ("b", 2.0))
            rows = store.fetch_all("SELECT name FROM items ORDER BY name")
            assert len(rows) == 2
            assert rows[0]["name"] == "a"
            assert rows[1]["name"] == "b"
