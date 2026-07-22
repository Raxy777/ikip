"""Unit tests for the PostgreSQL migration runner; no live database is required."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_MIGRATE_PATH = Path(__file__).resolve().parents[1] / "db" / "migrate.py"
_SPEC = importlib.util.spec_from_file_location("ikip_db_migrate", _MIGRATE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
migrate = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = migrate
_SPEC.loader.exec_module(migrate)


class FakeCursor:
    def __init__(self, rows: list[tuple[str, str]], fail_sql: str | None = None) -> None:
        self.rows = rows
        self.fail_sql = fail_sql
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        self.calls.append((query, params))
        if query == self.fail_sql:
            raise RuntimeError("simulated database failure")

    def fetchall(self) -> list[tuple[str, str]]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[tuple[str, str]], fail_sql: str | None = None) -> None:
        self.fake_cursor = FakeCursor(rows, fail_sql)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _migration(version: str, sql: str) -> migrate.Migration:
    return migrate.Migration(version, hashlib.sha256(sql.encode()).hexdigest(), sql)


def test_discover_orders_files_and_calculates_checksums(tmp_path: Path) -> None:
    (tmp_path / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "notes.sql").write_text("ignored", encoding="utf-8")
    (tmp_path / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")

    found = migrate.discover(tmp_path)

    assert [item.version for item in found] == ["0001_first.sql", "0002_second.sql"]
    assert found[0].checksum == hashlib.sha256(b"SELECT 1;").hexdigest()


def test_discover_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="No migrations found"):
        migrate.discover(tmp_path)


def test_validate_applied_rejects_unknown_and_checksum_mismatch() -> None:
    migration = _migration("0001_first.sql", "SELECT 1;")
    with pytest.raises(RuntimeError, match="unknown migration"):
        migrate.validate_applied({"0000_old.sql": "checksum"}, [migration])
    with pytest.raises(RuntimeError, match="Checksum mismatch"):
        migrate.validate_applied({migration.version: "edited"}, [migration])


def test_up_locks_first_applies_only_pending_in_order_and_commits() -> None:
    first = _migration("0001_first.sql", "SELECT 1;")
    second = _migration("0002_second.sql", "SELECT 2;")
    connection = FakeConnection([(first.version, first.checksum)])

    migrate.run(connection, "up", [first, second])

    calls = connection.fake_cursor.calls
    assert calls[0] == (migrate._ADVISORY_LOCK_SQL, (migrate._ADVISORY_LOCK_KEY,))
    assert not any(query == first.sql for query, _ in calls)
    second_sql_index = next(i for i, call in enumerate(calls) if call[0] == second.sql)
    insert_index = next(i for i, call in enumerate(calls) if call[0].startswith("INSERT INTO"))
    assert second_sql_index < insert_index
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_status_locks_and_rolls_back_without_applying(capsys: Any) -> None:
    migration = _migration("0001_first.sql", "SELECT 1;")
    connection = FakeConnection([])

    migrate.run(connection, "status", [migration])

    assert connection.fake_cursor.calls[0][0] == migrate._ADVISORY_LOCK_SQL
    assert not any(query == migration.sql for query, _ in connection.fake_cursor.calls)
    assert "pending 0001_first.sql" in capsys.readouterr().out
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_apply_failure_rolls_back_and_does_not_commit() -> None:
    migration = _migration("0001_first.sql", "BROKEN SQL")
    connection = FakeConnection([], fail_sql=migration.sql)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        migrate.run(connection, "up", [migration])

    assert connection.commits == 0
    assert connection.rollbacks == 1
