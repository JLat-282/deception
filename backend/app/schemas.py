from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class APIModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
    )


GameMode = Literal["daily", "practice"]
GameStatus = Literal["playing", "won", "lost"]


class GameConfig(APIModel):
    word_length: int
    max_guesses: int


class DailyInfo(APIModel):
    puzzle_key: str
    availability: Literal["available", "used"]
    reset_at: datetime


class BootstrapResponse(APIModel):
    config: GameConfig
    daily: DailyInfo


class StartGameRequest(APIModel):
    mode: GameMode


class StartGameResponse(APIModel):
    game_id: str
    mode: GameMode
    config: GameConfig
    puzzle_key: str | None = None


class GuessRequest(APIModel):
    guess: str


class GuessResponse(APIModel):
    guess: str
    feedback: str
    attempt: int
    status: GameStatus
    answer: str | None = None


class HealthResponse(APIModel):
    status: Literal["ok"]
    database: Literal["ok"]


class ErrorBody(APIModel):
    code: str
    message: str


class ErrorResponse(APIModel):
    error: ErrorBody

