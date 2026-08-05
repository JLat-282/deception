from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Iterator

from psycopg import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from .repository import (
    MIGRATION_1,
    MIGRATION_2,
    MIGRATION_3,
    MIGRATION_4,
    MIGRATION_5,
    MIGRATION_7,
    MIGRATION_9,
    Repository,
    SCHEMA,
)


POSTGRES_ERRORS = (PsycopgError, PoolTimeout)


class PostgresConnection:
    """Small compatibility layer for the repository's DB-API-style SQL."""

    def __init__(self, raw: Any, release: Any) -> None:
        self._raw = raw
        self._release = release
        self._closed = False

    @staticmethod
    def _sql(statement: str) -> str:
        converted = statement.replace("BEGIN IMMEDIATE", "BEGIN")
        insert_or_ignore = bool(
            re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", converted, re.I)
        )
        if insert_or_ignore:
            converted = re.sub(
                r"\bINSERT\s+OR\s+IGNORE\s+INTO\b",
                "INSERT INTO",
                converted,
                count=1,
                flags=re.I,
            )
        converted = converted.replace("?", "%s").rstrip().rstrip(";")
        if insert_or_ignore:
            converted += " ON CONFLICT DO NOTHING"
        return converted

    def execute(
        self, statement: str, parameters: tuple[Any, ...] = ()
    ) -> Any:
        return self._raw.execute(self._sql(statement), parameters)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._release(self._raw)

    def __enter__(self) -> PostgresConnection:
        return self

    def __exit__(
        self,
        exception_type: Any,
        _exception: Any,
        _traceback: Any,
    ) -> None:
        try:
            if exception_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


class PostgresRepository(Repository):
    """Repository backend for managed Postgres in serverless production."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._pool = ConnectionPool(
            conninfo=database_url,
            min_size=0,
            max_size=3,
            open=False,
            timeout=5,
            kwargs={
                "autocommit": False,
                "connect_timeout": 5,
                "prepare_threshold": None,
                "row_factory": dict_row,
            },
        )
        self._pool.open()
        self.initialize()

    def connect(self) -> PostgresConnection:
        raw = self._pool.getconn()
        return PostgresConnection(raw, self._pool.putconn)

    @contextmanager
    def transaction(self) -> Iterator[PostgresConnection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext('deception-write'))"
            )
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        postgres_schema = SCHEMA.replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT",
            "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
        )
        with self.connect() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext('deception-schema'))"
            )
            self._execute_script(connection, postgres_schema)
            connection.execute(
                "ALTER TABLE games ADD COLUMN IF NOT EXISTS "
                "rules_version INTEGER NOT NULL DEFAULT 1"
            )
            connection.execute(
                "ALTER TABLE games ADD COLUMN IF NOT EXISTS "
                "preset_key TEXT NOT NULL DEFAULT 'doubt-2@1'"
            )
            connection.execute(
                "ALTER TABLE games ADD COLUMN IF NOT EXISTS blueprint_json TEXT"
            )
            for migration in (
                MIGRATION_1,
                MIGRATION_2,
                MIGRATION_3,
                MIGRATION_4,
                MIGRATION_5,
                MIGRATION_7,
                MIGRATION_9,
            ):
                self._execute_script(connection, migration)
            connection.execute(
                "ALTER TABLE daily_descent_puzzles ADD COLUMN IF NOT EXISTS "
                "blueprint_json TEXT"
            )
