from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Iterator, Literal


GameMode = Literal["daily", "practice"]
GameStatus = Literal["playing", "won", "lost"]
CURRENT_RULES_VERSION = 2


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


@dataclass(frozen=True)
class DailyAttempt:
    device_id: str
    puzzle_key: str
    game_id: str
    consumed_at: str | None


@dataclass(frozen=True)
class StoredGuess:
    attempt: int
    guess: str
    truth_feedback: str
    display_feedback: str


@dataclass(frozen=True)
class DeceptionSchedule:
    scheduled_attempt: int
    seed: str
    strategy_version: int


SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_puzzles (
    puzzle_key TEXT PRIMARY KEY,
    answer TEXT NOT NULL,
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
    created_at TEXT NOT NULL,
    UNIQUE (game_id, attempt)
);
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
            consumed_at=row["consumed_at"],
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
    ) -> StoredGame:
        timestamp = created_at.isoformat()
        connection.execute(
            """
            INSERT INTO games(
                id, device_id, mode, puzzle_key, answer, status,
                guess_count, created_at, updated_at, rules_version
            ) VALUES (?, ?, ?, ?, ?, 'playing', 0, ?, ?, ?)
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
    def get_game(
        connection: sqlite3.Connection, game_id: str
    ) -> StoredGame | None:
        row = connection.execute(
            """
            SELECT id, device_id, mode, puzzle_key, answer, status,
                   guess_count, rules_version
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
    def create_deception_schedule(
        connection: sqlite3.Connection,
        *,
        scheduled_attempt: int,
        seed: str,
        created_at: datetime,
        daily_puzzle_key: str | None = None,
        game_id: str | None = None,
    ) -> DeceptionSchedule:
        connection.execute(
            """
            INSERT OR IGNORE INTO deception_schedules(
                daily_puzzle_key, game_id, ordinal, scheduled_attempt,
                seed, strategy_version, created_at
            ) VALUES (?, ?, 1, ?, ?, 1, ?)
            """,
            (
                daily_puzzle_key,
                game_id,
                scheduled_attempt,
                seed,
                created_at.isoformat(),
            ),
        )
        schedule = Repository.get_deception_schedule(
            connection,
            daily_puzzle_key=daily_puzzle_key,
            game_id=game_id,
        )
        if schedule is None:
            raise sqlite3.IntegrityError(
                "The deception schedule could not be persisted."
            )
        return schedule

    @staticmethod
    def get_deception_schedule(
        connection: sqlite3.Connection,
        *,
        daily_puzzle_key: str | None = None,
        game_id: str | None = None,
    ) -> DeceptionSchedule | None:
        if (daily_puzzle_key is None) == (game_id is None):
            raise ValueError(
                "Provide exactly one deception schedule scope."
            )
        if daily_puzzle_key is not None:
            row = connection.execute(
                """
                SELECT scheduled_attempt, seed, strategy_version
                FROM deception_schedules
                WHERE daily_puzzle_key = ? AND ordinal = 1
                """,
                (daily_puzzle_key,),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT scheduled_attempt, seed, strategy_version
                FROM deception_schedules
                WHERE game_id = ? AND ordinal = 1
                """,
                (game_id,),
            ).fetchone()
        if row is None:
            return None
        return DeceptionSchedule(
            scheduled_attempt=row["scheduled_attempt"],
            seed=row["seed"],
            strategy_version=row["strategy_version"],
        )

    @staticmethod
    def list_guesses(
        connection: sqlite3.Connection, game_id: str
    ) -> list[StoredGuess]:
        rows = connection.execute(
            """
            SELECT attempt, guess, truth_feedback, display_feedback
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
            )
            for row in rows
        ]

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
        status: GameStatus,
        created_at: datetime,
    ) -> None:
        timestamp = created_at.isoformat()
        connection.execute(
            """
            INSERT INTO guesses(
                game_id, attempt, guess, truth_feedback,
                display_feedback, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                attempt,
                guess,
                truth_feedback,
                display_feedback,
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
