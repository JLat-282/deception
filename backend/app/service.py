from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import secrets
from typing import Callable

from .clock import PuzzleWindow, daily_window
from .config import Settings
from .engine import MAX_GUESSES, WORD_LENGTH, TruthEngine
from .errors import DomainError, GuessValidationError
from .repository import Repository, StoredGame
from .schemas import (
    BootstrapResponse,
    DailyInfo,
    GameConfig,
    GuessResponse,
    StartGameResponse,
)


NowProvider = Callable[[], datetime]


class GameService:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        engine: TruthEngine,
        now_provider: NowProvider | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.engine = engine
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.config = GameConfig(
            word_length=WORD_LENGTH,
            max_guesses=MAX_GUESSES,
        )

        if settings.fixed_answer:
            fixed = settings.fixed_answer.strip().lower()
            if fixed not in engine.answers:
                raise ValueError(
                    "DECEPTION_FIXED_ANSWER must be present in the answer list."
                )

    @staticmethod
    def new_device_id() -> str:
        return secrets.token_urlsafe(32)

    def now(self) -> datetime:
        current = self.now_provider()
        if current.tzinfo is None:
            raise ValueError("The game clock must return a timezone-aware datetime.")
        return current.astimezone(UTC)

    def ensure_device(self, device_id: str) -> None:
        now = self.now()
        with self.repository.transaction() as connection:
            self.repository.ensure_device(connection, device_id, now)

    def bootstrap(self, device_id: str) -> BootstrapResponse:
        now = self.now()
        window = daily_window(now)
        with self.repository.transaction() as connection:
            self.repository.ensure_device(connection, device_id, now)
            attempt = self.repository.get_daily_attempt(
                connection, device_id, window.puzzle_key
            )
        availability = (
            "used" if attempt is not None and attempt.consumed_at else "available"
        )
        return BootstrapResponse(
            config=self.config,
            daily=DailyInfo(
                puzzle_key=window.puzzle_key,
                availability=availability,
                reset_at=window.reset_at,
            ),
        )

    def _daily_answer(self, window: PuzzleWindow) -> str:
        if self.settings.fixed_answer:
            return self.settings.fixed_answer.lower()
        message = (
            f"{self.settings.answer_list_version}:{window.puzzle_key}"
        ).encode("utf-8")
        digest = hmac.new(
            self.settings.daily_seed.encode("utf-8"),
            message,
            hashlib.sha256,
        ).digest()
        index = int.from_bytes(digest[:8], "big") % len(self.engine.answers)
        return self.engine.answers[index]

    def _practice_answer(self, previous_answer: str | None) -> str:
        if self.settings.fixed_answer:
            return self.settings.fixed_answer.lower()
        choices = [
            answer for answer in self.engine.answers if answer != previous_answer
        ]
        return secrets.choice(choices or list(self.engine.answers))

    def start_game(
        self, device_id: str, mode: str
    ) -> StartGameResponse:
        if mode not in {"daily", "practice"}:
            raise DomainError(
                400, "INVALID_MODE", "Choose either daily or practice mode."
            )

        now = self.now()
        game_id = secrets.token_urlsafe(24)
        puzzle_key: str | None = None

        with self.repository.transaction() as connection:
            self.repository.ensure_device(connection, device_id, now)

            if mode == "daily":
                window = daily_window(now)
                puzzle_key = window.puzzle_key
                attempt = self.repository.get_daily_attempt(
                    connection, device_id, puzzle_key
                )
                if attempt is not None:
                    if attempt.consumed_at is not None:
                        raise DomainError(
                            409,
                            "DAILY_ALREADY_USED",
                            "Today’s Daily attempt has already been used.",
                        )
                    pending_game = self.repository.get_game(
                        connection, attempt.game_id
                    )
                    if pending_game is None:
                        raise DomainError(
                            503,
                            "SERVICE_UNAVAILABLE",
                            "The pending Daily game could not be restored.",
                        )
                    return self._start_response(pending_game)

                answer = self.repository.get_daily_puzzle(
                    connection, puzzle_key
                )
                if answer is None:
                    answer = self._daily_answer(window)
                    self.repository.create_daily_puzzle(
                        connection,
                        puzzle_key,
                        answer,
                        self.settings.answer_list_version,
                        now,
                    )
                game = self.repository.create_game(
                    connection,
                    game_id,
                    device_id,
                    "daily",
                    answer,
                    now,
                    puzzle_key,
                )
                self.repository.create_daily_attempt(
                    connection, device_id, puzzle_key, game_id, now
                )
            else:
                previous_answer = self.repository.last_practice_answer(
                    connection, device_id
                )
                answer = self._practice_answer(previous_answer)
                game = self.repository.create_game(
                    connection,
                    game_id,
                    device_id,
                    "practice",
                    answer,
                    now,
                )

        return self._start_response(game)

    def _start_response(self, game: StoredGame) -> StartGameResponse:
        return StartGameResponse(
            game_id=game.game_id,
            mode=game.mode,
            config=self.config,
            puzzle_key=game.puzzle_key,
        )

    def submit_guess(
        self, device_id: str, game_id: str, raw_guess: str
    ) -> GuessResponse:
        try:
            guess = self.engine.validate_guess(raw_guess)
        except GuessValidationError as error:
            raise DomainError(400, error.code, error.message) from error

        now = self.now()
        with self.repository.transaction() as connection:
            game = self.repository.get_game(connection, game_id)
            if game is None or game.device_id != device_id:
                raise DomainError(
                    404, "GAME_NOT_FOUND", "That game could not be found."
                )
            if game.status != "playing":
                raise DomainError(
                    409, "GAME_FINISHED", "This game has already finished."
                )

            truth_feedback = self.engine.evaluate(guess, game.answer)
            display_feedback = truth_feedback
            attempt = game.guess_count + 1

            if guess == game.answer:
                status = "won"
            elif attempt >= MAX_GUESSES:
                status = "lost"
            else:
                status = "playing"

            if game.mode == "daily":
                if game.puzzle_key is None:
                    raise DomainError(
                        503,
                        "SERVICE_UNAVAILABLE",
                        "The Daily game is missing its puzzle key.",
                    )
                daily_attempt = self.repository.get_daily_attempt(
                    connection, device_id, game.puzzle_key
                )
                if daily_attempt is None or daily_attempt.game_id != game_id:
                    raise DomainError(
                        503,
                        "SERVICE_UNAVAILABLE",
                        "The Daily attempt state is unavailable.",
                    )
                if daily_attempt.consumed_at is None:
                    self.repository.consume_daily_attempt(
                        connection,
                        device_id,
                        game.puzzle_key,
                        game_id,
                        now,
                    )

            self.repository.record_guess(
                connection,
                game_id,
                attempt,
                guess,
                truth_feedback,
                display_feedback,
                status,
                now,
            )

        return GuessResponse(
            guess=guess,
            feedback=display_feedback,
            attempt=attempt,
            status=status,
            answer=game.answer if status in {"won", "lost"} else None,
        )

