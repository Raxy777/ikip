"""Small forward-only PostgreSQL migration runner for the pilot.

Usage: ``python db/migrate.py up|status [--dry-run]``. Applied file names and SHA-256
checksums are recorded so an already-applied migration cannot be silently edited. A
transaction-scoped PostgreSQL advisory lock serializes migration inspection and apply.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import psycopg

MIGRATIONS = Path(__file__).with_name("migrations")
# Stable signed 64-bit namespace key derived once for "ikip-schema-migrations".
_ADVISORY_LOCK_KEY = 6_871_433_419_553_460_206
_ADVISORY_LOCK_SQL = "SELECT pg_advisory_xact_lock(%s)"
_METADATA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


@dataclass(frozen=True)
class Migration:
    version: str
    checksum: str
    sql: str


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = None) -> object: ...
    def fetchall(self) -> list[tuple[str, str]]: ...


class CursorContext(Cursor, Protocol):
    def __enter__(self) -> Cursor: ...
    def __exit__(self, *args: object) -> None: ...


class Connection(Protocol):
    def cursor(self) -> CursorContext: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def discover(directory: Path = MIGRATIONS) -> list[Migration]:
    """Discover named SQL files in lexical/version order and calculate their checksums."""
    migrations: list[Migration] = []
    for path in sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        sql = path.read_text(encoding="utf-8")
        migrations.append(Migration(path.name, hashlib.sha256(sql.encode()).hexdigest(), sql))
    if not migrations:
        raise RuntimeError(f"No migrations found in {directory}")
    return migrations


def database_url() -> str:
    if url := os.environ.get("IKIP_DATABASE_URL"):
        return url
    required = ["IKIP_DB_HOST", "IKIP_DB_NAME", "IKIP_DB_USER", "IKIP_DB_PASSWORD"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing database configuration: " + ", ".join(missing))
    port = os.environ.get("IKIP_DB_PORT", "5432")
    return (
        f"host={os.environ['IKIP_DB_HOST']} port={port} dbname={os.environ['IKIP_DB_NAME']} "
        f"user={os.environ['IKIP_DB_USER']} password={os.environ['IKIP_DB_PASSWORD']}"
    )


def validate_applied(applied: dict[str, str], migrations: list[Migration]) -> None:
    known = {migration.version: migration for migration in migrations}
    for version, checksum in applied.items():
        if version not in known:
            raise RuntimeError(f"Database contains unknown migration {version}")
        if known[version].checksum != checksum:
            raise RuntimeError(f"Checksum mismatch for applied migration {version}")


def run(connection: Connection, command: str, migrations: list[Migration]) -> None:
    """Inspect or apply migrations within one serialized transaction."""
    try:
        with connection.cursor() as cursor:
            # This must be the first database operation: metadata inspection and DDL are
            # serialized with every other invocation that uses this runner.
            cursor.execute(_ADVISORY_LOCK_SQL, (_ADVISORY_LOCK_KEY,))
            cursor.execute(_METADATA_SQL)
            cursor.execute("SELECT version, checksum FROM schema_migration ORDER BY version")
            applied: dict[str, str] = dict(cursor.fetchall())
            validate_applied(applied, migrations)
            for migration in migrations:
                state = "applied" if migration.version in applied else "pending"
                print(f"{state:7} {migration.version}")
                if command == "up" and state == "pending":
                    cursor.execute(migration.sql)
                    cursor.execute(
                        "INSERT INTO schema_migration (version, checksum) VALUES (%s, %s)",
                        (migration.version, migration.checksum),
                    )
        if command == "up":
            connection.commit()
        else:
            connection.rollback()
    except BaseException:
        connection.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply IKIP PostgreSQL migrations")
    parser.add_argument("command", choices=("up", "status"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrations = discover()
    if args.dry_run:
        for migration in migrations:
            print(f"pending? {migration.version} sha256={migration.checksum}")
        print("Dry run validates files only; database state was not inspected.")
        return 0

    with psycopg.connect(database_url()) as connection:
        run(connection, args.command, migrations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
