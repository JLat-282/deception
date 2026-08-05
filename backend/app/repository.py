from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Iterator, Literal


GameMode = Literal["daily", "practice"]
GameStatus = Literal["playing", "won", "lost"]
DailyRunStatus = Literal[
    "unstarted",
    "active",
    "checkpoint",
    "failed",
    "forfeited",
    "completed",
    "expired",
]
DailyStageStatus = Literal["ready", "active", "won", "lost", "forfeited"]
StoredDeceptionReason = Literal[
    "activated",
    "deadline_expired",
    "no_candidate",
    "strategy_restricted",
    "not_scheduled",
    "winning_guess",
    "final_guess",
    "legacy_unknown",
]
CURRENT_RULES_VERSION = 8
CURRENT_DECEPTION_STRATEGY_VERSION = 4


def _stored_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _stored_isoformat(value: str | datetime | None) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class StoredGame:
    game_id: str
    device_id: str
    mode: GameMode
    puzzle_key: str | None
    answer: str
    status: GameStatus
    guess_count: int
    rules_version: int
    preset_key: str
    blueprint_json: str | None


@dataclass(frozen=True)
class DailyAttempt:
    device_id: str
    puzzle_key: str
    game_id: str
    consumed_at: str | None


@dataclass(frozen=True)
class DailyDescentRun:
    device_id: str
    puzzle_key: str
    status: DailyRunStatus
    current_stage: int
    continuation_hash: str | None


@dataclass(frozen=True)
class DailyDescentPuzzle:
    puzzle_key: str
    stage_index: int
    preset_key: str
    answer: str
    blueprint_json: str | None


@dataclass(frozen=True)
class DailyDescentStage:
    device_id: str
    puzzle_key: str
    stage_index: int
    game_id: str
    status: DailyStageStatus


@dataclass(frozen=True)
class StoredGuess:
    attempt: int
    guess: str
    truth_feedback: str
    display_feedback: str
    deception_reason: StoredDeceptionReason


@dataclass(frozen=True)
class DeceptionSchedule:
    ordinal: int
    scheduled_attempt: int
    seed: str
    strategy_version: int


@dataclass(frozen=True)
class ReverseEntryState:
    game_id: str
    seed: str
    status: Literal["armed", "active", "consumed"]
    trigger_attempt: int | None
    trigger_reason: Literal["lowInformation", "chance"] | None
    consumed_attempt: int | None
    event_count: int
    max_events: int


@dataclass(frozen=True)
class GuessTimerState:
    game_id: str
    ordinal: int
    seed: str
    status: Literal[
        "skipped", "scheduled", "active", "completed", "expired"
    ]
    scheduled_attempt: int | None
    duration_seconds: int | None
    starts_at: datetime | None
    deadline_at: datetime | None
    resolved_attempt: int | None


@dataclass(frozen=True)
class BlackoutState:
    game_id: str
    seed: str
    status: Literal["skipped", "scheduled", "activated"]
    scheduled_attempt: int | None


SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_puzzles (
    puzzle_key TEXT PRIMARY KEY,
    answer TEXT NOT NULL,
    blueprint_json TEXT,
    answer_list_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(id),
    mode TEXT NOT NULL CHECK (mode IN ('daily', 'practice')),
    puzzle_key TEXT,
    answer TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'playing'
        CHECK (status IN ('playing', 'won', 'lost')),
    guess_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_device_mode
ON games(device_id, mode, created_at DESC);

CREATE TABLE IF NOT EXISTS daily_attempts (
    device_id TEXT NOT NULL REFERENCES devices(id),
    puzzle_key TEXT NOT NULL,
    game_id TEXT NOT NULL UNIQUE REFERENCES games(id),
    consumed_at TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (device_id, puzzle_key)
);

CREATE TABLE IF NOT EXISTS guesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL REFERENCES games(id),
    attempt INTEGER NOT NULL,
    guess TEXT NOT NULL,
    truth_feedback TEXT NOT NULL,
    display_feedback TEXT NOT NULL,
    deception_reason TEXT NOT NULL DEFAULT 'legacy_unknown',
    created_at TEXT NOT NULL,
    UNIQUE (game_id, attempt)
);
"""

MIGRATION_10 = """
-- Applied conditionally because SQLite cannot add an existing column.
"""


MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS deception_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    daily_puzzle_key TEXT REFERENCES daily_puzzles(puzzle_key),
    game_id TEXT REFERENCES games(id),
    ordinal INTEGER NOT NULL DEFAULT 1 CHECK (ordinal >= 1),
    scheduled_attempt INTEGER NOT NULL CHECK (
        scheduled_attempt BETWEEN 1 AND 6
    ),
    seed TEXT NOT NULL,
    strategy_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    CHECK (
        (daily_puzzle_key IS NOT NULL AND game_id IS NULL)
        OR (daily_puzzle_key IS NULL AND game_id IS NOT NULL)
    ),
    UNIQUE (daily_puzzle_key, ordinal),
    UNIQUE (game_id, ordinal)
);
"""

MIGRATION_2 = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_schedule_attempt
ON deception_schedules(daily_puzzle_key, scheduled_attempt)
WHERE daily_puzzle_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_game_schedule_attempt
ON deception_schedules(game_id, scheduled_attempt)
WHERE game_id IS NOT NULL;
"""

MIGRATION_3 = """
CREATE TABLE IF NOT EXISTS reverse_entry_states (
    game_id TEXT PRIMARY KEY REFERENCES games(id),
    seed TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'armed'
        CHECK (status IN ('armed', 'active', 'consumed')),
    trigger_attempt INTEGER CHECK (trigger_attempt BETWEEN 1 AND 5),
    trigger_reason TEXT
        CHECK (trigger_reason IN ('lowInformation', 'chance')),
    consumed_attempt INTEGER CHECK (consumed_attempt BETWEEN 2 AND 6),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (status = 'armed' AND trigger_attempt IS NULL
            AND trigger_reason IS NULL AND consumed_attempt IS NULL)
        OR (status = 'active' AND trigger_attempt IS NOT NULL
            AND trigger_reason IS NOT NULL AND consumed_attempt IS NULL)
        OR (status = 'consumed' AND trigger_attempt IS NOT NULL
            AND trigger_reason IS NOT NULL AND consumed_attempt IS NOT NULL)
    )
);
"""

MIGRATION_4 = """
CREATE TABLE IF NOT EXISTS guess_timer_states (
    game_id TEXT PRIMARY KEY REFERENCES games(id),
    seed TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (
            status IN (
                'skipped', 'scheduled', 'active', 'completed', 'expired'
            )
        ),
    scheduled_attempt INTEGER CHECK (scheduled_attempt BETWEEN 2 AND 6),
    duration_seconds INTEGER CHECK (duration_seconds IN (10, 30)),
    starts_at TEXT,
    deadline_at TEXT,
    resolved_attempt INTEGER CHECK (resolved_attempt BETWEEN 2 AND 6),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (
            status = 'skipped'
            AND scheduled_attempt IS NULL
            AND duration_seconds IS NULL
            AND starts_at IS NULL
            AND deadline_at IS NULL
            AND resolved_attempt IS NULL
        )
        OR (
            status = 'scheduled'
            AND scheduled_attempt IS NOT NULL
            AND duration_seconds IS NOT NULL
            AND starts_at IS NULL
            AND deadline_at IS NULL
            AND resolved_attempt IS NULL
        )
        OR (
            status = 'active'
            AND scheduled_attempt IS NOT NULL
            AND duration_seconds IS NOT NULL
            AND starts_at IS NOT NULL
            AND deadline_at IS NOT NULL
            AND resolved_attempt IS NULL
        )
        OR (
            status IN ('completed', 'expired')
            AND scheduled_attempt IS NOT NULL
            AND duration_seconds IS NOT NULL
            AND starts_at IS NOT NULL
            AND deadline_at IS NOT NULL
            AND resolved_attempt = scheduled_attempt
        )
    )
);
"""

MIGRATION_5 = """
CREATE TABLE IF NOT EXISTS blackout_states (
    game_id TEXT PRIMARY KEY REFERENCES games(id),
    seed TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('skipped', 'scheduled', 'activated')),
    scheduled_attempt INTEGER CHECK (scheduled_attempt BETWEEN 3 AND 5),
    activated_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (
            status = 'skipped'
            AND scheduled_attempt IS NULL
            AND activated_at IS NULL
        )
        OR (
            status = 'scheduled'
            AND scheduled_attempt IS NOT NULL
            AND activated_at IS NULL
        )
        OR (
            status = 'activated'
            AND scheduled_attempt IS NOT NULL
            AND activated_at IS NOT NULL
        )
    )
);
"""

MIGRATION_7 = """
CREATE TABLE IF NOT EXISTS reverse_entry_states_v2 (
    game_id TEXT PRIMARY KEY REFERENCES games(id),
    seed TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('armed', 'active', 'consumed')),
    trigger_attempt INTEGER CHECK (trigger_attempt BETWEEN 1 AND 5),
    trigger_reason TEXT CHECK (trigger_reason IN ('lowInformation', 'chance')),
    consumed_attempt INTEGER CHECK (consumed_attempt BETWEEN 2 AND 6),
    event_count INTEGER NOT NULL DEFAULT 0 CHECK (event_count >= 0),
    max_events INTEGER NOT NULL DEFAULT 1 CHECK (max_events >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (event_count <= max_events)
);

CREATE TABLE IF NOT EXISTS guess_timer_events (
    game_id TEXT NOT NULL REFERENCES games(id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 1),
    seed TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('skipped', 'scheduled', 'active', 'completed', 'expired')
    ),
    scheduled_attempt INTEGER CHECK (scheduled_attempt BETWEEN 2 AND 6),
    duration_seconds INTEGER CHECK (duration_seconds IN (10, 30)),
    starts_at TEXT,
    deadline_at TEXT,
    resolved_attempt INTEGER CHECK (resolved_attempt BETWEEN 2 AND 6),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (game_id, ordinal),
    UNIQUE (game_id, scheduled_attempt)
);
"""

MIGRATION_9 = """
CREATE TABLE IF NOT EXISTS daily_descent_puzzles (
    puzzle_key TEXT NOT NULL,
    stage_index INTEGER NOT NULL CHECK (stage_index BETWEEN 1 AND 4),
    preset_key TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_list_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (puzzle_key, stage_index),
    UNIQUE (puzzle_key, answer)
);

CREATE TABLE IF NOT EXISTS daily_descent_runs (
    device_id TEXT NOT NULL REFERENCES devices(id),
    puzzle_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'unstarted', 'active', 'checkpoint', 'failed',
            'forfeited', 'completed', 'expired'
        )
    ),
    current_stage INTEGER NOT NULL CHECK (current_stage BETWEEN 1 AND 4),
    continuation_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (device_id, puzzle_key)
);

CREATE TABLE IF NOT EXISTS daily_descent_stages (
    device_id TEXT NOT NULL,
    puzzle_key TEXT NOT NULL,
    stage_index INTEGER NOT NULL CHECK (stage_index BETWEEN 1 AND 4),
    game_id TEXT NOT NULL UNIQUE REFERENCES games(id),
    status TEXT NOT NULL CHECK (
        status IN ('ready', 'active', 'won', 'lost', 'forfeited')
    ),
    consumed_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (device_id, puzzle_key, stage_index),
    FOREIGN KEY (device_id, puzzle_key)
        REFERENCES daily_descent_runs(device_id, puzzle_key)
);
"""

class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def _execute_script(
        connection: sqlite3.Connection, script: str
    ) -> None:
        """Execute static schema statements without ending the active transaction."""
        statement = ""
        for line in script.splitlines():
            statement += f"{line}\n"
            if not sqlite3.complete_statement(statement):
                continue
            if statement.strip():
                connection.execute(statement)
            statement = ""
        if statement.strip():
            raise sqlite3.OperationalError("Incomplete schema statement.")

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN EXCLUSIVE")
            self._execute_script(connection, SCHEMA)
            version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if version < 1:
                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(games)"
                    ).fetchall()
                }
                if "rules_version" not in columns:
                    connection.execute(
                        """
                        ALTER TABLE games
                        ADD COLUMN rules_version INTEGER NOT NULL DEFAULT 1
                        """
                    )
                connection.execute("PRAGMA user_version = 1")
            self._execute_script(connection, MIGRATION_1)
            if version < 2:
                self._execute_script(connection, MIGRATION_2)
                connection.execute("PRAGMA user_version = 2")
            if version < 3:
                self._execute_script(connection, MIGRATION_3)
                connection.execute("PRAGMA user_version = 3")
            if version < 4:
                self._execute_script(connection, MIGRATION_4)
                connection.execute("PRAGMA user_version = 4")
            if version < 5:
                self._execute_script(connection, MIGRATION_5)
                connection.execute("PRAGMA user_version = 5")
            if version < 6:
                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(games)"
                    ).fetchall()
                }
                if "preset_key" not in columns:
                    connection.execute(
                        """
                        ALTER TABLE games ADD COLUMN preset_key TEXT NOT NULL
                        DEFAULT 'doubt-2@1'
                        """
                    )
                if "blueprint_json" not in columns:
                    connection.execute(
                        "ALTER TABLE games ADD COLUMN blueprint_json TEXT"
                    )
                connection.execute("PRAGMA user_version = 6")
            if version < 7:
                self._execute_script(connection, MIGRATION_7)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO reverse_entry_states_v2(
                        game_id, seed, status, trigger_attempt, trigger_reason,
                        consumed_attempt, event_count, max_events, created_at,
                        updated_at
                    )
                    SELECT game_id, seed, status, trigger_attempt, trigger_reason,
                           consumed_attempt,
                           CASE WHEN status = 'armed' THEN 0 ELSE 1 END,
                           1, created_at, updated_at
                    FROM reverse_entry_states
                    """
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO guess_timer_events(
                        game_id, ordinal, seed, status, scheduled_attempt,
                        duration_seconds, starts_at, deadline_at,
                        resolved_attempt, created_at, updated_at
                    )
                    SELECT game_id, 1, seed, status, scheduled_attempt,
                           duration_seconds, starts_at, deadline_at,
                           resolved_attempt, created_at, updated_at
                    FROM guess_timer_states
                    """
                )
                connection.execute("PRAGMA user_version = 7")
            if version < 8:
                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(guesses)"
                    ).fetchall()
                }
                if "deception_reason" not in columns:
                    connection.execute(
                        """
                        ALTER TABLE guesses ADD COLUMN deception_reason TEXT
                        NOT NULL DEFAULT 'legacy_unknown'
                        """
                    )
                connection.execute("PRAGMA user_version = 8")
            if version < 9:
                self._execute_script(connection, MIGRATION_9)
                connection.execute("PRAGMA user_version = 9")
            if version < 10:
                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(daily_descent_puzzles)"
                    ).fetchall()
                }
                if "blueprint_json" not in columns:
                    connection.execute(
                        "ALTER TABLE daily_descent_puzzles "
                        "ADD COLUMN blueprint_json TEXT"
                    )
                connection.execute("PRAGMA user_version = 10")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def health(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()

    @staticmethod
    def ensure_device(
        connection: sqlite3.Connection, device_id: str, created_at: datetime
    ) -> None:
        connection.execute(
            "INSERT OR IGNORE INTO devices(id, created_at) VALUES (?, ?)",
            (device_id, created_at.isoformat()),
        )

    @staticmethod
    def get_daily_attempt(
        connection: sqlite3.Connection, device_id: str, puzzle_key: str
    ) -> DailyAttempt | None:
        row = connection.execute(
            """
            SELECT device_id, puzzle_key, game_id, consumed_at
            FROM daily_attempts
            WHERE device_id = ? AND puzzle_key = ?
            """,
            (device_id, puzzle_key),
        ).fetchone()
        if row is None:
            return None
        return DailyAttempt(
            device_id=row["device_id"],
            puzzle_key=row["puzzle_key"],
            game_id=row["game_id"],
            consumed_at=_stored_isoformat(row["consumed_at"]),
        )

    @staticmethod
    def get_daily_puzzle(
        connection: sqlite3.Connection, puzzle_key: str
    ) -> str | None:
        row = connection.execute(
            "SELECT answer FROM daily_puzzles WHERE puzzle_key = ?",
            (puzzle_key,),
        ).fetchone()
        return None if row is None else str(row["answer"])

    @staticmethod
    def create_daily_puzzle(
        connection: sqlite3.Connection,
        puzzle_key: str,
        answer: str,
        answer_list_version: str,
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO daily_puzzles(
                puzzle_key, answer, answer_list_version, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                puzzle_key,
                answer,
                answer_list_version,
                created_at.isoformat(),
            ),
        )

    @staticmethod
    def create_game(
        connection: sqlite3.Connection,
        game_id: str,
        device_id: str,
        mode: GameMode,
        answer: str,
        created_at: datetime,
        puzzle_key: str | None = None,
        preset_key: str = "doubt-2@1",
        blueprint_json: str | None = None,
    ) -> StoredGame:
        timestamp = created_at.isoformat()
        connection.execute(
            """
            INSERT INTO games(
                id, device_id, mode, puzzle_key, answer, status,
                guess_count, created_at, updated_at, rules_version,
                preset_key, blueprint_json
            ) VALUES (?, ?, ?, ?, ?, 'playing', 0, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                device_id,
                mode,
                puzzle_key,
                answer,
                timestamp,
                timestamp,
                CURRENT_RULES_VERSION,
                preset_key,
                blueprint_json,
            ),
        )
        return StoredGame(
            game_id=game_id,
            device_id=device_id,
            mode=mode,
            puzzle_key=puzzle_key,
            answer=answer,
            status="playing",
            guess_count=0,
            rules_version=CURRENT_RULES_VERSION,
            preset_key=preset_key,
            blueprint_json=blueprint_json,
        )

    @staticmethod
    def create_daily_attempt(
        connection: sqlite3.Connection,
        device_id: str,
        puzzle_key: str,
        game_id: str,
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO daily_attempts(
                device_id, puzzle_key, game_id, consumed_at, created_at
            ) VALUES (?, ?, ?, NULL, ?)
            """,
            (device_id, puzzle_key, game_id, created_at.isoformat()),
        )

    @staticmethod
    def list_daily_descent_puzzles(
        connection: sqlite3.Connection, puzzle_key: str
    ) -> list[DailyDescentPuzzle]:
        rows = connection.execute(
            """
            SELECT puzzle_key, stage_index, preset_key, answer, blueprint_json
            FROM daily_descent_puzzles
            WHERE puzzle_key = ?
            ORDER BY stage_index
            """,
            (puzzle_key,),
        ).fetchall()
        return [
            DailyDescentPuzzle(
                puzzle_key=row["puzzle_key"],
                stage_index=row["stage_index"],
                preset_key=row["preset_key"],
                answer=row["answer"],
                blueprint_json=row["blueprint_json"],
            )
            for row in rows
        ]

    @staticmethod
    def create_daily_descent_puzzle(
        connection: sqlite3.Connection,
        *,
        puzzle_key: str,
        stage_index: int,
        preset_key: str,
        answer: str,
        blueprint_json: str,
        answer_list_version: str,
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO daily_descent_puzzles(
                puzzle_key, stage_index, preset_key, answer,
                answer_list_version, blueprint_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                puzzle_key,
                stage_index,
                preset_key,
                answer,
                answer_list_version,
                blueprint_json,
                created_at.isoformat(),
            ),
        )

    @staticmethod
    def set_daily_descent_blueprint(
        connection: sqlite3.Connection,
        puzzle_key: str,
        stage_index: int,
        blueprint_json: str,
    ) -> None:
        connection.execute(
            """
            UPDATE daily_descent_puzzles SET blueprint_json = ?
            WHERE puzzle_key = ? AND stage_index = ? AND blueprint_json IS NULL
            """,
            (blueprint_json, puzzle_key, stage_index),
        )

    @staticmethod
    def get_daily_descent_run(
        connection: sqlite3.Connection, device_id: str, puzzle_key: str
    ) -> DailyDescentRun | None:
        row = connection.execute(
            """
            SELECT device_id, puzzle_key, status, current_stage,
                   continuation_hash
            FROM daily_descent_runs
            WHERE device_id = ? AND puzzle_key = ?
            """,
            (device_id, puzzle_key),
        ).fetchone()
        if row is None:
            return None
        return DailyDescentRun(
            device_id=row["device_id"],
            puzzle_key=row["puzzle_key"],
            status=row["status"],
            current_stage=row["current_stage"],
            continuation_hash=row["continuation_hash"],
        )

    @staticmethod
    def create_daily_descent_run(
        connection: sqlite3.Connection,
        device_id: str,
        puzzle_key: str,
        created_at: datetime,
    ) -> DailyDescentRun:
        timestamp = created_at.isoformat()
        connection.execute(
            """
            INSERT INTO daily_descent_runs(
                device_id, puzzle_key, status, current_stage,
                continuation_hash, created_at, updated_at
            ) VALUES (?, ?, 'unstarted', 1, NULL, ?, ?)
            """,
            (device_id, puzzle_key, timestamp, timestamp),
        )
        return DailyDescentRun(
            device_id=device_id,
            puzzle_key=puzzle_key,
            status="unstarted",
            current_stage=1,
            continuation_hash=None,
        )

    @staticmethod
    def get_daily_descent_stage(
        connection: sqlite3.Connection,
        device_id: str,
        puzzle_key: str,
        stage_index: int,
    ) -> DailyDescentStage | None:
        row = connection.execute(
            """
            SELECT device_id, puzzle_key, stage_index, game_id, status
            FROM daily_descent_stages
            WHERE device_id = ? AND puzzle_key = ? AND stage_index = ?
            """,
            (device_id, puzzle_key, stage_index),
        ).fetchone()
        if row is None:
            return None
        return DailyDescentStage(
            device_id=row["device_id"],
            puzzle_key=row["puzzle_key"],
            stage_index=row["stage_index"],
            game_id=row["game_id"],
            status=row["status"],
        )

    @staticmethod
    def get_daily_descent_stage_for_game(
        connection: sqlite3.Connection, game_id: str
    ) -> DailyDescentStage | None:
        row = connection.execute(
            """
            SELECT device_id, puzzle_key, stage_index, game_id, status
            FROM daily_descent_stages WHERE game_id = ?
            """,
            (game_id,),
        ).fetchone()
        if row is None:
            return None
        return DailyDescentStage(
            device_id=row["device_id"],
            puzzle_key=row["puzzle_key"],
            stage_index=row["stage_index"],
            game_id=row["game_id"],
            status=row["status"],
        )

    @staticmethod
    def create_daily_descent_stage(
        connection: sqlite3.Connection,
        *,
        device_id: str,
        puzzle_key: str,
        stage_index: int,
        game_id: str,
        created_at: datetime,
    ) -> DailyDescentStage:
        timestamp = created_at.isoformat()
        connection.execute(
            """
            INSERT INTO daily_descent_stages(
                device_id, puzzle_key, stage_index, game_id, status,
                consumed_at, completed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'ready', NULL, NULL, ?, ?)
            """,
            (device_id, puzzle_key, stage_index, game_id, timestamp, timestamp),
        )
        return DailyDescentStage(
            device_id=device_id,
            puzzle_key=puzzle_key,
            stage_index=stage_index,
            game_id=game_id,
            status="ready",
        )

    @staticmethod
    def activate_daily_descent_stage(
        connection: sqlite3.Connection,
        *,
        device_id: str,
        puzzle_key: str,
        stage_index: int,
        continuation_hash: str,
        activated_at: datetime,
    ) -> None:
        timestamp = activated_at.isoformat()
        connection.execute(
            """
            UPDATE daily_descent_stages
            SET status = 'active', consumed_at = ?, updated_at = ?
            WHERE device_id = ? AND puzzle_key = ? AND stage_index = ?
              AND status = 'ready'
            """,
            (timestamp, timestamp, device_id, puzzle_key, stage_index),
        )
        connection.execute(
            """
            UPDATE daily_descent_runs
            SET status = 'active', continuation_hash = ?, updated_at = ?
            WHERE device_id = ? AND puzzle_key = ?
              AND status IN ('unstarted', 'checkpoint')
              AND current_stage = ?
            """,
            (
                continuation_hash,
                timestamp,
                device_id,
                puzzle_key,
                stage_index,
            ),
        )

    @staticmethod
    def finish_daily_descent_stage(
        connection: sqlite3.Connection,
        *,
        device_id: str,
        puzzle_key: str,
        stage_index: int,
        won: bool,
        finished_at: datetime,
    ) -> DailyRunStatus:
        timestamp = finished_at.isoformat()
        stage_status: DailyStageStatus = "won" if won else "lost"
        connection.execute(
            """
            UPDATE daily_descent_stages
            SET status = ?, completed_at = ?, updated_at = ?
            WHERE device_id = ? AND puzzle_key = ? AND stage_index = ?
              AND status = 'active'
            """,
            (
                stage_status,
                timestamp,
                timestamp,
                device_id,
                puzzle_key,
                stage_index,
            ),
        )
        if not won:
            run_status: DailyRunStatus = "failed"
            next_stage = stage_index
        elif stage_index == 4:
            run_status = "completed"
            next_stage = 4
        else:
            run_status = "checkpoint"
            next_stage = stage_index + 1
        connection.execute(
            """
            UPDATE daily_descent_runs
            SET status = ?, current_stage = ?, continuation_hash = NULL,
                updated_at = ?
            WHERE device_id = ? AND puzzle_key = ? AND status = 'active'
              AND current_stage = ?
            """,
            (
                run_status,
                next_stage,
                timestamp,
                device_id,
                puzzle_key,
                stage_index,
            ),
        )
        return run_status

    @staticmethod
    def forfeit_daily_descent_run(
        connection: sqlite3.Connection,
        device_id: str,
        puzzle_key: str,
        stage_index: int,
        forfeited_at: datetime,
    ) -> None:
        timestamp = forfeited_at.isoformat()
        connection.execute(
            """
            UPDATE daily_descent_stages
            SET status = 'forfeited', completed_at = ?, updated_at = ?
            WHERE device_id = ? AND puzzle_key = ? AND stage_index = ?
              AND status = 'active'
            """,
            (timestamp, timestamp, device_id, puzzle_key, stage_index),
        )
        connection.execute(
            """
            UPDATE daily_descent_runs
            SET status = 'forfeited', continuation_hash = NULL, updated_at = ?
            WHERE device_id = ? AND puzzle_key = ? AND status = 'active'
            """,
            (timestamp, device_id, puzzle_key),
        )

    @staticmethod
    def expire_daily_descent_run(
        connection: sqlite3.Connection,
        device_id: str,
        puzzle_key: str,
        expired_at: datetime,
    ) -> None:
        connection.execute(
            """
            UPDATE daily_descent_runs
            SET status = 'expired', continuation_hash = NULL, updated_at = ?
            WHERE device_id = ? AND puzzle_key = ?
              AND status IN ('unstarted', 'active', 'checkpoint')
            """,
            (expired_at.isoformat(), device_id, puzzle_key),
        )

    @staticmethod
    def get_game(
        connection: sqlite3.Connection, game_id: str
    ) -> StoredGame | None:
        row = connection.execute(
            """
            SELECT id, device_id, mode, puzzle_key, answer, status,
                   guess_count, rules_version, preset_key, blueprint_json
            FROM games
            WHERE id = ?
            """,
            (game_id,),
        ).fetchone()
        if row is None:
            return None
        return StoredGame(
            game_id=row["id"],
            device_id=row["device_id"],
            mode=row["mode"],
            puzzle_key=row["puzzle_key"],
            answer=row["answer"],
            status=row["status"],
            guess_count=row["guess_count"],
            rules_version=row["rules_version"],
            preset_key=row["preset_key"],
            blueprint_json=row["blueprint_json"],
        )

    @staticmethod
    def set_game_blueprint(
        connection: sqlite3.Connection,
        game_id: str,
        preset_key: str,
        blueprint_json: str,
    ) -> None:
        connection.execute(
            """
            UPDATE games SET preset_key = ?, blueprint_json = ?
            WHERE id = ? AND guess_count = 0
            """,
            (preset_key, blueprint_json, game_id),
        )

    @staticmethod
    def upgrade_game_rules(
        connection: sqlite3.Connection, game_id: str
    ) -> None:
        connection.execute(
            """
            UPDATE games
            SET rules_version = ?
            WHERE id = ? AND guess_count = 0
            """,
            (CURRENT_RULES_VERSION, game_id),
        )

    @staticmethod
    def replace_deception_schedules(
        connection: sqlite3.Connection,
        *,
        scheduled_attempts: tuple[int, ...],
        seed: str,
        created_at: datetime,
        daily_puzzle_key: str | None = None,
        game_id: str | None = None,
    ) -> list[DeceptionSchedule]:
        if (daily_puzzle_key is None) == (game_id is None):
            raise ValueError("Provide exactly one deception schedule scope.")
        if (
            len(scheduled_attempts) not in range(1, 6)
            or len(set(scheduled_attempts)) != len(scheduled_attempts)
            or any(attempt not in range(1, 7) for attempt in scheduled_attempts)
        ):
            raise ValueError(
                "A deception schedule must contain one to five distinct rows."
            )
        if daily_puzzle_key is not None:
            connection.execute(
                "DELETE FROM deception_schedules WHERE daily_puzzle_key = ?",
                (daily_puzzle_key,),
            )
        else:
            connection.execute(
                "DELETE FROM deception_schedules WHERE game_id = ?",
                (game_id,),
            )

        for ordinal, scheduled_attempt in enumerate(
            sorted(scheduled_attempts), start=1
        ):
            connection.execute(
                """
                INSERT INTO deception_schedules(
                    daily_puzzle_key, game_id, ordinal, scheduled_attempt,
                    seed, strategy_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    daily_puzzle_key,
                    game_id,
                    ordinal,
                    scheduled_attempt,
                    seed,
                    CURRENT_DECEPTION_STRATEGY_VERSION,
                    created_at.isoformat(),
                ),
            )
        return Repository.list_deception_schedules(
            connection,
            daily_puzzle_key=daily_puzzle_key,
            game_id=game_id,
        )

    @staticmethod
    def list_deception_schedules(
        connection: sqlite3.Connection,
        *,
        daily_puzzle_key: str | None = None,
        game_id: str | None = None,
    ) -> list[DeceptionSchedule]:
        if (daily_puzzle_key is None) == (game_id is None):
            raise ValueError(
                "Provide exactly one deception schedule scope."
            )
        if daily_puzzle_key is not None:
            row = connection.execute(
                """
                SELECT ordinal, scheduled_attempt, seed, strategy_version
                FROM deception_schedules
                WHERE daily_puzzle_key = ?
                ORDER BY scheduled_attempt, ordinal
                """,
                (daily_puzzle_key,),
            ).fetchall()
        else:
            row = connection.execute(
                """
                SELECT ordinal, scheduled_attempt, seed, strategy_version
                FROM deception_schedules
                WHERE game_id = ?
                ORDER BY scheduled_attempt, ordinal
                """,
                (game_id,),
            ).fetchall()
        return [
            DeceptionSchedule(
                ordinal=item["ordinal"],
                scheduled_attempt=item["scheduled_attempt"],
                seed=item["seed"],
                strategy_version=item["strategy_version"],
            )
            for item in row
        ]

    @staticmethod
    def list_guesses(
        connection: sqlite3.Connection, game_id: str
    ) -> list[StoredGuess]:
        rows = connection.execute(
            """
            SELECT attempt, guess, truth_feedback, display_feedback,
                   deception_reason
            FROM guesses
            WHERE game_id = ?
            ORDER BY attempt
            """,
            (game_id,),
        ).fetchall()
        return [
            StoredGuess(
                attempt=row["attempt"],
                guess=row["guess"],
                truth_feedback=row["truth_feedback"],
                display_feedback=row["display_feedback"],
                deception_reason=row["deception_reason"],
            )
            for row in rows
        ]

    @staticmethod
    def create_reverse_entry_state(
        connection: sqlite3.Connection,
        game_id: str,
        seed: str,
        max_events: int,
        created_at: datetime,
    ) -> ReverseEntryState:
        timestamp = created_at.isoformat()
        connection.execute(
            """
            INSERT OR IGNORE INTO reverse_entry_states_v2(
                game_id, seed, status, trigger_attempt, trigger_reason,
                consumed_attempt, event_count, max_events, created_at, updated_at
            ) VALUES (?, ?, 'armed', NULL, NULL, NULL, 0, ?, ?, ?)
            """,
            (game_id, seed, max_events, timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO reverse_entry_states(
                game_id, seed, status, trigger_attempt, trigger_reason,
                consumed_attempt, created_at, updated_at
            ) VALUES (?, ?, 'armed', NULL, NULL, NULL, ?, ?)
            """,
            (game_id, seed, timestamp, timestamp),
        )
        state = Repository.get_reverse_entry_state(connection, game_id)
        if state is None:
            raise sqlite3.IntegrityError(
                "Reverse Entry state could not be created."
            )
        return state

    @staticmethod
    def get_reverse_entry_state(
        connection: sqlite3.Connection, game_id: str
    ) -> ReverseEntryState | None:
        row = connection.execute(
            """
            SELECT game_id, seed, status, trigger_attempt, trigger_reason,
                   consumed_attempt, event_count, max_events
            FROM reverse_entry_states_v2
            WHERE game_id = ?
            """,
            (game_id,),
        ).fetchone()
        if row is None:
            return None
        return ReverseEntryState(
            game_id=row["game_id"],
            seed=row["seed"],
            status=row["status"],
            trigger_attempt=row["trigger_attempt"],
            trigger_reason=row["trigger_reason"],
            consumed_attempt=row["consumed_attempt"],
            event_count=row["event_count"],
            max_events=row["max_events"],
        )

    @staticmethod
    def activate_reverse_entry(
        connection: sqlite3.Connection,
        game_id: str,
        trigger_attempt: int,
        trigger_reason: Literal["lowInformation", "chance"],
        updated_at: datetime,
    ) -> None:
        connection.execute(
            """
            UPDATE reverse_entry_states_v2
            SET status = 'active', trigger_attempt = ?, trigger_reason = ?,
                event_count = event_count + 1, updated_at = ?
            WHERE game_id = ? AND status = 'armed' AND event_count < max_events
            """,
            (
                trigger_attempt,
                trigger_reason,
                updated_at.isoformat(),
                game_id,
            ),
        )
        connection.execute(
            """
            UPDATE reverse_entry_states
            SET status = 'active', trigger_attempt = ?, trigger_reason = ?,
                updated_at = ?
            WHERE game_id = ?
            """,
            (trigger_attempt, trigger_reason, updated_at.isoformat(), game_id),
        )

    @staticmethod
    def consume_reverse_entry(
        connection: sqlite3.Connection,
        game_id: str,
        consumed_attempt: int,
        updated_at: datetime,
        *,
        rearm: bool = False,
    ) -> None:
        connection.execute(
            """
            UPDATE reverse_entry_states_v2
            SET status = ?,
                trigger_attempt = CASE WHEN ? THEN NULL ELSE trigger_attempt END,
                trigger_reason = CASE WHEN ? THEN NULL ELSE trigger_reason END,
                consumed_attempt = CASE WHEN ? THEN NULL ELSE ? END,
                updated_at = ?
            WHERE game_id = ? AND status = 'active'
            """,
            (
                "armed" if rearm else "consumed",
                rearm,
                rearm,
                rearm,
                consumed_attempt,
                updated_at.isoformat(),
                game_id,
            ),
        )
        if rearm:
            connection.execute(
                """
                UPDATE reverse_entry_states
                SET status = 'armed', trigger_attempt = NULL,
                    trigger_reason = NULL, consumed_attempt = NULL, updated_at = ?
                WHERE game_id = ?
                """,
                (updated_at.isoformat(), game_id),
            )
        else:
            connection.execute(
                """
                UPDATE reverse_entry_states
                SET status = 'consumed', consumed_attempt = ?, updated_at = ?
                WHERE game_id = ?
                """,
                (consumed_attempt, updated_at.isoformat(), game_id),
            )

    @staticmethod
    def create_guess_timer_state(
        connection: sqlite3.Connection,
        game_id: str,
        seed: str,
        scheduled_attempt: int | None,
        duration_seconds: int | None,
        created_at: datetime,
    ) -> GuessTimerState:
        if (scheduled_attempt is None) != (duration_seconds is None):
            raise ValueError(
                "Timer attempt and duration must either both be set or omitted."
            )
        timestamp = created_at.isoformat()
        status = "skipped" if scheduled_attempt is None else "scheduled"
        connection.execute(
            """
            INSERT OR IGNORE INTO guess_timer_events(
                game_id, ordinal, seed, status, scheduled_attempt, duration_seconds,
                starts_at, deadline_at, resolved_attempt, created_at,
                updated_at
            ) VALUES (?, 1, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
            """,
            (
                game_id,
                seed,
                status,
                scheduled_attempt,
                duration_seconds,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO guess_timer_states(
                game_id, seed, status, scheduled_attempt, duration_seconds,
                starts_at, deadline_at, resolved_attempt, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
            """,
            (
                game_id,
                seed,
                status,
                scheduled_attempt,
                duration_seconds,
                timestamp,
                timestamp,
            ),
        )
        state = Repository.get_guess_timer_state(connection, game_id)
        if state is None:
            raise sqlite3.IntegrityError(
                "Guess Timer state could not be created."
            )
        return state

    @staticmethod
    def get_guess_timer_state(
        connection: sqlite3.Connection, game_id: str
    ) -> GuessTimerState | None:
        row = connection.execute(
            """
            SELECT game_id, ordinal, seed, status, scheduled_attempt,
                   duration_seconds, starts_at, deadline_at,
                   resolved_attempt
            FROM guess_timer_events
            WHERE game_id = ?
            ORDER BY CASE status
                WHEN 'active' THEN 0 WHEN 'scheduled' THEN 1 ELSE 2 END,
                scheduled_attempt, ordinal
            LIMIT 1
            """,
            (game_id,),
        ).fetchone()
        if row is None:
            return None
        return GuessTimerState(
            game_id=row["game_id"],
            ordinal=row["ordinal"],
            seed=row["seed"],
            status=row["status"],
            scheduled_attempt=row["scheduled_attempt"],
            duration_seconds=row["duration_seconds"],
            starts_at=_stored_datetime(row["starts_at"]),
            deadline_at=_stored_datetime(row["deadline_at"]),
            resolved_attempt=row["resolved_attempt"],
        )

    @staticmethod
    def list_guess_timer_states(
        connection: sqlite3.Connection, game_id: str
    ) -> list[GuessTimerState]:
        rows = connection.execute(
            """
            SELECT game_id, ordinal, seed, status, scheduled_attempt,
                   duration_seconds, starts_at, deadline_at, resolved_attempt
            FROM guess_timer_events
            WHERE game_id = ?
            ORDER BY ordinal
            """,
            (game_id,),
        ).fetchall()
        return [
            GuessTimerState(
                game_id=row["game_id"],
                ordinal=row["ordinal"],
                seed=row["seed"],
                status=row["status"],
                scheduled_attempt=row["scheduled_attempt"],
                duration_seconds=row["duration_seconds"],
                starts_at=_stored_datetime(row["starts_at"]),
                deadline_at=_stored_datetime(row["deadline_at"]),
                resolved_attempt=row["resolved_attempt"],
            )
            for row in rows
        ]

    @staticmethod
    def get_guess_timer_for_attempt(
        connection: sqlite3.Connection, game_id: str, attempt: int
    ) -> GuessTimerState | None:
        return next(
            (
                state
                for state in Repository.list_guess_timer_states(connection, game_id)
                if state.scheduled_attempt == attempt
            ),
            None,
        )

    @staticmethod
    def create_guess_timer_events(
        connection: sqlite3.Connection,
        game_id: str,
        seed: str,
        events: tuple[tuple[int, int], ...],
        created_at: datetime,
    ) -> list[GuessTimerState]:
        if not events:
            Repository.create_guess_timer_state(
                connection, game_id, seed, None, None, created_at
            )
            return Repository.list_guess_timer_states(connection, game_id)
        timestamp = created_at.isoformat()
        for ordinal, (attempt, duration) in enumerate(events, start=1):
            connection.execute(
                """
                INSERT OR IGNORE INTO guess_timer_events(
                    game_id, ordinal, seed, status, scheduled_attempt,
                    duration_seconds, starts_at, deadline_at, resolved_attempt,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'scheduled', ?, ?, NULL, NULL, NULL, ?, ?)
                """,
                (game_id, ordinal, seed, attempt, duration, timestamp, timestamp),
            )
        first_attempt, first_duration = events[0]
        connection.execute(
            """
            INSERT OR IGNORE INTO guess_timer_states(
                game_id, seed, status, scheduled_attempt, duration_seconds,
                starts_at, deadline_at, resolved_attempt, created_at, updated_at
            ) VALUES (?, ?, 'scheduled', ?, ?, NULL, NULL, NULL, ?, ?)
            """,
            (game_id, seed, first_attempt, first_duration, timestamp, timestamp),
        )
        return Repository.list_guess_timer_states(connection, game_id)

    @staticmethod
    def activate_guess_timer(
        connection: sqlite3.Connection,
        game_id: str,
        ordinal: int,
        starts_at: datetime,
        deadline_at: datetime,
        updated_at: datetime,
    ) -> GuessTimerState:
        connection.execute(
            """
            UPDATE guess_timer_events
            SET status = 'active', starts_at = ?, deadline_at = ?,
                updated_at = ?
            WHERE game_id = ? AND ordinal = ? AND status = 'scheduled'
            """,
            (
                starts_at.isoformat(),
                deadline_at.isoformat(),
                updated_at.isoformat(),
                game_id,
                ordinal,
            ),
        )
        if ordinal == 1:
            connection.execute(
                """
                UPDATE guess_timer_states
                SET status = 'active', starts_at = ?, deadline_at = ?, updated_at = ?
                WHERE game_id = ? AND status = 'scheduled'
                """,
                (
                    starts_at.isoformat(), deadline_at.isoformat(),
                    updated_at.isoformat(), game_id,
                ),
            )
        state = Repository.get_guess_timer_state(connection, game_id)
        if state is None:
            raise sqlite3.IntegrityError(
                "Guess Timer state could not be activated."
            )
        return state

    @staticmethod
    def resolve_guess_timer(
        connection: sqlite3.Connection,
        game_id: str,
        ordinal: int,
        outcome: Literal["completed", "expired"],
        resolved_attempt: int,
        updated_at: datetime,
    ) -> None:
        connection.execute(
            """
            UPDATE guess_timer_events
            SET status = ?, resolved_attempt = ?, updated_at = ?
            WHERE game_id = ? AND ordinal = ? AND status = 'active'
            """,
            (
                outcome,
                resolved_attempt,
                updated_at.isoformat(),
                game_id,
                ordinal,
            ),
        )
        if ordinal == 1:
            connection.execute(
                """
                UPDATE guess_timer_states
                SET status = ?, resolved_attempt = ?, updated_at = ?
                WHERE game_id = ? AND status = 'active'
                """,
                (outcome, resolved_attempt, updated_at.isoformat(), game_id),
            )

    @staticmethod
    def create_blackout_state(
        connection: sqlite3.Connection,
        game_id: str,
        seed: str,
        scheduled_attempt: int | None,
        created_at: datetime,
    ) -> BlackoutState:
        if scheduled_attempt is not None and scheduled_attempt not in range(3, 6):
            raise ValueError("Blackout must be scheduled for attempt 3, 4, or 5.")
        timestamp = created_at.isoformat()
        status = "skipped" if scheduled_attempt is None else "scheduled"
        connection.execute(
            """
            INSERT OR IGNORE INTO blackout_states(
                game_id, seed, status, scheduled_attempt, activated_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                game_id,
                seed,
                status,
                scheduled_attempt,
                timestamp,
                timestamp,
            ),
        )
        state = Repository.get_blackout_state(connection, game_id)
        if state is None:
            raise sqlite3.IntegrityError("Blackout state could not be created.")
        return state

    @staticmethod
    def get_blackout_state(
        connection: sqlite3.Connection, game_id: str
    ) -> BlackoutState | None:
        row = connection.execute(
            """
            SELECT game_id, seed, status, scheduled_attempt
            FROM blackout_states
            WHERE game_id = ?
            """,
            (game_id,),
        ).fetchone()
        if row is None:
            return None
        return BlackoutState(
            game_id=row["game_id"],
            seed=row["seed"],
            status=row["status"],
            scheduled_attempt=row["scheduled_attempt"],
        )

    @staticmethod
    def activate_blackout(
        connection: sqlite3.Connection,
        game_id: str,
        activated_at: datetime,
    ) -> None:
        timestamp = activated_at.isoformat()
        connection.execute(
            """
            UPDATE blackout_states
            SET status = 'activated', activated_at = ?, updated_at = ?
            WHERE game_id = ? AND status = 'scheduled'
            """,
            (timestamp, timestamp, game_id),
        )

    @staticmethod
    def record_timeout(
        connection: sqlite3.Connection,
        game_id: str,
        attempt: int,
        status: GameStatus,
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            UPDATE games
            SET status = ?, guess_count = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, attempt, created_at.isoformat(), game_id),
        )

    @staticmethod
    def last_practice_answer(
        connection: sqlite3.Connection, device_id: str
    ) -> str | None:
        row = connection.execute(
            """
            SELECT answer
            FROM games
            WHERE device_id = ? AND mode = 'practice'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (device_id,),
        ).fetchone()
        return None if row is None else str(row["answer"])

    @staticmethod
    def consume_daily_attempt(
        connection: sqlite3.Connection,
        device_id: str,
        puzzle_key: str,
        game_id: str,
        consumed_at: datetime,
    ) -> None:
        connection.execute(
            """
            UPDATE daily_attempts
            SET consumed_at = ?
            WHERE device_id = ? AND puzzle_key = ? AND game_id = ?
              AND consumed_at IS NULL
            """,
            (
                consumed_at.isoformat(),
                device_id,
                puzzle_key,
                game_id,
            ),
        )

    @staticmethod
    def record_guess(
        connection: sqlite3.Connection,
        game_id: str,
        attempt: int,
        guess: str,
        truth_feedback: str,
        display_feedback: str,
        deception_reason: StoredDeceptionReason,
        status: GameStatus,
        created_at: datetime,
    ) -> None:
        timestamp = created_at.isoformat()
        connection.execute(
            """
            INSERT INTO guesses(
                game_id, attempt, guess, truth_feedback,
                display_feedback, deception_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                attempt,
                guess,
                truth_feedback,
                display_feedback,
                deception_reason,
                timestamp,
            ),
        )
        connection.execute(
            """
            UPDATE games
            SET status = ?, guess_count = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, attempt, timestamp, game_id),
        )
