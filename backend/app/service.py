from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from typing import Callable

from .clock import PuzzleWindow, daily_window
from .config import Settings
from .deception import DeceptionEngine, VisibleGuess
from .engine import MAX_GUESSES, WORD_LENGTH, TruthEngine, normalize_word
from .errors import DomainError, GuessValidationError
from .repository import (
    BlackoutState,
    CURRENT_RULES_VERSION,
    DeceptionSchedule,
    GuessTimerState,
    Repository,
    ReverseEntryState,
    StoredGame,
    StoredGuess,
)
from .schemas import (
    ActivatedBlackout,
    ActivatedGuessTimer,
    ActivatedDeceptionReveal,
    AttemptResponse,
    BootstrapResponse,
    DailyInfo,
    DeceptionChange,
    DeceptionReveal,
    GameConfig,
    GuessResponse,
    NotActivatedDeceptionReveal,
    CompletedGuessTimer,
    ReverseEntryUpdate,
    StartGameResponse,
    TimedOutResponse,
    ExpiredGuessTimer,
)


NowProvider = Callable[[], datetime]
SeedProvider = Callable[[], str]
TIMER_GAME_PROBABILITY = 0.45
THIRTY_SECOND_TIMER_PROBABILITY = 0.70
TIMER_ACTIVATION_DELAY = timedelta(seconds=1)
BLACKOUT_GAME_PROBABILITY = 0.10


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

    def _create_schedules(
        self,
        connection,
        game: StoredGame,
        now: datetime,
    ) -> list[DeceptionSchedule]:
        existing = self._get_schedules(connection, game)
        if existing:
            return existing
        seed = self.session_seed_provider()
        scheduled_attempts = (
            self.settings.fixed_lie_rows
            or (
                (self.settings.fixed_lie_row,)
                if self.settings.fixed_lie_row is not None
                else None
            )
            or self.deception_engine.scheduled_attempts(seed)
        )
        if game.mode == "daily":
            if game.puzzle_key is None:
                raise DomainError(
                    503,
                    "SERVICE_UNAVAILABLE",
                    "The Daily game is missing its puzzle key.",
                )
            return self.repository.replace_deception_schedules(
                connection,
                scheduled_attempts=scheduled_attempts,
                seed=seed,
                created_at=now,
                daily_puzzle_key=game.puzzle_key,
            )
        return self.repository.replace_deception_schedules(
            connection,
            scheduled_attempts=scheduled_attempts,
            seed=seed,
            created_at=now,
            game_id=game.game_id,
        )

    def _get_schedules(
        self, connection, game: StoredGame
    ) -> list[DeceptionSchedule]:
        if game.mode == "daily":
            if game.puzzle_key is None:
                return []
            return self.repository.list_deception_schedules(
                connection, daily_puzzle_key=game.puzzle_key
            )
        return self.repository.list_deception_schedules(
            connection, game_id=game.game_id
        )

    def _ensure_current_rules(
        self, connection, game: StoredGame, now: datetime
    ) -> tuple[StoredGame, list[DeceptionSchedule]]:
        if game.rules_version < CURRENT_RULES_VERSION:
            if game.guess_count > 0:
                if game.rules_version == 1:
                    return game, []
                return game, self._get_schedules(connection, game)
            self.repository.upgrade_game_rules(connection, game.game_id)
            upgraded = self.repository.get_game(connection, game.game_id)
            if upgraded is None:
                raise DomainError(
                    503,
                    "SERVICE_UNAVAILABLE",
                    "The game rules could not be upgraded.",
                )
            game = upgraded
        schedules = self._get_schedules(connection, game)
        if not schedules:
            schedules = self._create_schedules(connection, game, now)
        blackout_state = self._ensure_blackout_state(connection, game, now)
        self._ensure_reverse_entry_state(connection, game, now)
        self._ensure_guess_timer_state(
            connection, game, now, blackout_state=blackout_state
        )
        return game, schedules

    def _ensure_reverse_entry_state(
        self, connection, game: StoredGame, now: datetime
    ) -> ReverseEntryState | None:
        if (
            not self.settings.reverse_entry_enabled
            or game.rules_version < CURRENT_RULES_VERSION
        ):
            return None
        state = self.repository.get_reverse_entry_state(
            connection, game.game_id
        )
        if state is not None:
            return state
        return self.repository.create_reverse_entry_state(
            connection,
            game.game_id,
            self.session_seed_provider(),
            now,
        )

    def _ensure_blackout_state(
        self, connection, game: StoredGame, now: datetime
    ) -> BlackoutState | None:
        if (
            not self.settings.blackout_enabled
            or game.rules_version < CURRENT_RULES_VERSION
        ):
            return None
        existing = self.repository.get_blackout_state(
            connection, game.game_id
        )
        if existing is not None:
            return existing

        seed = self.session_seed_provider()
        inclusion_roll = (
            self.settings.fixed_blackout_roll
            if self.settings.fixed_blackout_roll is not None
            else self._seeded_probability(seed, "blackout:v1:inclusion")
        )
        if inclusion_roll >= BLACKOUT_GAME_PROBABILITY:
            return self.repository.create_blackout_state(
                connection, game.game_id, seed, None, now
            )

        scheduled_attempt = self.settings.fixed_blackout_attempt
        if scheduled_attempt is None:
            attempt_digest = hmac.new(
                seed.encode("utf-8"),
                b"blackout:v1:attempt",
                hashlib.sha256,
            ).digest()
            scheduled_attempt = 3 + int.from_bytes(
                attempt_digest[:8], "big"
            ) % 3
        return self.repository.create_blackout_state(
            connection, game.game_id, seed, scheduled_attempt, now
        )

    @staticmethod
    def _blackout_blocked_attempts(
        blackout_state: BlackoutState | None,
    ) -> set[int]:
        if (
            blackout_state is None
            or blackout_state.status == "skipped"
            or blackout_state.scheduled_attempt is None
        ):
            return set()
        return {
            blackout_state.scheduled_attempt,
            blackout_state.scheduled_attempt + 1,
        }

    @staticmethod
    def _seeded_probability(seed: str, label: str) -> float:
        digest = hmac.new(
            seed.encode("utf-8"),
            label.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return int.from_bytes(digest[:8], "big") / 2**64

    def _ensure_guess_timer_state(
        self,
        connection,
        game: StoredGame,
        now: datetime,
        *,
        blackout_state: BlackoutState | None = None,
    ) -> GuessTimerState | None:
        if (
            not self.settings.guess_timer_enabled
            or game.rules_version < CURRENT_RULES_VERSION
        ):
            return None
        existing = self.repository.get_guess_timer_state(
            connection, game.game_id
        )
        if existing is not None:
            return existing

        seed = self.session_seed_provider()
        inclusion_roll = (
            self.settings.fixed_timer_roll
            if self.settings.fixed_timer_roll is not None
            else self._seeded_probability(
                seed, "guess-timer:v1:inclusion"
            )
        )
        if inclusion_roll >= TIMER_GAME_PROBABILITY:
            return self.repository.create_guess_timer_state(
                connection,
                game.game_id,
                seed,
                None,
                None,
                now,
            )

        blocked_attempts = self._blackout_blocked_attempts(blackout_state)
        eligible_attempts = [
            attempt
            for attempt in range(2, 7)
            if attempt not in blocked_attempts
        ]
        scheduled_attempt = self.settings.fixed_timer_attempt
        if scheduled_attempt not in eligible_attempts:
            attempt_digest = hmac.new(
                seed.encode("utf-8"),
                b"guess-timer:v2:attempt",
                hashlib.sha256,
            ).digest()
            scheduled_attempt = eligible_attempts[
                int.from_bytes(attempt_digest[:8], "big")
                % len(eligible_attempts)
            ]

        duration_seconds = self.settings.fixed_timer_duration
        if duration_seconds is None:
            duration_roll = self._seeded_probability(
                seed, "guess-timer:v1:duration"
            )
            duration_seconds = (
                30
                if duration_roll < THIRTY_SECOND_TIMER_PROBABILITY
                else 10
            )

        return self.repository.create_guess_timer_state(
            connection,
            game.game_id,
            seed,
            scheduled_attempt,
            duration_seconds,
            now,
        )

    def _activate_guess_timer(
        self,
        connection,
        timer_state: GuessTimerState,
        now: datetime,
    ) -> ActivatedGuessTimer:
        if timer_state.duration_seconds not in {10, 30}:
            raise DomainError(
                503,
                "SERVICE_UNAVAILABLE",
                "The Guess Timer duration is unavailable.",
            )
        starts_at = now + TIMER_ACTIVATION_DELAY
        deadline_at = starts_at + timedelta(
            seconds=timer_state.duration_seconds
        )
        active = self.repository.activate_guess_timer(
            connection,
            timer_state.game_id,
            starts_at,
            deadline_at,
            now,
        )
        if (
            active.starts_at is None
            or active.deadline_at is None
            or active.duration_seconds not in {10, 30}
        ):
            raise DomainError(
                503,
                "SERVICE_UNAVAILABLE",
                "The Guess Timer could not be activated.",
            )
        return ActivatedGuessTimer(
            state="activated",
            duration_seconds=active.duration_seconds,
            starts_at=active.starts_at,
            deadline_at=active.deadline_at,
        )

    def _reverse_entry_trigger_reason(
        self,
        state: ReverseEntryState,
        display_feedback: str,
        attempt: int,
    ) -> str | None:
        if display_feedback.count("B") >= 4:
            return "lowInformation"
        if self.settings.fixed_reverse_entry_roll is not None:
            roll = self.settings.fixed_reverse_entry_roll
        else:
            digest = hmac.new(
                state.seed.encode("utf-8"),
                f"reverse-entry:v1:{attempt}".encode("utf-8"),
                hashlib.sha256,
            ).digest()
            roll = int.from_bytes(digest[:8], "big") / 2**64
        return "chance" if roll < 0.10 else None

    @staticmethod
    def _deception_reveal(
        schedule: DeceptionSchedule,
        guesses: list[StoredGuess],
        status: str,
        guess_count: int,
    ) -> ActivatedDeceptionReveal | NotActivatedDeceptionReveal:
        row = next(
            (
                guess
                for guess in guesses
                if guess.attempt == schedule.scheduled_attempt
            ),
            None,
        )
        if row is not None and row.truth_feedback != row.display_feedback:
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
            self._create_schedules(connection, game, now)
            blackout_state = self._ensure_blackout_state(
                connection, game, now
            )
            self._ensure_reverse_entry_state(connection, game, now)
            self._ensure_guess_timer_state(
                connection,
                game,
                now,
                blackout_state=blackout_state,
            )

        return self._start_response(game)

    def _start_response(self, game: StoredGame) -> StartGameResponse:
        return StartGameResponse(
            game_id=game.game_id,
            mode=game.mode,
            config=self.config,
            puzzle_key=game.puzzle_key,
        )

    def _terminal_deception(
        self,
        connection,
        game_id: str,
        schedules: list[DeceptionSchedule],
        status: str,
        guess_count: int,
    ) -> DeceptionReveal | None:
        if status not in {"won", "lost"} or not schedules:
            return None
        terminal_guesses = self.repository.list_guesses(
            connection, game_id
        )
        return DeceptionReveal(
            events=[
                self._deception_reveal(
                    item,
                    terminal_guesses,
                    status,
                    guess_count,
                )
                for item in schedules
            ]
        )

    def _consume_timer_timeout(
        self,
        connection,
        game: StoredGame,
        schedules: list[DeceptionSchedule],
        timer_state: GuessTimerState,
        now: datetime,
    ) -> TimedOutResponse:
        attempt = game.guess_count + 1
        if (
            timer_state.status != "active"
            or timer_state.scheduled_attempt != attempt
        ):
            raise DomainError(
                409,
                "TIMER_NOT_ACTIVE",
                "There is no active timer for this guess.",
            )
        status = "lost" if attempt >= MAX_GUESSES else "playing"
        self.repository.record_timeout(
            connection,
            game.game_id,
            attempt,
            status,
            now,
        )
        self.repository.resolve_guess_timer(
            connection,
            game.game_id,
            "expired",
            attempt,
            now,
        )
        deception = self._terminal_deception(
            connection,
            game.game_id,
            schedules,
            status,
            attempt,
        )
        return TimedOutResponse(
            attempt=attempt,
            status=status,
            answer=game.answer if status == "lost" else None,
            deception=deception,
            timer=ExpiredGuessTimer(state="expired"),
        )

    def expire_timer(
        self, device_id: str, game_id: str
    ) -> TimedOutResponse:
        now = self.now()
        with self.repository.transaction() as connection:
            game = self.repository.get_game(connection, game_id)
            if game is None or game.device_id != device_id:
                raise DomainError(
                    404, "GAME_NOT_FOUND", "That game could not be found."
                )
            game, schedules = self._ensure_current_rules(
                connection, game, now
            )
            timer_state = self.repository.get_guess_timer_state(
                connection, game_id
            )
            if (
                timer_state is not None
                and timer_state.status == "expired"
                and timer_state.resolved_attempt is not None
            ):
                deception = self._terminal_deception(
                    connection,
                    game.game_id,
                    schedules,
                    game.status,
                    game.guess_count,
                )
                return TimedOutResponse(
                    attempt=timer_state.resolved_attempt,
                    status=game.status,
                    answer=game.answer if game.status == "lost" else None,
                    deception=deception,
                    timer=ExpiredGuessTimer(state="expired"),
                )
            if game.status != "playing":
                raise DomainError(
                    409, "GAME_FINISHED", "This game has already finished."
                )
            if (
                timer_state is None
                or timer_state.status != "active"
                or timer_state.deadline_at is None
            ):
                raise DomainError(
                    409,
                    "TIMER_NOT_ACTIVE",
                    "There is no active timer for this guess.",
                )
            if now < timer_state.deadline_at:
                raise DomainError(
                    409,
                    "TIMER_STILL_RUNNING",
                    "The timer is still running.",
                )
            return self._consume_timer_timeout(
                connection,
                game,
                schedules,
                timer_state,
                now,
            )

    def submit_guess(
        self, device_id: str, game_id: str, raw_guess: str
    ) -> AttemptResponse:
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

            game, schedules = self._ensure_current_rules(
                connection, game, now
            )
            timer_state = self.repository.get_guess_timer_state(
                connection, game_id
            )
            blackout_state = self.repository.get_blackout_state(
                connection, game_id
            )
            blackout_blocked_attempts = self._blackout_blocked_attempts(
                blackout_state
            )
            attempt = game.guess_count + 1
            timer_active = (
                timer_state is not None
                and timer_state.status == "active"
                and timer_state.scheduled_attempt == attempt
            )
            if (
                timer_active
                and timer_state is not None
                and timer_state.deadline_at is not None
                and now >= timer_state.deadline_at
            ):
                return self._consume_timer_timeout(
                    connection,
                    game,
                    schedules,
                    timer_state,
                    now,
                )
            reverse_entry_state = self.repository.get_reverse_entry_state(
                connection, game_id
            )
            reverse_entry_active = (
                reverse_entry_state is not None
                and reverse_entry_state.status == "active"
                and not timer_active
            )
            submitted_guess = normalize_word(raw_guess)
            if reverse_entry_active:
                submitted_guess = submitted_guess[::-1]
            try:
                guess = self.engine.validate_guess(submitted_guess)
            except GuessValidationError as error:
                if reverse_entry_active and error.code == "INVALID_WORD":
                    raise DomainError(
                        400,
                        "INVALID_REVERSED_WORD",
                        "That guess isn’t accepted.",
                    ) from error
                raise DomainError(400, error.code, error.message) from error

            truth_feedback = self.engine.evaluate(guess, game.answer)
            display_feedback = truth_feedback

            if guess == game.answer:
                status = "won"
            elif attempt >= MAX_GUESSES:
                status = "lost"
            else:
                status = "playing"

            schedule = next(
                (
                    item
                    for item in schedules
                    if item.scheduled_attempt == attempt
                ),
                None,
            )
            if (
                schedule is not None
                and attempt < MAX_GUESSES
                and status != "won"
            ):
                prior_guesses = self.repository.list_guesses(
                    connection, game_id
                )
                excluded_tile_indexes = {
                    index
                    for row in prior_guesses
                    for index, markers in enumerate(
                        zip(row.truth_feedback, row.display_feedback)
                    )
                    if markers[0] != markers[1]
                }
                decision_seed = schedule.seed
                if schedule.strategy_version >= 2:
                    decision_seed = hmac.new(
                        schedule.seed.encode("utf-8"),
                        f"decision:v2:{schedule.ordinal}".encode("utf-8"),
                        hashlib.sha256,
                    ).hexdigest()
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
                    seed=decision_seed,
                    excluded_tile_indexes=excluded_tile_indexes,
                    allow_constraint_fallback=(
                        schedule.strategy_version >= 3
                    ),
                    time_budget_ms=self.settings.deception_decision_budget_ms,
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
            timer_update = None
            if timer_active:
                self.repository.resolve_guess_timer(
                    connection,
                    game_id,
                    "completed",
                    attempt,
                    now,
                )
                timer_update = CompletedGuessTimer(state="completed")

            timer_targets_next_attempt = (
                timer_state is not None
                and timer_state.status == "scheduled"
                and timer_state.scheduled_attempt == attempt + 1
                and status == "playing"
            )
            blackout_update = None
            blackout_activates = (
                blackout_state is not None
                and blackout_state.status == "scheduled"
                and blackout_state.scheduled_attempt == attempt
                and status == "playing"
            )
            if blackout_activates:
                self.repository.activate_blackout(connection, game_id, now)
                blackout_update = ActivatedBlackout(state="activated")
            reverse_entry_update = None
            if reverse_entry_active:
                self.repository.consume_reverse_entry(
                    connection, game_id, attempt, now
                )
                reverse_entry_update = ReverseEntryUpdate(state="resolved")
            elif (
                reverse_entry_state is not None
                and reverse_entry_state.status == "armed"
                and status == "playing"
                and not timer_targets_next_attempt
                and attempt + 1 not in blackout_blocked_attempts
            ):
                trigger_reason = self._reverse_entry_trigger_reason(
                    reverse_entry_state, display_feedback, attempt
                )
                if trigger_reason is not None:
                    self.repository.activate_reverse_entry(
                        connection,
                        game_id,
                        attempt,
                        trigger_reason,
                        now,
                    )
                    reverse_entry_update = ReverseEntryUpdate(
                        state="activated"
                    )
            if timer_targets_next_attempt and timer_state is not None:
                timer_update = self._activate_guess_timer(
                    connection,
                    timer_state,
                    self.now(),
                )
            deception = self._terminal_deception(
                connection,
                game_id,
                schedules,
                status,
                attempt,
            )

        return GuessResponse(
            guess=guess,
            feedback=display_feedback,
            attempt=attempt,
            status=status,
            answer=game.answer if status in {"won", "lost"} else None,
            deception=deception,
            reverse_entry=reverse_entry_update,
            timer=timer_update,
            blackout=blackout_update,
        )
