from __future__ import annotations

from typing import Any

from backend.app.postgres_repository import (
    PostgresConnection,
    PostgresRepository,
)


class FakeRawConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, statement: str, _parameters: tuple[Any, ...] = ()) -> Any:
        self.statements.append(statement)
        return self

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeRawConnection()
        self.released = 0

    def getconn(self) -> FakeRawConnection:
        return self.connection

    def putconn(self, _connection: FakeRawConnection) -> None:
        self.released += 1


def test_postgres_sql_converts_placeholders() -> None:
    assert PostgresConnection._sql(
        "SELECT * FROM games WHERE device_id = ? AND mode = ?"
    ) == "SELECT * FROM games WHERE device_id = %s AND mode = %s"


def test_postgres_sql_converts_insert_or_ignore() -> None:
    assert PostgresConnection._sql(
        "INSERT OR IGNORE INTO devices(id, created_at) VALUES (?, ?)"
    ) == (
        "INSERT INTO devices(id, created_at) VALUES (%s, %s) "
        "ON CONFLICT DO NOTHING"
    )


def test_postgres_sql_converts_sqlite_write_lock() -> None:
    assert PostgresConnection._sql("BEGIN IMMEDIATE") == "BEGIN"


def test_postgres_transaction_serializes_writes() -> None:
    repository = object.__new__(PostgresRepository)
    pool = FakePool()
    repository._pool = pool

    with repository.transaction() as connection:
        connection.execute("SELECT 1")

    assert pool.connection.statements == [
        "BEGIN",
        "SELECT pg_advisory_xact_lock(hashtext('deception-write'))",
        "SELECT 1",
    ]
    assert pool.connection.commits == 1
    assert pool.connection.rollbacks == 0
    assert pool.released == 1
