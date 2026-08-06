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
DailyRunStatus = Literal[
    "unstarted",
    "active",
    "checkpoint",
    "failed",
    "forfeited",
    "completed",
    "expired",
]


class GameConfig(APIModel):
    word_length: int
    max_guesses: int


class DifficultyPresetSummary(APIModel):
    preset_key: str
    name: str
    rank: int
    pressure: str
    description: str
    available: bool


class DailyInfo(APIModel):
    puzzle_key: str
    availability: Literal["available", "used"]
    reset_at: datetime
    status: DailyRunStatus
    current_stage: int = Field(ge=1, le=4)
    cleared_stages: int = Field(ge=0, le=4)
    current_preset: DifficultyPresetSummary | None = None


class BootstrapResponse(APIModel):
    config: GameConfig
    daily: DailyInfo
    presets: list[DifficultyPresetSummary]


class StartGameRequest(APIModel):
    mode: GameMode
    preset_key: str | None = None
    continuation_token: str | None = Field(default=None, min_length=20, max_length=256)


class StartGameResponse(APIModel):
    game_id: str
    mode: GameMode
    config: GameConfig
    preset: DifficultyPresetSummary
    puzzle_key: str | None = None
    daily_stage: int | None = Field(default=None, ge=1, le=4)


class GuessRequest(APIModel):
    guess: str
    continuation_token: str | None = Field(default=None, min_length=20, max_length=256)


class ContinuationRequest(APIModel):
    continuation_token: str | None = Field(default=None, min_length=20, max_length=256)


FeedbackMarker = Literal["G", "Y", "B"]


class DeceptionChange(APIModel):
    tile_index: int
    letter: str
    truthful_feedback: FeedbackMarker
    displayed_feedback: FeedbackMarker


class ActivatedDeceptionReveal(APIModel):
    outcome: Literal["activated"]
    kind: Literal["feedbackLie", "falseVictory"]
    scheduled_attempt: int
    changes: list[DeceptionChange] = Field(min_length=1, max_length=2)


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
    events: list[DeceptionEvent] = Field(min_length=1, max_length=5)


class ReverseEntryUpdate(APIModel):
    state: Literal["activated", "resolved", "continued"]


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


class ActivatedIntrusion(APIModel):
    state: Literal["activated"]
    placement: Literal["upperLeft", "upperRight", "lowerLeft", "lowerRight"]


class PunishmentUpdate(APIModel):
    kind: Literal[
        "timer",
        "reverseEntry",
        "blackout",
        "intrusion",
        "blindEntry",
        "corruptedHistory",
        "noRevision",
        "forcedCommitment",
        "memoryTax",
    ]
    state: Literal["activated", "resolved", "continued", "expired"]
    effective_attempt: int = Field(ge=1, le=6)
    duration_seconds: Literal[10, 30] | None = None
    starts_at: datetime | None = None
    deadline_at: datetime | None = None
    row_attempt: int | None = Field(default=None, ge=1, le=6)
    retain_rows: int | None = Field(default=None, ge=1, le=5)
    placement: Literal[
        "upperLeft", "upperRight", "lowerLeft", "lowerRight"
    ] | None = None


class PunishmentReportEvent(APIModel):
    kind: Literal[
        "timer",
        "reverseEntry",
        "blackout",
        "intrusion",
        "blindEntry",
        "corruptedHistory",
        "noRevision",
        "forcedCommitment",
        "memoryTax",
    ]
    ordinal: int = Field(ge=1)
    trigger_attempt: int = Field(ge=1, le=6)
    effective_attempt: int = Field(ge=1, le=6)
    outcome: Literal["activated", "missed", "superseded", "notReached"]


class PunishmentReport(APIModel):
    events: list[PunishmentReportEvent]


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
    intrusion: ActivatedIntrusion | None = None
    punishments: list[PunishmentUpdate] | None = None
    punishment_report: PunishmentReport | None = None


class TimedOutResponse(APIModel):
    timed_out: Literal[True] = True
    attempt: int
    status: GameStatus
    answer: str | None = None
    deception: DeceptionReveal | None = None
    reverse_entry: ReverseEntryUpdate | None = None
    timer: ExpiredGuessTimer
    next_timer: ActivatedGuessTimer | None = None
    punishments: list[PunishmentUpdate] | None = None
    punishment_report: PunishmentReport | None = None


class InvalidCommitmentResponse(APIModel):
    consumed: Literal[True] = True
    reason: Literal["invalidCommitment"] = "invalidCommitment"
    attempted_guess: str
    attempt: int
    status: GameStatus
    answer: str | None = None
    deception: DeceptionReveal | None = None
    reverse_entry: ReverseEntryUpdate | None = None
    next_timer: ActivatedGuessTimer | None = None
    punishments: list[PunishmentUpdate] | None = None
    punishment_report: PunishmentReport | None = None


AttemptResponse = GuessResponse | TimedOutResponse | InvalidCommitmentResponse


class HealthResponse(APIModel):
    status: Literal["ok"]
    database: Literal["ok"]


class ErrorBody(APIModel):
    code: str
    message: str


class ErrorResponse(APIModel):
    error: ErrorBody
