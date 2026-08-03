from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


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


FeedbackMarker = Literal["G", "Y", "B"]


class DeceptionChange(APIModel):
    tile_index: int
    letter: str
    truthful_feedback: FeedbackMarker
    displayed_feedback: FeedbackMarker


class ActivatedDeceptionReveal(APIModel):
    outcome: Literal["activated"]
    scheduled_attempt: int
    change: DeceptionChange


class NotActivatedDeceptionReveal(APIModel):
    outcome: Literal["notActivated"]
    scheduled_attempt: int
    reason: Literal[
        "notReached",
        "winningGuess",
        "finalAttempt",
        "noEligibleLie",
    ]


DeceptionEvent = Annotated[
    ActivatedDeceptionReveal | NotActivatedDeceptionReveal,
    Field(discriminator="outcome"),
]


class DeceptionReveal(APIModel):
    events: list[DeceptionEvent] = Field(min_length=1, max_length=2)


class ReverseEntryUpdate(APIModel):
    state: Literal["activated", "resolved"]


class ActivatedGuessTimer(APIModel):
    state: Literal["activated"]
    duration_seconds: Literal[10, 30]
    starts_at: datetime
    deadline_at: datetime


class CompletedGuessTimer(APIModel):
    state: Literal["completed"]


class ExpiredGuessTimer(APIModel):
    state: Literal["expired"]


class ActivatedBlackout(APIModel):
    state: Literal["activated"]


class GuessResponse(APIModel):
    guess: str
    feedback: str
    attempt: int
    status: GameStatus
    answer: str | None = None
    deception: DeceptionReveal | None = None
    reverse_entry: ReverseEntryUpdate | None = None
    timer: ActivatedGuessTimer | CompletedGuessTimer | None = None
    blackout: ActivatedBlackout | None = None


class TimedOutResponse(APIModel):
    timed_out: Literal[True] = True
    attempt: int
    status: GameStatus
    answer: str | None = None
    deception: DeceptionReveal | None = None
    timer: ExpiredGuessTimer


AttemptResponse = GuessResponse | TimedOutResponse


class HealthResponse(APIModel):
    status: Literal["ok"]
    database: Literal["ok"]


class ErrorBody(APIModel):
    code: str
    message: str


class ErrorResponse(APIModel):
    error: ErrorBody
