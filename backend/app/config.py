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

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=_resolve_project_path(
                os.getenv("DECEPTION_DB_PATH", ".data/deception.sqlite")
            ),
            daily_seed=os.getenv(
                "DECEPTION_DAILY_SEED", "local-truth-baseline-seed"
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
        )
