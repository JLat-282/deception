from datetime import UTC, datetime

import pytest

from backend.app.clock import daily_window


def test_daily_window_before_0300_utc_uses_previous_date() -> None:
    window = daily_window(datetime(2026, 7, 28, 2, 59, 59, tzinfo=UTC))

    assert window.puzzle_key == "2026-07-27"
    assert window.reset_at == datetime(2026, 7, 28, 3, 0, tzinfo=UTC)


def test_daily_window_at_0300_utc_uses_new_date() -> None:
    window = daily_window(datetime(2026, 7, 28, 3, 0, tzinfo=UTC))

    assert window.puzzle_key == "2026-07-28"
    assert window.reset_at == datetime(2026, 7, 29, 3, 0, tzinfo=UTC)


def test_daily_window_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        daily_window(datetime(2026, 7, 28, 3, 0))

