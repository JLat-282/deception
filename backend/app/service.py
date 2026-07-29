from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import secrets
from typing import Callable

from .clock import PuzzleWindow, daily_window
from .config import Settings
from .deception import DeceptionEngine, VisibleGuess
from .engine import MAX_GUESSES, WORD_LENGTH, TruthEngine
from .errors import DomainError, GuessValidationError
from .repository import (
    CURRENT_RULES_VERSION,
    DeceptionSchedule,
    Repository,
    StoredGame,
    StoredGuess,
)
from .schemas import (
    ActivatedDeceptionReveal,
    BootstrapResponse,
    DailyInfo,
    DeceptionChange,
    GameConfig,
    GuessResponse,
    NotActivatedDeceptionReveal,
    StartGameResponse,
)


NowProvider = Callable[[], datetime]
SeedProvider = Callable[[], str]


class GameService:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        engine: TruthEngine,
        now_provider: NowProvider | None = None,
        deception_engine: DeceptionEngine | None = None,
        session_seed_provider: SeedProvider | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.engine = engine
        self.deception_engine = deception_engine or DeceptionEngine(engine)
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.session_seed_provider = (
            session_seed_provider
            or settings.fixed_session_seed
            and (lambda: settings.fixed_session_seed or "")
            or (lambda: secrets.token_urlsafe(32))
        )
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

    def _create_schedule(
        self,
        connection,
        game: StoredGame,
        now: datetime,
    ) -> DeceptionSchedule:
        existing = self._get_schedule(connection, game)
        if existing is not None:
            return existing
        seed = self.session_seed_provider()
        scheduled_attempt = (
            self.settings.fixed_lie_row
            or self.deception_engine.scheduled_attempt(seed)
        )
        if game.mode == "daily":
            if game.puzzle_key is None:
                raise DomainError(
                    503,
                    "SERVICE_UNAVAILABLE",
                    "The Daily game is missing its puzzle key.",
                )
            return self.repository.create_deception_schedule(
                connection,
                scheduled_attempt=scheduled_attempt,
                seed=seed,
                created_at=now,
                daily_puzzle_key=game.puzzle_key,
            )
        return self.repository.create_deception_schedule(
            connection,
            scheduled_attempt=scheduled_attempt,
            seed=seed,
            created_at=now,
            game_id=game.game_id,
        )

    def _get_schedule(
        self, connection, game: StoredGame
    ) -> DeceptionSchedule | None:
        if game.mode == "daily":
            if game.puzzle_key is None:
                return None
            return self.repository.get_deception_schedule(
                connection, daily_puzzle_key=game.puzzle_key
            )
        return self.repository.get_deception_schedule(
            connection, game_id=game.game_id
        )

    def _ensure_current_rules(
        self, connection, game: StoredGame, now: datetime
    ) -> tuple[StoredGame, DeceptionSchedule | None]:
        if game.rules_version < CURRENT_RULES_VERSION:
            if game.guess_count > 0:
                return game, None
            self.repository.upgrade_game_rules(connection, game.game_id)
            upgraded = self.repository.get_game(connection, game.game_id)
            if upgraded is None:
                raise DomainError(
                    503,
                    "SERVICE_UNAVAILABLE",
                    "The game rules could not be upgraded.",
                )
            game = upgraded
        schedule = self._get_schedule(connection, game)
        if schedule is None:
            schedule = self._create_schedule(connection, game, now)
        return game, schedule

    @staticmethod
    def _deception_reveal(
        schedule: DeceptionSchedule,
        guesses: list[StoredGuess],
        status: str,
    ) -> ActivatedDeceptionReveal | NotActivatedDeceptionReveal:
        for row in guesses:
            if row.truth_feedback == row.display_feedback:
                continue
            tile_index = next(
                index
                for index, markers in enumerate(
                    zip(row.truth_feedback, row.display_feedback)
                )
                if markers[0] != markers[1]
            )
            return ActivatedDeceptionReveal(
                outcome="activated",
                scheduled_attempt=schedule.scheduled_attempt,
                change=DeceptionChange(
                    tile_index=tile_index,
                    letter=row.guess[tile_index],
                    truthful_feedback=row.truth_feedback[tile_index],
                    displayed_feedback=row.display_feedback[tile_index],
                ),
            )

        guess_count = len(guesses)
        if schedule.scheduled_attempt > guess_count:
            reason = "notReached"
        elif (
            status == "won"
            and schedule.scheduled_attempt == guess_count
        ):
            reason = "winningGuess"
        elif schedule.scheduled_attempt == MAX_GUESSES:
            reason = "finalAttempt"
        else:
            reason = "noEligibleLie"
        return NotActivatedDeceptionReveal(
            outcome="notActivated",
            scheduled_attempt=schedule.scheduled_attempt,
            reason=reason,
        )

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
                    pending_game, _ = self._ensure_current_rules(
                        connection, pending_game, now
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
            self._create_schedule(connection, game, now)

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

            game, schedule = self._ensure_current_rules(
                connection, game, now
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

            if (
                schedule is not None
                and attempt == schedule.scheduled_attempt
                and attempt < MAX_GUESSES
                and status != "won"
            ):
                prior_guesses = self.repository.list_guesses(
                    connection, game_id
                )
                decision = self.deception_engine.choose_feedback(
                    guess=guess,
                    real_answer=game.answer,
                    truth_feedback=truth_feedback,
                    prior_history=(
                        VisibleGuess(
                            guess=row.guess,
                            feedback=row.display_feedback,
                        )
                        for row in prior_guesses
                    ),
                    seed=schedule.seed,
                )
                display_feedback = decision.feedback

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
            deception = None
            if status in {"won", "lost"} and schedule is not None:
                deception = self._deception_reveal(
                    schedule,
                    self.repository.list_guesses(connection, game_id),
                    status,
                )

        return GuessResponse(
            guess=guess,
            feedback=display_feedback,
            attempt=attempt,
            status=status,
            answer=game.answer if status in {"won", "lost"} else None,
            deception=deception,
        )
