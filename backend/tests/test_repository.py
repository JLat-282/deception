from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from threading import Event, Lock, get_ident

from backend.app.repository import Repository


def test_legacy_migration_is_serialized_across_initializers(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "concurrent-legacy.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE games (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                puzzle_key TEXT,
                answer TEXT NOT NULL,
                status TEXT NOT NULL,
                guess_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    original_execute_script = Repository._execute_script
    first_migration_entered = Event()
    release_first_migration = Event()
    second_initializer_started = Event()
    second_migration_entered = Event()
    owner_lock = Lock()
    owner_thread: int | None = None

    def delayed_execute_script(
        connection: sqlite3.Connection, script: str
    ) -> None:
        nonlocal owner_thread
        thread_id = get_ident()
        should_pause = False
        with owner_lock:
            if owner_thread is None:
                owner_thread = thread_id
                should_pause = True
            elif thread_id != owner_thread:
                second_migration_entered.set()

        if should_pause:
            first_migration_entered.set()
            assert release_first_migration.wait(timeout=5)
        original_execute_script(connection, script)

    monkeypatch.setattr(
        Repository,
        "_execute_script",
        staticmethod(delayed_execute_script),
    )

    def initialize_second() -> Repository:
        second_initializer_started.set()
        return Repository(db_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(Repository, db_path)
        assert first_migration_entered.wait(timeout=5)
        second = executor.submit(initialize_second)
        assert second_initializer_started.wait(timeout=5)
        assert not second_migration_entered.wait(timeout=0.2)
        release_first_migration.set()
        first.result(timeout=5)
        second.result(timeout=5)

    assert second_migration_entered.is_set()
    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(games)")
        }
        schedule_table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'deception_schedules'
            """
        ).fetchone()
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert "rules_version" in columns
    assert schedule_table == ("deception_schedules",)
    assert schema_version == 1
