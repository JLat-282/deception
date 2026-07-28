from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import DEFAULT_DATA_DIR, Settings
from backend.app.main import create_app


@dataclass
class MutableClock:
    current: datetime

    def __call__(self) -> datetime:
        return self.current


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock(datetime(2026, 7, 28, 12, 0, tzinfo=UTC))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        db_path=tmp_path / "deception.sqlite",
        daily_seed="test-seed",
        answer_list_version="test-answers-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
    )


@pytest.fixture
def app(settings: Settings, clock: MutableClock):
    return create_app(settings=settings, now_provider=clock)


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client

