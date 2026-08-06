from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import secrets
from typing import Callable

from .clock import PuzzleWindow, daily_window
from .config import Settings
from .deception import DeceptionEngine, VisibleGuess
from .difficulty import (
    DEFAULT_PRESET_KEY,
    BlueprintOverrides,
    GameBlueprint,
    build_blueprint,
    get_preset,
    intrusion_for_attempt,
    public_presets,
)
from .engine import MAX_GUESSES, WORD_LENGTH, TruthEngine, normalize_word
from .errors import DomainError, GuessValidationError
from .repository import (
    BlackoutState,
    CURRENT_RULES_VERSION,
    DailyDescentRun,
    DailyDescentStage,
    DeceptionSchedule,
    GuessTimerState,
    Repository,
    ReverseEntryState,
    StoredGame,
    StoredGuess,
    StoredDeceptionReason,
)
from .schemas import (
    ActivatedBlackout,
    ActivatedGuessTimer,
    ActivatedIntrusion,
    ActivatedDeceptionReveal,
    AttemptResponse,
    BootstrapResponse,
    DailyInfo,
    DeceptionChange,
    DeceptionReveal,
    DifficultyPresetSummary,
    GameConfig,
    GuessResponse,
    NotActivatedDeceptionReveal,
    CompletedGuessTimer,
    InvalidCommitmentResponse,
    PunishmentReport,
    PunishmentReportEvent,
    PunishmentUpdate,
    ReverseEntryUpdate,
    StartGameResponse,
    TimedOutResponse,
    ExpiredGuessTimer,
)


NowProvider = Callable[[], datetime]
SeedProvider = Callable[[], str]
TIMER_ACTIVATION_DELAY = timedelta(seconds=1)


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

    @staticmethod
    def _preset_summary(preset_key: str) -> DifficultyPresetSummary:
        preset = get_preset(preset_key)
        return DifficultyPresetSummary(
            preset_key=preset.key,
            name=preset.name,
            rank=preset.order,
            pressure=preset.pressure,
            description=preset.description,
            available=preset.available,
        )

    def bootstrap(self, device_id: str) -> BootstrapResponse:
        now = self.now()
        window = daily_window(now)
        with self.repository.transaction() as connection:
            self.repository.ensure_device(connection, device_id, now)
            run = self.repository.get_daily_descent_run(
                connection, device_id, window.puzzle_key
            )
            if run is not None and run.status == "active":
                self.repository.forfeit_daily_descent_run(
                    connection,
                    device_id,
                    window.puzzle_key,
                    run.current_stage,
                    now,
                )
                run = self.repository.get_daily_descent_run(
                    connection, device_id, window.puzzle_key
                )
            current_puzzles = self.repository.list_daily_descent_puzzles(
                connection, window.puzzle_key
            )
        run_status = run.status if run is not None else "unstarted"
        current_stage = run.current_stage if run is not None else 1
        cleared_stages = (
            4
            if run_status == "completed"
            else max(0, current_stage - 1)
        )
        availability = (
            "used"
            if run_status in {"active", "failed", "forfeited", "completed", "expired"}
            else "available"
        )
        pinned_preset_key = next(
            (
                puzzle.preset_key
                for puzzle in current_puzzles
                if puzzle.stage_index == current_stage
            ),
            None,
        )
        preset = (
            get_preset(pinned_preset_key)
            if pinned_preset_key is not None
            else sorted(public_presets(), key=lambda item: item.order)[
                current_stage - 1
            ]
        )
        return BootstrapResponse(
            config=self.config,
            daily=DailyInfo(
                puzzle_key=window.puzzle_key,
                availability=availability,
                reset_at=window.reset_at,
                status=run_status,
                current_stage=current_stage,
                cleared_stages=cleared_stages,
                current_preset=self._preset_summary(preset.key),
            ),
            presets=[
                self._preset_summary(preset.key)
                for preset in public_presets()
            ],
        )

    def _ensure_daily_descent_puzzles(
        self, connection, window: PuzzleWindow, now: datetime
    ):
        existing = self.repository.list_daily_descent_puzzles(
            connection, window.puzzle_key
        )
        for puzzle in existing:
            if puzzle.blueprint_json is None:
                self.repository.set_daily_descent_blueprint(
                    connection,
                    window.puzzle_key,
                    puzzle.stage_index,
                    self._new_blueprint(
                        puzzle.preset_key,
                        mode="daily",
                        puzzle_key=window.puzzle_key,
                    ).to_json(),
                )
        if len(existing) == 4:
            return self.repository.list_daily_descent_puzzles(
                connection, window.puzzle_key
            )

        selected_answers = {puzzle.answer for puzzle in existing}
        existing_stages = {puzzle.stage_index for puzzle in existing}
        presets = sorted(public_presets(), key=lambda preset: preset.order)
        for stage_index, preset in enumerate(presets, start=1):
            if stage_index in existing_stages:
                continue
            if stage_index == 1 and self.settings.fixed_answer:
                answer = self.settings.fixed_answer.lower()
            else:
                message = (
                    f"{self.settings.answer_list_version}:{window.puzzle_key}:"
                    f"daily-descent:{stage_index}"
                ).encode("utf-8")
                digest = hmac.new(
                    self.settings.daily_seed.encode("utf-8"),
                    message,
                    hashlib.sha256,
                ).digest()
                start = int.from_bytes(digest[:8], "big") % len(
                    self.engine.answers
                )
                answer = next(
                    self.engine.answers[(start + offset) % len(self.engine.answers)]
                    for offset in range(len(self.engine.answers))
                    if self.engine.answers[(start + offset) % len(self.engine.answers)]
                    not in selected_answers
                )
            selected_answers.add(answer)
            self.repository.create_daily_descent_puzzle(
                connection,
                puzzle_key=window.puzzle_key,
                stage_index=stage_index,
                preset_key=preset.key,
                answer=answer,
                answer_list_version=self.settings.answer_list_version,
                blueprint_json=self._new_blueprint(
                    preset.key,
                    mode="daily",
                    puzzle_key=window.puzzle_key,
                ).to_json(),
                created_at=now,
            )
        return self.repository.list_daily_descent_puzzles(
            connection, window.puzzle_key
        )

    @staticmethod
    def _continuation_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _require_continuation_token(token: str | None) -> str:
        if token is None or len(token) < 20:
            raise DomainError(
                400,
                "CONTINUATION_TOKEN_REQUIRED",
                "This Daily Descent stage needs an active-page token.",
            )
        return token

    def _daily_stage_access(
        self,
        connection,
        game: StoredGame,
        continuation_token: str | None,
        now: datetime,
        *,
        bind_if_ready: bool,
    ) -> tuple[DailyDescentRun, DailyDescentStage]:
        token = self._require_continuation_token(continuation_token)
        if game.puzzle_key is None:
            raise DomainError(
                503,
                "SERVICE_UNAVAILABLE",
                "The Daily Descent stage is missing its puzzle key.",
            )
        current_window = daily_window(now)
        if current_window.puzzle_key != game.puzzle_key:
            self.repository.expire_daily_descent_run(
                connection, game.device_id, game.puzzle_key, now
            )
            raise DomainError(
                409,
                "DAILY_DESCENT_EXPIRED",
                "This Daily Descent expired at the reset.",
            )
        run = self.repository.get_daily_descent_run(
            connection, game.device_id, game.puzzle_key
        )
        stage = self.repository.get_daily_descent_stage_for_game(
            connection, game.game_id
        )
        if run is None or stage is None or run.current_stage != stage.stage_index:
            raise DomainError(
                503,
                "SERVICE_UNAVAILABLE",
                "The Daily Descent stage state is unavailable.",
            )
        token_hash = self._continuation_hash(token)
        if run.status == "active":
            if (
                stage.status != "active"
                or run.continuation_hash is None
                or not hmac.compare_digest(run.continuation_hash, token_hash)
            ):
                raise DomainError(
                    409,
                    "CONTINUATION_MISMATCH",
                    "This Daily Descent stage belongs to another active page.",
                )
            return run, stage
        if (
            run.status in {"unstarted", "checkpoint"}
            and stage.status == "ready"
        ):
            if bind_if_ready:
                self.repository.activate_daily_descent_stage(
                    connection,
                    device_id=game.device_id,
                    puzzle_key=game.puzzle_key,
                    stage_index=stage.stage_index,
                    continuation_hash=token_hash,
                    activated_at=now,
                )
                active_run = self.repository.get_daily_descent_run(
                    connection, game.device_id, game.puzzle_key
                )
                active_stage = self.repository.get_daily_descent_stage_for_game(
                    connection, game.game_id
                )
                if active_run is None or active_stage is None:
                    raise DomainError(
                        503,
                        "SERVICE_UNAVAILABLE",
                        "The Daily Descent stage could not be activated.",
                    )
                return active_run, active_stage
            return run, stage
        raise DomainError(
            409,
            "DAILY_DESCENT_FINISHED",
            "This Daily Descent stage can no longer be played.",
        )

    def _finish_daily_stage(
        self,
        connection,
        game: StoredGame,
        status: str,
        now: datetime,
    ) -> None:
        if game.mode != "daily" or status not in {"won", "lost"}:
            return
        stage = self.repository.get_daily_descent_stage_for_game(
            connection, game.game_id
        )
        if stage is None:
            raise DomainError(
                503,
                "SERVICE_UNAVAILABLE",
                "The Daily Descent stage state is unavailable.",
            )
        self.repository.finish_daily_descent_stage(
            connection,
            device_id=stage.device_id,
            puzzle_key=stage.puzzle_key,
            stage_index=stage.stage_index,
            won=status == "won",
            finished_at=now,
        )

    def _practice_answer(self, previous_answer: str | None) -> str:
        if self.settings.fixed_answer:
            return self.settings.fixed_answer.lower()
        choices = [
            answer for answer in self.engine.answers if answer != previous_answer
        ]
        return secrets.choice(choices or list(self.engine.answers))

    def _blueprint_overrides(self) -> BlueprintOverrides:
        lie_attempts = self.settings.fixed_lie_rows
        if lie_attempts is None and self.settings.fixed_lie_row is not None:
            lie_attempts = (self.settings.fixed_lie_row,)
        return BlueprintOverrides(
            lie_attempts=lie_attempts,
            timer_roll=self.settings.fixed_timer_roll,
            timer_attempt=self.settings.fixed_timer_attempt,
            timer_duration=self.settings.fixed_timer_duration,
            blackout_roll=self.settings.fixed_blackout_roll,
            blackout_attempt=self.settings.fixed_blackout_attempt,
            reverse_roll=self.settings.fixed_reverse_entry_roll,
            timer_enabled=self.settings.guess_timer_enabled,
            reverse_enabled=self.settings.reverse_entry_enabled,
            blackout_enabled=self.settings.blackout_enabled,
        )

    def _daily_blueprint_seed(
        self, puzzle_key: str, preset_key: str
    ) -> str:
        return hmac.new(
            self.settings.daily_seed.encode("utf-8"),
            f"blueprint:v1:{puzzle_key}:{preset_key}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _new_blueprint(
        self,
        preset_key: str,
        *,
        mode: str,
        puzzle_key: str | None,
    ) -> GameBlueprint:
        seed = (
            self.session_seed_provider()
            if self.settings.fixed_session_seed is not None
            else (
                self._daily_blueprint_seed(puzzle_key, preset_key)
                if mode == "daily" and puzzle_key is not None
                else self.session_seed_provider()
            )
        )
        return build_blueprint(
            preset_key, seed, overrides=self._blueprint_overrides()
        )

    def _blueprint_for_game(
        self, connection, game: StoredGame
    ) -> tuple[StoredGame, GameBlueprint]:
        if game.blueprint_json:
            return game, GameBlueprint.from_json(game.blueprint_json)
        blueprint = self._new_blueprint(
            game.preset_key,
            mode=game.mode,
            puzzle_key=game.puzzle_key,
        )
        blueprint_json = blueprint.to_json()
        self.repository.set_game_blueprint(
            connection, game.game_id, game.preset_key, blueprint_json
        )
        return replace(game, blueprint_json=blueprint_json), blueprint

    def _create_schedules(
        self,
        connection,
        game: StoredGame,
        now: datetime,
    ) -> list[DeceptionSchedule]:
        existing = self._get_schedules(connection, game)
        if existing:
            return existing
        game, blueprint = self._blueprint_for_game(connection, game)
        seed = blueprint.seed
        scheduled_attempts = blueprint.lie_attempts
        return self.repository.replace_deception_schedules(
            connection,
            scheduled_attempts=scheduled_attempts,
            seed=seed,
            created_at=now,
            game_id=game.game_id,
            strategy_version=5 if blueprint.schema_version >= 6 else 4,
        )

    def _get_schedules(
        self, connection, game: StoredGame
    ) -> list[DeceptionSchedule]:
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
        game, blueprint = self._blueprint_for_game(connection, game)
        blackout_state = self._ensure_blackout_state(
            connection, game, now, blueprint
        )
        self._ensure_reverse_entry_state(connection, game, now, blueprint)
        self._ensure_guess_timer_state(
            connection,
            game,
            now,
            blueprint,
            blackout_state=blackout_state,
        )
        return game, schedules

    def _ensure_reverse_entry_state(
        self,
        connection,
        game: StoredGame,
        now: datetime,
        blueprint: GameBlueprint,
    ) -> ReverseEntryState | None:
        if (
            not blueprint.reverse_enabled
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
            blueprint.reverse_seed,
            blueprint.reverse_max_events,
            now,
        )

    def _ensure_blackout_state(
        self,
        connection,
        game: StoredGame,
        now: datetime,
        blueprint: GameBlueprint,
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

        seed = blueprint.seed
        if blueprint.blackout_attempt is None:
            return self.repository.create_blackout_state(
                connection, game.game_id, seed, None, now
            )
        return self.repository.create_blackout_state(
            connection,
            game.game_id,
            seed,
            blueprint.blackout_attempt,
            now,
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

    def _ensure_guess_timer_state(
        self,
        connection,
        game: StoredGame,
        now: datetime,
        blueprint: GameBlueprint,
        *,
        blackout_state: BlackoutState | None = None,
    ) -> GuessTimerState | None:
        if (
            not self.settings.guess_timer_enabled
            or game.rules_version < CURRENT_RULES_VERSION
        ):
            return None
        existing = self.repository.list_guess_timer_states(
            connection, game.game_id
        )
        if existing:
            return existing[0]

        created = self.repository.create_guess_timer_events(
            connection,
            game.game_id,
            blueprint.seed,
            tuple(
                (event.attempt, event.duration_seconds)
                for event in blueprint.timer_events
            ),
            now,
        )
        return created[0] if created else None

    def _activate_guess_timer(
        self,
        connection,
        timer_state: GuessTimerState,
        now: datetime,
        *,
        after_blackout: bool = False,
    ) -> ActivatedGuessTimer:
        if timer_state.duration_seconds not in {10, 30}:
            raise DomainError(
                503,
                "SERVICE_UNAVAILABLE",
                "The Guess Timer duration is unavailable.",
            )
        starts_at = now + (
            timedelta(seconds=2) if after_blackout else TIMER_ACTIVATION_DELAY
        )
        deadline_at = starts_at + timedelta(
            seconds=timer_state.duration_seconds
        )
        active = self.repository.activate_guess_timer(
            connection,
            timer_state.game_id,
            timer_state.ordinal,
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
        fallback_probability: float,
        fallback_attempt: int | None = None,
    ) -> str | None:
        if display_feedback.count("B") >= 4:
            return "lowInformation"
        if fallback_attempt is not None and attempt + 1 == fallback_attempt:
            return "chance"
        if self.settings.fixed_reverse_entry_roll is not None:
            roll = self.settings.fixed_reverse_entry_roll
        else:
            digest = hmac.new(
                state.seed.encode("utf-8"),
                f"reverse-entry:v1:{attempt}".encode("utf-8"),
                hashlib.sha256,
            ).digest()
            roll = int.from_bytes(digest[:8], "big") / 2**64
        return "chance" if roll < fallback_probability else None

    @staticmethod
    def _scheduled_punishment_updates(
        blueprint: GameBlueprint | None,
        trigger_attempt: int,
        status: str,
    ) -> list[PunishmentUpdate]:
        if blueprint is None or status != "playing":
            return []
        updates: list[PunishmentUpdate] = []
        for plan in blueprint.punishments_for_trigger(trigger_attempt):
            if plan.kind not in {
                "blindEntry", "corruptedHistory", "noRevision",
                "forcedCommitment", "memoryTax",
            }:
                continue
            updates.append(
                PunishmentUpdate(
                    kind=plan.kind,
                    state="activated",
                    effective_attempt=plan.effective_attempt,
                    row_attempt=(
                        int(plan.config["rowAttempt"])
                        if "rowAttempt" in plan.config else None
                    ),
                    retain_rows=(
                        int(plan.config["retainRows"])
                        if "retainRows" in plan.config else None
                    ),
                )
            )
        return updates

    @staticmethod
    def _terminal_punishment_report(
        blueprint: GameBlueprint | None,
        status: str,
        final_attempt: int,
    ) -> PunishmentReport | None:
        if blueprint is None or status == "playing" or not blueprint.punishment_plans:
            return None
        events: list[PunishmentReportEvent] = []
        for plan in blueprint.punishment_plans:
            if plan.trigger_attempt > final_attempt:
                outcome = "notReached"
            elif status == "won" and plan.trigger_attempt == final_attempt:
                outcome = "superseded"
            elif plan.effective_attempt > final_attempt:
                outcome = "notReached"
            else:
                outcome = "activated"
            events.append(
                PunishmentReportEvent(
                    kind=plan.kind,
                    ordinal=plan.ordinal,
                    trigger_attempt=plan.trigger_attempt,
                    effective_attempt=plan.effective_attempt,
                    outcome=outcome,
                )
            )
        return PunishmentReport(events=events)

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
            changes = [
                DeceptionChange(
                    tile_index=index,
                    letter=row.guess[index],
                    truthful_feedback=row.truth_feedback[index],
                    displayed_feedback=row.display_feedback[index],
                )
                for index, markers in enumerate(
                    zip(row.truth_feedback, row.display_feedback)
                )
                if markers[0] != markers[1]
            ]
            return ActivatedDeceptionReveal(
                outcome="activated",
                kind=(
                    "falseVictory"
                    if row.truth_feedback == "GGGGG"
                    else "feedbackLie"
                ),
                scheduled_attempt=schedule.scheduled_attempt,
                changes=changes,
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
        self,
        device_id: str,
        mode: str,
        preset_key: str | None = None,
        continuation_token: str | None = None,
    ) -> StartGameResponse:
        if mode not in {"daily", "practice"}:
            raise DomainError(
                400, "INVALID_MODE", "Choose either daily or practice mode."
            )

        selected_preset_key = preset_key or DEFAULT_PRESET_KEY
        if mode == "daily":
            self._require_continuation_token(continuation_token)
            if preset_key is not None:
                raise DomainError(
                    400,
                    "DAILY_PRESET_LOCKED",
                    "Daily Descent chooses each stage in order.",
                )
        else:
            try:
                selected_preset = get_preset(selected_preset_key)
            except ValueError as error:
                raise DomainError(
                    400,
                    "INVALID_PRESET",
                    "Choose a recognized difficulty.",
                ) from error
            if not selected_preset.available:
                raise DomainError(
                    409,
                    "PRESET_UNAVAILABLE",
                    "That difficulty is not available yet.",
                )

        now = self.now()
        game_id = secrets.token_urlsafe(24)
        puzzle_key: str | None = None
        stage_index: int | None = None

        with self.repository.transaction() as connection:
            self.repository.ensure_device(connection, device_id, now)

            if mode == "daily":
                window = daily_window(now)
                puzzle_key = window.puzzle_key
                puzzles = self._ensure_daily_descent_puzzles(
                    connection, window, now
                )
                run = self.repository.get_daily_descent_run(
                    connection, device_id, puzzle_key
                )
                if run is None:
                    run = self.repository.create_daily_descent_run(
                        connection, device_id, puzzle_key, now
                    )
                if run.status in {
                    "failed",
                    "forfeited",
                    "completed",
                    "expired",
                }:
                    raise DomainError(
                        409,
                        "DAILY_DESCENT_FINISHED",
                        "Today’s Daily Descent has already ended.",
                    )
                if run.status == "active":
                    raise DomainError(
                        409,
                        "DAILY_STAGE_ACTIVE",
                        "This Daily Descent stage is already in progress.",
                    )

                stage_index = run.current_stage
                puzzle = puzzles[stage_index - 1]
                selected_preset_key = puzzle.preset_key
                existing_stage = self.repository.get_daily_descent_stage(
                    connection, device_id, puzzle_key, stage_index
                )
                if existing_stage is not None:
                    pending_game = self.repository.get_game(
                        connection, existing_stage.game_id
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
                    return self._start_response(
                        pending_game, daily_stage=stage_index
                    )
                game = self.repository.create_game(
                    connection,
                    game_id,
                    device_id,
                    "daily",
                    puzzle.answer,
                    now,
                    puzzle_key,
                    preset_key=selected_preset_key,
                    blueprint_json=puzzle.blueprint_json,
                )
                self.repository.create_daily_descent_stage(
                    connection,
                    device_id=device_id,
                    puzzle_key=puzzle_key,
                    stage_index=stage_index,
                    game_id=game_id,
                    created_at=now,
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
                    preset_key=selected_preset_key,
                    blueprint_json=self._new_blueprint(
                        selected_preset_key,
                        mode="practice",
                        puzzle_key=None,
                    ).to_json(),
                )
            game, _ = self._ensure_current_rules(connection, game, now)

        return self._start_response(
            game,
            daily_stage=stage_index,
        )

    def _start_response(
        self, game: StoredGame, daily_stage: int | None = None
    ) -> StartGameResponse:
        return StartGameResponse(
            game_id=game.game_id,
            mode=game.mode,
            config=self.config,
            preset=self._preset_summary(game.preset_key),
            puzzle_key=game.puzzle_key,
            daily_stage=daily_stage,
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

    def _resolve_reverse_entry_for_consumed_attempt(
        self,
        connection,
        game: StoredGame,
        blueprint: GameBlueprint | None,
        attempt: int,
        status: str,
        now: datetime,
    ) -> tuple[ReverseEntryState | None, ReverseEntryUpdate | None]:
        """Consume the Reverse event used by an accepted or expired attempt.

        A separately planned Reverse event may begin on the next attempt. That
        is reported as ``continued`` even though the event that affected this
        attempt was consumed first; an ordinary rearm never leaks the same
        event into another row.
        """
        state = self.repository.get_reverse_entry_state(
            connection, game.game_id
        )
        if state is None or state.status != "active":
            return state, None

        can_rearm = state.event_count < state.max_events and status == "playing"
        self.repository.consume_reverse_entry(
            connection,
            game.game_id,
            attempt,
            now,
            rearm=can_rearm,
        )
        update = ReverseEntryUpdate(state="resolved")
        state = self.repository.get_reverse_entry_state(
            connection, game.game_id
        )

        if can_rearm and state is not None and state.status == "armed":
            next_scheduled_attempt = (
                next(
                    (
                        plan.effective_attempt
                        for plan in blueprint.punishment_plans
                        if plan.kind == "reverseEntry"
                        and plan.ordinal == state.event_count + 1
                    ),
                    None,
                )
                if blueprint is not None
                else None
            )
            if next_scheduled_attempt == attempt + 1:
                self.repository.activate_reverse_entry(
                    connection,
                    game.game_id,
                    attempt,
                    "chance",
                    now,
                )
                state = self.repository.get_reverse_entry_state(
                    connection, game.game_id
                )
                update = ReverseEntryUpdate(state="continued")

        return state, update

    def _replayed_timeout_reverse_entry_update(
        self,
        connection,
        game_id: str,
        attempt: int,
    ) -> ReverseEntryUpdate | None:
        state = self.repository.get_reverse_entry_state(connection, game_id)
        if state is None or state.consumed_attempt != attempt:
            return None
        if state.status == "active" and state.trigger_attempt == attempt:
            return ReverseEntryUpdate(state="continued")
        return ReverseEntryUpdate(state="resolved")

    def _consume_timer_timeout(
        self,
        connection,
        game: StoredGame,
        schedules: list[DeceptionSchedule],
        timer_state: GuessTimerState,
        now: datetime,
    ) -> TimedOutResponse:
        attempt = game.guess_count + 1
        blueprint = (
            GameBlueprint.from_json(game.blueprint_json)
            if game.blueprint_json else None
        )
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
        self._finish_daily_stage(connection, game, status, now)
        self.repository.resolve_guess_timer(
            connection,
            game.game_id,
            timer_state.ordinal,
            "expired",
            attempt,
            now,
        )
        _, reverse_entry_update = (
            self._resolve_reverse_entry_for_consumed_attempt(
                connection,
                game,
                blueprint,
                attempt,
                status,
                now,
            )
        )
        next_timer = None
        if status == "playing":
            scheduled_next = self.repository.get_guess_timer_for_attempt(
                connection, game.game_id, attempt + 1
            )
            if scheduled_next is not None and scheduled_next.status == "scheduled":
                next_timer = self._activate_guess_timer(
                    connection, scheduled_next, self.now()
                )
        deception = self._terminal_deception(
            connection,
            game.game_id,
            schedules,
            status,
            attempt,
        )
        punishment_updates = self._scheduled_punishment_updates(
            blueprint, attempt, status
        )
        if reverse_entry_update is not None:
            punishment_updates.append(
                PunishmentUpdate(
                    kind="reverseEntry",
                    state=reverse_entry_update.state,
                    effective_attempt=min(attempt + 1, MAX_GUESSES),
                )
            )
        return TimedOutResponse(
            attempt=attempt,
            status=status,
            answer=game.answer if status == "lost" else None,
            deception=deception,
            reverse_entry=reverse_entry_update,
            timer=ExpiredGuessTimer(state="expired"),
            next_timer=next_timer,
            punishments=punishment_updates or None,
            punishment_report=self._terminal_punishment_report(
                blueprint, status, attempt
            ),
        )

    def expire_timer(
        self,
        device_id: str,
        game_id: str,
        continuation_token: str | None = None,
    ) -> TimedOutResponse:
        now = self.now()
        with self.repository.transaction() as connection:
            game = self.repository.get_game(connection, game_id)
            if game is None or game.device_id != device_id:
                raise DomainError(
                    404, "GAME_NOT_FOUND", "That game could not be found."
                )
            if game.mode == "daily":
                self._daily_stage_access(
                    connection,
                    game,
                    continuation_token,
                    now,
                    bind_if_ready=False,
                )
            game, schedules = self._ensure_current_rules(
                connection, game, now
            )
            timer_state = self.repository.get_guess_timer_for_attempt(
                connection, game_id, game.guess_count + 1
            )
            resolved_timer = (
                self.repository.get_guess_timer_for_attempt(
                    connection, game_id, game.guess_count
                )
                if game.guess_count > 0
                else None
            )
            # Preserve idempotence when no later timed turn is active. When
            # timers are consecutive, the newly active timer must win this
            # lookup so a duplicate expiry request cannot consume it early.
            if (
                timer_state is None
                and resolved_timer is not None
                and resolved_timer.status == "expired"
            ):
                timer_state = resolved_timer
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
                reverse_entry_update = (
                    self._replayed_timeout_reverse_entry_update(
                        connection,
                        game.game_id,
                        timer_state.resolved_attempt,
                    )
                )
                punishment_updates = []
                if reverse_entry_update is not None:
                    punishment_updates.append(
                        PunishmentUpdate(
                            kind="reverseEntry",
                            state=reverse_entry_update.state,
                            effective_attempt=min(
                                timer_state.resolved_attempt + 1,
                                MAX_GUESSES,
                            ),
                        )
                    )
                return TimedOutResponse(
                    attempt=timer_state.resolved_attempt,
                    status=game.status,
                    answer=game.answer if game.status == "lost" else None,
                    deception=deception,
                    reverse_entry=reverse_entry_update,
                    timer=ExpiredGuessTimer(state="expired"),
                    next_timer=None,
                    punishments=punishment_updates or None,
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
        self,
        device_id: str,
        game_id: str,
        raw_guess: str,
        continuation_token: str | None = None,
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

            if game.mode == "daily":
                self._daily_stage_access(
                    connection,
                    game,
                    continuation_token,
                    now,
                    bind_if_ready=False,
                )

            game, schedules = self._ensure_current_rules(
                connection, game, now
            )
            blueprint = (
                GameBlueprint.from_json(game.blueprint_json)
                if game.blueprint_json
                else None
            )
            timer_states = self.repository.list_guess_timer_states(
                connection, game_id
            )
            blackout_state = self.repository.get_blackout_state(
                connection, game_id
            )
            blackout_blocked_attempts = (
                set(blueprint.blackout_blocked_attempts)
                if blueprint is not None
                else self._blackout_blocked_attempts(blackout_state)
            )
            attempt = game.guess_count + 1
            timer_state = next(
                (
                    state
                    for state in timer_states
                    if state.scheduled_attempt == attempt
                ),
                None,
            )
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
                and (
                    get_preset(game.preset_key).combination_policy != "none"
                    or not timer_active
                )
            )
            submitted_guess = normalize_word(raw_guess)
            if reverse_entry_active:
                submitted_guess = submitted_guess[::-1]
            effective_punishments = (
                blueprint.punishments_for_effective(attempt)
                if blueprint is not None else ()
            )
            forced_commitment_active = any(
                plan.kind == "forcedCommitment"
                and plan.effective_attempt == attempt
                for plan in effective_punishments
            )
            try:
                guess = self.engine.validate_guess(submitted_guess)
            except GuessValidationError as error:
                if (
                    forced_commitment_active
                    and error.code == "INVALID_WORD"
                    and len(submitted_guess) == WORD_LENGTH
                ):
                    if game.mode == "daily":
                        self._daily_stage_access(
                            connection, game, continuation_token, now,
                            bind_if_ready=True,
                        )
                    status = "lost" if attempt >= MAX_GUESSES else "playing"
                    self.repository.record_timeout(
                        connection, game_id, attempt, status, now
                    )
                    self._finish_daily_stage(connection, game, status, now)
                    if timer_active and timer_state is not None:
                        self.repository.resolve_guess_timer(
                            connection, game_id, timer_state.ordinal,
                            "completed", attempt, now,
                        )
                    reverse_entry_update = None
                    if reverse_entry_active:
                        _, reverse_entry_update = (
                            self._resolve_reverse_entry_for_consumed_attempt(
                                connection,
                                game,
                                blueprint,
                                attempt,
                                status,
                                now,
                            )
                        )
                    next_timer = None
                    if status == "playing":
                        scheduled_next = next(
                            (
                                state
                                for state in timer_states
                                if state.status == "scheduled"
                                and state.scheduled_attempt == attempt + 1
                            ),
                            None,
                        )
                        if scheduled_next is not None:
                            next_timer = self._activate_guess_timer(
                                connection, scheduled_next, self.now()
                            )
                    deception = self._terminal_deception(
                        connection, game_id, schedules, status, attempt
                    )
                    punishment_updates = self._scheduled_punishment_updates(
                        blueprint, attempt, status
                    )
                    if reverse_entry_update is not None:
                        punishment_updates.append(
                            PunishmentUpdate(
                                kind="reverseEntry",
                                state=reverse_entry_update.state,
                                effective_attempt=min(
                                    attempt + 1, MAX_GUESSES
                                ),
                            )
                        )
                    return InvalidCommitmentResponse(
                        attempted_guess=submitted_guess,
                        attempt=attempt,
                        status=status,
                        answer=game.answer if status == "lost" else None,
                        deception=deception,
                        reverse_entry=reverse_entry_update,
                        next_timer=next_timer,
                        punishments=punishment_updates or None,
                        punishment_report=self._terminal_punishment_report(
                            blueprint, status, attempt
                        ),
                    )
                if reverse_entry_active and error.code == "INVALID_WORD":
                    raise DomainError(
                        400,
                        "INVALID_REVERSED_WORD",
                        "That guess isn’t accepted.",
                    ) from error
                raise DomainError(400, error.code, error.message) from error

            if game.mode == "daily":
                self._daily_stage_access(
                    connection,
                    game,
                    continuation_token,
                    now,
                    bind_if_ready=True,
                )

            truth_feedback = self.engine.evaluate(guess, game.answer)
            display_feedback = truth_feedback
            deception_reason: StoredDeceptionReason = "not_scheduled"
            deception_diagnostics_json: str | None = None
            prior_guesses = self.repository.list_guesses(
                connection, game_id
            )
            is_correct = guess == game.answer
            schedule = next(
                (
                    item
                    for item in schedules
                    if item.scheduled_attempt == attempt
                ),
                None,
            )
            false_victory_eligible = (
                is_correct
                and blueprint is not None
                and blueprint.false_victory_enabled
                and attempt in range(2, 5)
                and schedule is not None
                and not any(
                    row.truth_feedback == "GGGGG" for row in prior_guesses
                )
            )
            if is_correct:
                status = "won"
            elif attempt >= MAX_GUESSES:
                status = "lost"
            else:
                status = "playing"

            if (
                schedule is not None
                and attempt < MAX_GUESSES
                and (not is_correct or false_victory_eligible)
            ):
                excluded_tile_indexes = {
                    index
                    for row in prior_guesses
                    for index, markers in enumerate(
                        zip(row.truth_feedback, row.display_feedback)
                    )
                    if markers[0] != markers[1]
                }
                if get_preset(game.preset_key).max_false_tiles > 1:
                    excluded_tile_indexes = set()
                decision_seed = schedule.seed
                if schedule.strategy_version >= 2:
                    decision_seed = hmac.new(
                        schedule.seed.encode("utf-8"),
                        f"decision:v2:{schedule.ordinal}".encode("utf-8"),
                        hashlib.sha256,
                    ).hexdigest()
                preset = get_preset(game.preset_key)
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
                    max_false_tiles=(
                        blueprint.false_tiles_for_attempt(attempt)
                        if blueprint is not None
                        else 1
                    ),
                    credible_lie_row_cap=(
                        preset.lie_policy.credible_lie_row_cap
                    ),
                    repeat_thread_probability=(
                        preset.lie_policy.repeat_thread_probability
                    ),
                    belief_aware=schedule.strategy_version >= 5,
                    time_budget_ms=self.settings.deception_decision_budget_ms,
                )
                display_feedback = decision.feedback
                deception_reason = decision.reason
                deception_diagnostics_json = json.dumps(
                    decision.diagnostics(),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if is_correct and decision.activated:
                    status = "playing"
            elif schedule is not None and attempt >= MAX_GUESSES:
                deception_reason = "final_guess"
            elif schedule is not None and is_correct:
                deception_reason = "winning_guess"

            self.repository.record_guess(
                connection,
                game_id,
                attempt,
                guess,
                truth_feedback,
                display_feedback,
                deception_reason,
                deception_diagnostics_json,
                status,
                now,
            )
            self._finish_daily_stage(connection, game, status, now)
            timer_update = None
            if timer_active:
                self.repository.resolve_guess_timer(
                    connection,
                    game_id,
                    timer_state.ordinal,
                    "completed",
                    attempt,
                    now,
                )
                timer_update = CompletedGuessTimer(state="completed")

            next_timer_state = next(
                (
                    state
                    for state in timer_states
                    if state.status == "scheduled"
                    and state.scheduled_attempt == attempt + 1
                ),
                None,
            )
            timer_targets_next_attempt = (
                next_timer_state is not None and status == "playing"
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
            intrusion_placement = (
                intrusion_for_attempt(blueprint, attempt)
                if blueprint is not None and status == "playing"
                else None
            )
            intrusion_update = (
                ActivatedIntrusion(
                    state="activated", placement=intrusion_placement
                )
                if intrusion_placement is not None
                else None
            )
            reverse_entry_update = None
            if reverse_entry_active:
                reverse_entry_state, reverse_entry_update = (
                    self._resolve_reverse_entry_for_consumed_attempt(
                        connection,
                        game,
                        blueprint,
                        attempt,
                        status,
                        now,
                    )
                )
            combination_policy = get_preset(game.preset_key).combination_policy
            reverse_can_overlap = combination_policy != "none"
            if (
                reverse_entry_state is not None
                and reverse_entry_state.status == "armed"
                # The consumed event cannot re-arm itself from the same guess.
                # A separately scheduled adjacent event is activated above.
                and not reverse_entry_active
                and status == "playing"
                and (reverse_can_overlap or not timer_targets_next_attempt)
                and (
                    reverse_can_overlap
                    or attempt + 1 not in blackout_blocked_attempts
                )
            ):
                trigger_reason = self._reverse_entry_trigger_reason(
                    reverse_entry_state,
                    display_feedback,
                    attempt,
                    (
                        blueprint.reverse_fallback_probability
                        if blueprint is not None
                        else 0.10
                    ),
                    (
                        next(
                            (
                                plan.effective_attempt
                                for plan in blueprint.punishment_plans
                                if plan.kind == "reverseEntry"
                                and plan.ordinal
                                == reverse_entry_state.event_count + 1
                            ),
                            None,
                        )
                        if blueprint is not None else None
                    ),
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
                        state=(
                            "continued"
                            if reverse_entry_update is not None
                            else "activated"
                        )
                    )
            if timer_targets_next_attempt and next_timer_state is not None:
                timer_update = self._activate_guess_timer(
                    connection,
                    next_timer_state,
                    self.now(),
                    after_blackout=blackout_activates,
                )
            deception = self._terminal_deception(
                connection,
                game_id,
                schedules,
                status,
                attempt,
            )

        punishment_updates = self._scheduled_punishment_updates(
            blueprint, attempt, status
        )
        if reverse_entry_update is not None:
            punishment_updates.append(
                PunishmentUpdate(
                    kind="reverseEntry",
                    state=reverse_entry_update.state,
                    effective_attempt=min(attempt + 1, 6),
                )
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
            intrusion=intrusion_update,
            punishments=punishment_updates or None,
            punishment_report=self._terminal_punishment_report(
                blueprint, status, attempt
            ),
        )
