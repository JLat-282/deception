from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta


RESET_HOUR_UTC = 3


@dataclass(frozen=True)
class PuzzleWindow:
    puzzle_key: str
    reset_at: datetime


def daily_window(now: datetime) -> PuzzleWindow:
    if now.tzinfo is None:
        raise ValueError("Daily clock requires a timezone-aware datetime.")

    utc_now = now.astimezone(UTC)
    shifted_day = (utc_now - timedelta(hours=RESET_HOUR_UTC)).date()
    next_day = shifted_day + timedelta(days=1)
    reset_at = datetime.combine(next_day, time(RESET_HOUR_UTC), tzinfo=UTC)
    return PuzzleWindow(puzzle_key=shifted_day.isoformat(), reset_at=reset_at)


def window_for_date(puzzle_date: date) -> PuzzleWindow:
    reset_at = datetime.combine(
        puzzle_date + timedelta(days=1), time(RESET_HOUR_UTC), tzinfo=UTC
    )
    return PuzzleWindow(puzzle_key=puzzle_date.isoformat(), reset_at=reset_at)

