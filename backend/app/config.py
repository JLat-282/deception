from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _resolve_project_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _optional_utc_datetime(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("DECEPTION_FIXED_NOW must include a UTC offset.")
    return parsed.astimezone(UTC)


def _optional_lie_row(raw_value: str | None) -> int | None:
    if not raw_value:
        return None
    try:
        row = int(raw_value)
    except ValueError as error:
        raise ValueError(
            "DECEPTION_FIXED_LIE_ROW must be an integer from 1 through 6."
        ) from error
    if row not in range(1, 7):
        raise ValueError(
            "DECEPTION_FIXED_LIE_ROW must be an integer from 1 through 6."
        )
    return row


def _optional_lie_rows(raw_value: str | None) -> tuple[int, ...] | None:
    if not raw_value:
        return None
    try:
        rows = tuple(int(value.strip()) for value in raw_value.split(","))
    except ValueError as error:
        raise ValueError(
            "DECEPTION_FIXED_LIE_ROWS must contain one or two distinct "
            "integers from 1 through 6."
        ) from error
    if (
        len(rows) not in {1, 2}
        or len(set(rows)) != len(rows)
        or any(row not in range(1, 7) for row in rows)
    ):
        raise ValueError(
            "DECEPTION_FIXED_LIE_ROWS must contain one or two distinct "
            "integers from 1 through 6."
        )
    return tuple(sorted(rows))


def _optional_probability(raw_value: str | None) -> float | None:
    if not raw_value:
        return None
    try:
        probability = float(raw_value)
    except ValueError as error:
        raise ValueError(
            "DECEPTION_FIXED_REVERSE_ENTRY_ROLL must be between 0 and 1."
        ) from error
    if not 0 <= probability <= 1:
        raise ValueError(
            "DECEPTION_FIXED_REVERSE_ENTRY_ROLL must be between 0 and 1."
        )
    return probability


@dataclass(frozen=True)
class Settings:
    db_path: Path
    daily_seed: str
    answer_list_version: str
    data_dir: Path = DEFAULT_DATA_DIR
    cookie_name: str = "deception_device"
    secure_cookie: bool = False
    fixed_answer: str | None = None
    fixed_now: datetime | None = None
    fixed_lie_row: int | None = None
    fixed_lie_rows: tuple[int, ...] | None = None
    fixed_session_seed: str | None = None
    reverse_entry_enabled: bool = False
    fixed_reverse_entry_roll: float | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=_resolve_project_path(
                os.getenv("DECEPTION_DB_PATH", ".data/deception.sqlite")
            ),
            daily_seed=os.getenv(
                "DECEPTION_DAILY_SEED", "local-development-seed"
            ),
            answer_list_version=os.getenv(
                "DECEPTION_ANSWER_LIST_VERSION", "wordle-answers-v1"
            ),
            secure_cookie=os.getenv("DECEPTION_SECURE_COOKIE", "false").lower()
            in {"1", "true", "yes"},
            fixed_answer=os.getenv("DECEPTION_FIXED_ANSWER") or None,
            fixed_now=_optional_utc_datetime(
                os.getenv("DECEPTION_FIXED_NOW")
            ),
            fixed_lie_row=_optional_lie_row(
                os.getenv("DECEPTION_FIXED_LIE_ROW")
            ),
            fixed_lie_rows=_optional_lie_rows(
                os.getenv("DECEPTION_FIXED_LIE_ROWS")
            ),
            fixed_session_seed=(
                os.getenv("DECEPTION_FIXED_SESSION_SEED") or None
            ),
            reverse_entry_enabled=os.getenv(
                "DECEPTION_REVERSE_ENTRY_ENABLED", "true"
            ).lower()
            in {"1", "true", "yes"},
            fixed_reverse_entry_roll=_optional_probability(
                os.getenv("DECEPTION_FIXED_REVERSE_ENTRY_ROLL")
            ),
        )
