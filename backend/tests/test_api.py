from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import json
import sqlite3

from fastapi.testclient import TestClient

from backend.app.config import DEFAULT_DATA_DIR, Settings
from backend.app.deception import DeceptionDecision
from backend.app.difficulty import BlueprintOverrides
from backend.app.main import create_app

DAILY_TOKEN = "daily-test-continuation-token-12345"


def start_game(client: TestClient, mode: str = "practice") -> dict:
    payload = {"mode": mode}
    if mode == "daily":
        payload["continuationToken"] = DAILY_TOKEN
    response = client.post("/api/games", json=payload)
    assert response.status_code == 200
    return response.json()


def daily_guess(client: TestClient, game_id: str, guess: str):
    return client.post(
        f"/api/games/{game_id}/guesses",
        json={"guess": guess, "continuationToken": DAILY_TOKEN},
    )


def test_doubt_three_executes_repeated_overlapping_events(
    settings: Settings, clock, monkeypatch
) -> None:
    advanced = replace(
        settings,
        db_path=settings.db_path.with_name("doubt-three.sqlite"),
        fixed_lie_row=None,
        fixed_lie_rows=None,
        reverse_entry_enabled=True,
        fixed_reverse_entry_roll=0.0,
        guess_timer_enabled=True,
        blackout_enabled=True,
    )
    app = create_app(settings=advanced, now_provider=clock)
    monkeypatch.setattr(
        app.state.service,
        "_blueprint_overrides",
        lambda: BlueprintOverrides(
            lie_attempts=(1, 2, 3),
            lie_tile_counts=(2, 1, 1),
            timer_attempts=(2, 4),
            timer_durations=(10, 30),
            blackout_roll=0.0,
            blackout_attempt=3,
            timer_enabled=True,
            reverse_enabled=True,
            blackout_enabled=True,
        ),
    )

    with TestClient(app) as client:
        started = client.post(
            "/api/games",
            json={"mode": "practice", "presetKey": "doubt-3@1"},
        ).json()
        game_id = started["gameId"]
        first = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "slate"}
        ).json()
        second = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "ykcip"}
        ).json()
        third = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "duolc"}
        ).json()
        final = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "crane"}
        ).json()

    assert first["timer"]["durationSeconds"] == 10
    assert first["reverseEntry"] == {"state": "activated"}
    assert second["timer"] == {"state": "completed"}
    assert second["reverseEntry"] == {"state": "continued"}
    assert third["blackout"] == {"state": "activated"}
    assert third["timer"]["durationSeconds"] == 30
    assert third["reverseEntry"] == {"state": "resolved"}
    assert final["status"] == "won"
    assert final["timer"] == {"state": "completed"}
    assert len(final["deception"]["events"]) == 3
    assert len(final["deception"]["events"][0]["changes"]) == 2

    with sqlite3.connect(advanced.db_path) as connection:
        timers = connection.execute(
            """
            SELECT status FROM guess_timer_events
            WHERE game_id = ? ORDER BY ordinal
            """,
            (game_id,),
        ).fetchall()
        reverse = connection.execute(
            """
            SELECT status, event_count, max_events
            FROM reverse_entry_states_v2 WHERE game_id = ?
            """,
            (game_id,),
        ).fetchone()

    assert timers == [("completed",), ("completed",)]
    assert reverse == ("consumed", 2, 2)


def test_doubt_three_timer_expiry_can_activate_a_consecutive_timer(
    settings: Settings, clock, monkeypatch
) -> None:
    advanced = replace(
        settings,
        db_path=settings.db_path.with_name("consecutive-timers.sqlite"),
        fixed_lie_row=None,
        fixed_lie_rows=None,
        guess_timer_enabled=True,
    )
    app = create_app(settings=advanced, now_provider=clock)
    monkeypatch.setattr(
        app.state.service,
        "_blueprint_overrides",
        lambda: BlueprintOverrides(
            lie_attempts=(5,),
            timer_attempts=(2, 3),
            timer_durations=(10, 30),
            timer_enabled=True,
            reverse_enabled=False,
            blackout_enabled=False,
        ),
    )

    with TestClient(app) as client:
        started = client.post(
            "/api/games",
            json={"mode": "practice", "presetKey": "doubt-3@1"},
        ).json()
        game_id = started["gameId"]
        first = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "slate"}
        ).json()
        clock.current += timedelta(seconds=12)
        expired = client.post(
            f"/api/games/{game_id}/timer/expire"
        )
        duplicate = client.post(
            f"/api/games/{game_id}/timer/expire"
        )

    assert first["timer"]["durationSeconds"] == 10
    assert expired.status_code == 200
    assert expired.json()["attempt"] == 2
    assert expired.json()["nextTimer"]["durationSeconds"] == 30
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "TIMER_STILL_RUNNING"


def test_deception_can_reject_one_early_correct_answer_then_guarantees_recovery(
    settings: Settings, clock, monkeypatch
) -> None:
    advanced = replace(
        settings,
        db_path=settings.db_path.with_name("false-victory.sqlite"),
        fixed_lie_row=None,
        fixed_lie_rows=None,
        reverse_entry_enabled=False,
        guess_timer_enabled=False,
        blackout_enabled=False,
    )
    app = create_app(settings=advanced, now_provider=clock)
    monkeypatch.setattr(
        app.state.service,
        "_blueprint_overrides",
        lambda: BlueprintOverrides(
            lie_attempts=(2,),
            lie_tile_counts=(2,),
            false_victory_enabled=True,
            timer_enabled=False,
            reverse_enabled=False,
            blackout_enabled=False,
        ),
    )

    with TestClient(app) as client:
        started = client.post(
            "/api/games",
            json={"mode": "practice", "presetKey": "deception@1"},
        ).json()
        game_id = started["gameId"]
        client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "fight"}
        )
        rejected = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "crane"}
        ).json()
        recovered = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "crane"}
        ).json()

    assert rejected["status"] == "playing"
    assert rejected["feedback"] != "GGGGG"
    assert "answer" not in rejected
    assert recovered["status"] == "won"
    assert recovered["answer"] == "crane"
    assert recovered["deception"]["events"][0]["kind"] == "falseVictory"
    assert recovered["deception"]["events"][0]["scheduledAttempt"] == 2


def test_deception_never_rejects_a_correct_fifth_guess(
    settings: Settings, clock, monkeypatch
) -> None:
    advanced = replace(
        settings,
        db_path=settings.db_path.with_name("protected-fifth-guess.sqlite"),
        fixed_lie_row=None,
        fixed_lie_rows=None,
        reverse_entry_enabled=False,
        guess_timer_enabled=False,
        blackout_enabled=False,
    )
    app = create_app(settings=advanced, now_provider=clock)
    monkeypatch.setattr(
        app.state.service,
        "_blueprint_overrides",
        lambda: BlueprintOverrides(
            lie_attempts=(5,),
            lie_tile_counts=(2,),
            false_victory_enabled=True,
            timer_enabled=False,
            reverse_enabled=False,
            blackout_enabled=False,
        ),
    )

    with TestClient(app) as client:
        started = client.post(
            "/api/games",
            json={"mode": "practice", "presetKey": "deception@1"},
        ).json()
        game_id = started["gameId"]
        for guess in ("slate", "fight", "mould", "berry"):
            response = client.post(
                f"/api/games/{game_id}/guesses", json={"guess": guess}
            )
            assert response.json()["status"] == "playing"
        final = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "crane"}
        ).json()

    assert final["attempt"] == 5
    assert final["status"] == "won"
    assert final["feedback"] == "GGGGG"
    assert final["deception"]["events"][0]["reason"] == "winningGuess"


def test_deception_can_overlap_blackout_reverse_and_ten_second_timer(
    settings: Settings, clock, monkeypatch
) -> None:
    advanced = replace(
        settings,
        db_path=settings.db_path.with_name("broad-overlap.sqlite"),
        fixed_lie_row=None,
        fixed_lie_rows=None,
        reverse_entry_enabled=True,
        fixed_reverse_entry_roll=0.0,
        guess_timer_enabled=True,
        blackout_enabled=True,
    )
    app = create_app(settings=advanced, now_provider=clock)
    monkeypatch.setattr(
        app.state.service,
        "_blueprint_overrides",
        lambda: BlueprintOverrides(
            lie_attempts=(1, 2, 3),
            lie_tile_counts=(1, 1, 1),
            false_victory_enabled=False,
            timer_attempts=(4,),
            timer_durations=(10,),
            blackout_roll=0.0,
            blackout_attempt=3,
            timer_enabled=True,
            reverse_enabled=True,
            blackout_enabled=True,
        ),
    )

    with TestClient(app) as client:
        started = client.post(
            "/api/games",
            json={"mode": "practice", "presetKey": "deception@1"},
        ).json()
        game_id = started["gameId"]
        client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "slate"}
        )
        client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "thgif"}
        )
        overlap = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "ykcip"}
        ).json()

    assert overlap["attempt"] == 3
    assert overlap["blackout"] == {"state": "activated"}
    assert overlap["reverseEntry"] == {"state": "continued"}
    assert overlap["timer"]["durationSeconds"] == 10
    assert (
        datetime.fromisoformat(overlap["timer"]["startsAt"])
        - clock.current
    ) == timedelta(seconds=2)


def test_intrusion_can_repeat_on_consecutive_eligible_guesses(
    settings: Settings, clock, monkeypatch
) -> None:
    intrusion_settings = replace(
        settings,
        db_path=settings.db_path.with_name("intrusion.sqlite"),
        fixed_lie_row=None,
        fixed_lie_rows=None,
        reverse_entry_enabled=False,
        guess_timer_enabled=False,
        blackout_enabled=False,
    )
    app = create_app(settings=intrusion_settings, now_provider=clock)
    monkeypatch.setattr(
        app.state.service,
        "_blueprint_overrides",
        lambda: BlueprintOverrides(
            lie_attempts=(6,),
            intrusion_probability=1.0,
            timer_enabled=False,
            reverse_enabled=False,
            blackout_enabled=False,
        ),
    )

    with TestClient(app) as client:
        started = client.post(
            "/api/games",
            json={"mode": "practice", "presetKey": "doubt-2@1"},
        ).json()
        game_id = started["gameId"]
        first = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "slate"}
        ).json()
        second = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "fight"}
        ).json()
        third = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "mould"}
        ).json()
        winner = client.post(
            f"/api/games/{game_id}/guesses", json={"guess": "crane"}
        ).json()

    assert "intrusion" not in first
    assert second["intrusion"]["state"] == "activated"
    assert third["intrusion"]["state"] == "activated"
    assert second["intrusion"]["placement"] in {
        "upperLeft",
        "upperRight",
        "lowerLeft",
        "lowerRight",
    }
    assert winner["status"] == "won"
    assert "intrusion" not in winner


def reverse_entry_settings(
    tmp_path: Path,
    *,
    fixed_roll: float,
) -> Settings:
    return Settings(
        db_path=tmp_path / f"reverse-entry-{fixed_roll}.sqlite",
        daily_seed="reverse-entry-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_row=6,
        fixed_session_seed="reverse-entry-session",
        reverse_entry_enabled=True,
        fixed_reverse_entry_roll=fixed_roll,
    )


def guess_timer_settings(
    tmp_path: Path,
    *,
    fixed_roll: float = 0.0,
    duration: int = 10,
    attempt: int = 2,
    reverse_entry_enabled: bool = False,
) -> Settings:
    return Settings(
        db_path=tmp_path / (
            f"guess-timer-{fixed_roll}-{duration}-{attempt}-"
            f"{reverse_entry_enabled}.sqlite"
        ),
        daily_seed="guess-timer-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_row=6,
        fixed_session_seed="guess-timer-session",
        reverse_entry_enabled=reverse_entry_enabled,
        fixed_reverse_entry_roll=0.0,
        guess_timer_enabled=True,
        fixed_timer_roll=fixed_roll,
        fixed_timer_duration=duration,
        fixed_timer_attempt=attempt,
    )


def blackout_settings(
    tmp_path: Path,
    *,
    attempt: int = 3,
    reverse_entry_enabled: bool = False,
    guess_timer_enabled: bool = False,
    timer_attempt: int = 2,
) -> Settings:
    return Settings(
        db_path=tmp_path
        / (
            f"blackout-{attempt}-{reverse_entry_enabled}-"
            f"{guess_timer_enabled}-{timer_attempt}.sqlite"
        ),
        daily_seed="blackout-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_row=6,
        fixed_session_seed="blackout-session",
        reverse_entry_enabled=reverse_entry_enabled,
        fixed_reverse_entry_roll=1.0,
        guess_timer_enabled=guess_timer_enabled,
        fixed_timer_roll=0.0,
        fixed_timer_duration=30,
        fixed_timer_attempt=timer_attempt,
        blackout_enabled=True,
        fixed_blackout_roll=0.0,
        fixed_blackout_attempt=attempt,
    )


def test_health_reports_database_readiness(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_database_failure_uses_service_unavailable_contract(
    client: TestClient, monkeypatch
) -> None:
    def unavailable() -> None:
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(
        client.app.state.service.repository, "health", unavailable
    )
    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Game storage is temporarily unavailable.",
        }
    }


def test_bootstrap_sets_device_cookie_and_returns_contract(
    client: TestClient,
) -> None:
    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    assert response.json() == {
        "config": {"wordLength": 5, "maxGuesses": 6},
            "daily": {
                "puzzleKey": "2026-07-28",
                "availability": "available",
                "resetAt": "2026-07-29T03:00:00Z",
                "status": "unstarted",
                "currentStage": 1,
                "clearedStages": 0,
                "currentPreset": {
                    "presetKey": "doubt-1@1",
                    "name": "Doubt I",
                    "rank": 1,
                    "pressure": "Low",
                    "description": (
                        "An approachable introduction to uncertain feedback."
                    ),
                    "available": True,
                },
            },
        "presets": [
            {
                "presetKey": "doubt-1@1",
                "name": "Doubt I",
                "rank": 1,
                "pressure": "Low",
                "description": (
                    "An approachable introduction to uncertain feedback."
                ),
                "available": True,
            },
            {
                "presetKey": "doubt-2@1",
                "name": "Doubt II",
                "rank": 2,
                "pressure": "Standard",
                "description": "The complete standard Deception experience.",
                "available": True,
            },
            {
                "presetKey": "doubt-3@1",
                "name": "Doubt III",
                "rank": 3,
                "pressure": "High",
                "description": (
                    "Aggressive pressure with repeated punishments."
                ),
                    "available": True,
            },
            {
                "presetKey": "deception@1",
                "name": "Deception",
                "rank": 4,
                "pressure": "Extreme",
                "description": "An expert survival challenge.",
                "available": True,
            },
        ],
    }
    cookie = response.cookies.get("deception_device")
    assert cookie
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]


def test_practice_preset_is_selected_and_persisted(
    client: TestClient, settings: Settings
) -> None:
    response = client.post(
        "/api/games",
        json={"mode": "practice", "presetKey": "doubt-1@1"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["preset"]["presetKey"] == "doubt-1@1"
    with sqlite3.connect(settings.db_path) as connection:
        preset_key, blueprint_json = connection.execute(
            "SELECT preset_key, blueprint_json FROM games WHERE id = ?",
            (payload["gameId"],),
        ).fetchone()
    assert preset_key == "doubt-1@1"
    assert json.loads(blueprint_json)["preset_key"] == "doubt-1@1"


def test_daily_begins_at_doubt_one_and_rejects_manual_preset_selection(
    client: TestClient,
) -> None:
    daily = start_game(client, "daily")
    locked = client.post(
        "/api/games",
        json={
            "mode": "daily",
            "presetKey": "doubt-1@1",
            "continuationToken": DAILY_TOKEN,
        },
    )
    invalid = client.post(
        "/api/games",
        json={"mode": "practice", "presetKey": "unknown@1"},
    )
    assert daily["preset"]["presetKey"] == "doubt-1@1"
    assert daily["dailyStage"] == 1
    assert locked.status_code == 400
    assert locked.json()["error"]["code"] == "DAILY_PRESET_LOCKED"
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_PRESET"


def test_deception_is_selectable_in_practice(client: TestClient) -> None:
    response = client.post(
        "/api/games",
        json={"mode": "practice", "presetKey": "deception@1"},
    )

    assert response.status_code == 200
    assert response.json()["preset"]["presetKey"] == "deception@1"


def test_start_and_active_guess_do_not_reveal_answer(
    client: TestClient,
) -> None:
    game = start_game(client)
    assert "answer" not in game

    response = client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": "slate"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "guess": "slate",
        "feedback": "BBGBG",
        "attempt": 1,
        "status": "playing",
    }


def test_correct_guess_wins_and_reveals_answer(client: TestClient) -> None:
    game = start_game(client)

    response = client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": "crane"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "guess": "crane",
        "feedback": "GGGGG",
        "attempt": 1,
        "status": "won",
        "answer": "crane",
        "deception": {
            "events": [
                {
                    "outcome": "notActivated",
                    "scheduledAttempt": 6,
                    "reason": "notReached",
                }
            ],
        },
    }


def test_six_wrong_guesses_lose_and_reveal_answer(
    client: TestClient,
) -> None:
    game = start_game(client)
    guesses = ["slate", "fight", "mould", "berry", "shack", "dingo"]

    for guess in guesses[:-1]:
        response = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": guess},
        )
        assert response.json()["status"] == "playing"
        assert "answer" not in response.json()

    final = client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": guesses[-1]},
    )
    assert final.json()["status"] == "lost"
    assert final.json()["answer"] == "crane"
    assert final.json()["deception"] == {
        "events": [
            {
                "outcome": "notActivated",
                "scheduledAttempt": 6,
                "reason": "finalAttempt",
            }
        ],
    }


def test_daily_pending_game_is_reused_without_consuming(
    client: TestClient,
) -> None:
    first = start_game(client, "daily")
    second = start_game(client, "daily")

    assert second["gameId"] == first["gameId"]
    assert client.get("/api/bootstrap").json()["daily"]["availability"] == (
        "available"
    )


def test_invalid_first_guess_does_not_consume_daily(
    client: TestClient,
) -> None:
    game = start_game(client, "daily")

    short = daily_guess(client, game["gameId"], "cat")
    unknown = daily_guess(client, game["gameId"], "zzzzz")

    assert short.status_code == 400
    assert short.json()["error"]["code"] == "INVALID_LENGTH"
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "INVALID_WORD"
    assert client.get("/api/bootstrap").json()["daily"]["availability"] == (
        "available"
    )


def test_first_valid_daily_guess_consumes_attempt_and_blocks_restart(
    client: TestClient,
) -> None:
    game = start_game(client, "daily")

    guess = daily_guess(client, game["gameId"], "slate")

    assert guess.status_code == 200
    assert client.get("/api/bootstrap").json()["daily"]["availability"] == "used"
    blocked = client.post(
        "/api/games",
        json={"mode": "daily", "continuationToken": DAILY_TOKEN},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "DAILY_DESCENT_FINISHED"


def test_daily_attempt_is_isolated_by_anonymous_device(app) -> None:
    with TestClient(app) as first, TestClient(app) as second:
        first_game = start_game(first, "daily")
        daily_guess(first, first_game["gameId"], "slate")

        assert first.get("/api/bootstrap").json()["daily"]["availability"] == (
            "used"
        )
        assert second.get("/api/bootstrap").json()["daily"]["availability"] == (
            "available"
        )
        assert start_game(second, "daily")["mode"] == "daily"


def test_new_reset_window_makes_daily_available_again(client, clock) -> None:
    game = start_game(client, "daily")
    daily_guess(client, game["gameId"], "slate")

    clock.current = datetime(2026, 7, 29, 3, 0, tzinfo=UTC)
    bootstrap = client.get("/api/bootstrap").json()

    assert bootstrap["daily"]["puzzleKey"] == "2026-07-29"
    assert bootstrap["daily"]["availability"] == "available"


def test_daily_descent_clears_four_unique_stages_in_order(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "daily-descent.sqlite",
        daily_seed="daily-descent",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_row=6,
        fixed_session_seed="daily-descent-session",
        reverse_entry_enabled=False,
    )
    app = create_app(settings=settings, now_provider=clock)
    expected_presets = [
        "doubt-1@1",
        "doubt-2@1",
        "doubt-3@1",
        "deception@1",
    ]
    answers: list[str] = []

    with TestClient(app) as client:
        for stage_index, preset_key in enumerate(expected_presets, start=1):
            game = start_game(client, "daily")
            assert game["dailyStage"] == stage_index
            assert game["preset"]["presetKey"] == preset_key
            with sqlite3.connect(settings.db_path) as connection:
                answer = connection.execute(
                    "SELECT answer FROM games WHERE id = ?",
                    (game["gameId"],),
                ).fetchone()[0]
            answers.append(answer)
            result = daily_guess(client, game["gameId"], answer)
            assert result.status_code == 200
            assert result.json()["status"] == "won"
            bootstrap = client.get("/api/bootstrap").json()["daily"]
            expected_status = "completed" if stage_index == 4 else "checkpoint"
            assert bootstrap["status"] == expected_status
            assert bootstrap["clearedStages"] == stage_index

    assert len(set(answers)) == 4


def test_daily_descent_loss_blocks_later_stages(client: TestClient) -> None:
    game = start_game(client, "daily")
    for guess in ("slate", "fight", "mould", "berry", "shack", "dingo"):
        result = daily_guess(client, game["gameId"], guess)

    assert result.json()["status"] == "lost"
    bootstrap = client.get("/api/bootstrap").json()["daily"]
    assert bootstrap["status"] == "failed"
    blocked = client.post(
        "/api/games",
        json={"mode": "daily", "continuationToken": DAILY_TOKEN},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "DAILY_DESCENT_FINISHED"


def test_refresh_forfeits_an_active_daily_descent(client: TestClient) -> None:
    game = start_game(client, "daily")
    assert daily_guess(client, game["gameId"], "slate").status_code == 200

    bootstrap = client.get("/api/bootstrap").json()["daily"]
    resumed = daily_guess(client, game["gameId"], "fight")

    assert bootstrap["status"] == "forfeited"
    assert resumed.status_code == 409
    assert resumed.json()["error"]["code"] == "DAILY_DESCENT_FINISHED"


def test_daily_descent_rejects_a_competing_page_token(client: TestClient) -> None:
    game = start_game(client, "daily")
    assert daily_guess(client, game["gameId"], "slate").status_code == 200

    competing = client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={
            "guess": "fight",
            "continuationToken": "different-page-continuation-token-98765",
        },
    )

    assert competing.status_code == 409
    assert competing.json()["error"]["code"] == "CONTINUATION_MISMATCH"


def test_practice_games_avoid_immediate_repeat(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "practice.sqlite",
        daily_seed="practice-test",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        first = start_game(client)
        second = start_game(client)

    with sqlite3.connect(settings.db_path) as connection:
        rows = connection.execute(
            "SELECT answer FROM games WHERE id IN (?, ?) ORDER BY created_at",
            (first["gameId"], second["gameId"]),
        ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] != rows[1][0]


def test_daily_answer_persists_across_application_restart(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "persistent.sqlite",
        daily_seed="stable-seed",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
    )

    first_app = create_app(settings=settings, now_provider=clock)
    with TestClient(first_app) as client:
        start_game(client, "daily")

    with sqlite3.connect(settings.db_path) as connection:
        first_answers = connection.execute(
            """
            SELECT answer FROM daily_descent_puzzles
            WHERE puzzle_key = '2026-07-28' ORDER BY stage_index
            """
        ).fetchall()

    changed_seed = Settings(
        db_path=settings.db_path,
        daily_seed="different-seed",
        answer_list_version=settings.answer_list_version,
        data_dir=DEFAULT_DATA_DIR,
    )
    second_app = create_app(settings=changed_seed, now_provider=clock)
    with TestClient(second_app) as client:
        start_game(client, "daily")

    with sqlite3.connect(settings.db_path) as connection:
        second_answers = connection.execute(
            """
            SELECT answer FROM daily_descent_puzzles
            WHERE puzzle_key = '2026-07-28' ORDER BY stage_index
            """
        ).fetchall()

    assert len(first_answers) == 4
    assert len(set(first_answers)) == 4
    assert second_answers == first_answers


def test_activated_lie_is_secret_until_terminal_and_then_auditable(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "activated.sqlite",
        daily_seed="activated-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_row=1,
        fixed_session_seed="seed-0",
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        first = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        ).json()
        final = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "crane"},
        ).json()

    with sqlite3.connect(settings.db_path) as connection:
        recorded_reasons = connection.execute(
            """
            SELECT deception_reason FROM guesses
            WHERE game_id = ? ORDER BY attempt
            """,
            (game["gameId"],),
        ).fetchall()

    assert first == {
        "guess": "slate",
        "feedback": "BBGBY",
        "attempt": 1,
        "status": "playing",
    }
    assert final["deception"] == {
        "events": [
            {
                "outcome": "activated",
                "kind": "feedbackLie",
                "scheduledAttempt": 1,
                "changes": [{
                    "tileIndex": 4,
                    "letter": "e",
                    "truthfulFeedback": "G",
                    "displayedFeedback": "Y",
                }],
            }
        ],
    }
    assert recorded_reasons == [("activated",), ("not_scheduled",)]


def test_constraint_backed_lie_activates_when_curated_decoys_are_exhausted(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "constraint-backed.sqlite",
        daily_seed="constraint-backed-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="gnash",
        fixed_lie_row=3,
        fixed_session_seed="constraint-backed-session",
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        for guess in ("stare", "cloud"):
            response = client.post(
                f"/api/games/{game['gameId']}/guesses",
                json={"guess": guess},
            )
            assert response.status_code == 200
        third = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "picky"},
        ).json()
        final = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "gnash"},
        ).json()

    assert third["feedback"].count("Y") == 1
    assert third["feedback"].count("B") == 4
    assert final["deception"]["events"] == [
        {
            "outcome": "activated",
            "kind": "feedbackLie",
            "scheduledAttempt": 3,
            "changes": [{
                "tileIndex": third["feedback"].index("Y"),
                "letter": "picky"[third["feedback"].index("Y")],
                "truthfulFeedback": "B",
                "displayedFeedback": "Y",
            }],
        }
    ]


def test_truthful_deadline_reason_is_persisted(
    tmp_path: Path, clock, monkeypatch
) -> None:
    settings = Settings(
        db_path=tmp_path / "deadline-reason.sqlite",
        daily_seed="deadline-reason-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_row=1,
        fixed_session_seed="deadline-reason-session",
    )
    app = create_app(settings=settings, now_provider=clock)

    def deadline_decision(**kwargs) -> DeceptionDecision:
        return DeceptionDecision(
            feedback=kwargs["truth_feedback"],
            reason="deadline_expired",
        )

    monkeypatch.setattr(
        app.state.service.deception_engine,
        "choose_feedback",
        deadline_decision,
    )

    with TestClient(app) as client:
        game = start_game(client)
        response = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        )

    with sqlite3.connect(settings.db_path) as connection:
        reason = connection.execute(
            "SELECT deception_reason FROM guesses WHERE game_id = ?",
            (game["gameId"],),
        ).fetchone()[0]

    assert response.status_code == 200
    assert reason == "deadline_expired"


def test_two_scheduled_rows_can_activate_without_reusing_a_tile(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "two-activated.sqlite",
        daily_seed="two-activated-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_rows=(1, 2),
        fixed_session_seed="seed-0",
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        first = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        ).json()
        second = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "fight"},
        ).json()
        final = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "crane"},
        ).json()

    assert "deception" not in first
    assert "deception" not in second
    assert first["feedback"] == "BBGBY"
    assert second["feedback"] == "BBBYB"
    assert final["deception"] == {
        "events": [
            {
                "outcome": "activated",
                "kind": "feedbackLie",
                "scheduledAttempt": 1,
                "changes": [{
                    "tileIndex": 4,
                    "letter": "e",
                    "truthfulFeedback": "G",
                    "displayedFeedback": "Y",
                }],
            },
            {
                "outcome": "activated",
                "kind": "feedbackLie",
                "scheduledAttempt": 2,
                "changes": [{
                    "tileIndex": 3,
                    "letter": "h",
                    "truthfulFeedback": "B",
                    "displayedFeedback": "Y",
                }],
            },
        ]
    }


def test_daily_schedule_is_shared_while_practice_schedules_are_per_game(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "schedules.sqlite",
        daily_seed="schedule-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_rows=(2, 4),
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as first, TestClient(app) as second:
        start_game(first, "daily")
        start_game(second, "daily")
        start_game(first, "practice")
        start_game(second, "practice")

    with sqlite3.connect(settings.db_path) as connection:
        daily_schedules = connection.execute(
            """
            SELECT g.id, d.scheduled_attempt
            FROM deception_schedules d
            JOIN games g ON g.id = d.game_id
            WHERE g.mode = 'daily'
            ORDER BY g.id, d.scheduled_attempt
            """
        ).fetchall()
        practice_count = connection.execute(
            """
            SELECT COUNT(*) FROM deception_schedules d
            JOIN games g ON g.id = d.game_id
            WHERE g.mode = 'practice'
            """
        ).fetchone()[0]

    assert len(daily_schedules) == 4
    assert {row[1] for row in daily_schedules} == {2, 4}
    assert practice_count == 4


def test_schedule_persists_across_application_restart(
    tmp_path: Path, clock
) -> None:
    db_path = tmp_path / "schedule-restart.sqlite"
    first_settings = Settings(
        db_path=db_path,
        daily_seed="daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_rows=(2, 5),
        fixed_session_seed="first-session",
    )
    first_app = create_app(settings=first_settings, now_provider=clock)
    with TestClient(first_app) as client:
        start_game(client, "daily")

    second_settings = Settings(
        db_path=db_path,
        daily_seed="different",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_rows=(1, 4),
        fixed_session_seed="different-session",
    )
    second_app = create_app(settings=second_settings, now_provider=clock)
    with TestClient(second_app) as client:
        start_game(client, "daily")

    with sqlite3.connect(db_path) as connection:
        schedules = connection.execute(
            """
            SELECT d.scheduled_attempt, d.seed
            FROM deception_schedules d
            JOIN games g ON g.id = d.game_id
            WHERE g.mode = 'daily'
            ORDER BY g.id, d.scheduled_attempt
            """
        ).fetchall()

    assert len(schedules) == 4
    assert {row[0] for row in schedules} == {2, 5}
    assert {row[1] for row in schedules} == {"first-session"}


def test_existing_single_row_daily_schedule_is_not_expanded_midday(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "existing-daily.sqlite",
        daily_seed="existing-daily",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_rows=(2, 4),
        fixed_session_seed="existing-session",
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as first:
        game = start_game(first, "daily")

    with sqlite3.connect(settings.db_path) as connection:
        connection.execute(
            """
            DELETE FROM deception_schedules
            WHERE game_id = ? AND ordinal = 2
            """
            ,
            (game["gameId"],),
        )
        connection.execute(
            """
            UPDATE deception_schedules
            SET strategy_version = 1
            WHERE game_id = ?
            """
            ,
            (game["gameId"],),
        )

    with TestClient(app) as second:
        start_game(second, "daily")

    with sqlite3.connect(settings.db_path) as connection:
        schedule = connection.execute(
            """
            SELECT scheduled_attempt, strategy_version
            FROM deception_schedules
            WHERE game_id = ?
            """
            ,
            (game["gameId"],),
        ).fetchall()

    assert schedule == [(2, 1)]


def test_layer_one_database_migrates_without_injecting_midgame_lie(
    tmp_path: Path, clock
) -> None:
    db_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE devices (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );
            CREATE TABLE daily_puzzles (
                puzzle_key TEXT PRIMARY KEY,
                answer TEXT NOT NULL,
                answer_list_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE games (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL REFERENCES devices(id),
                mode TEXT NOT NULL,
                puzzle_key TEXT,
                answer TEXT NOT NULL,
                status TEXT NOT NULL,
                guess_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE daily_attempts (
                device_id TEXT NOT NULL,
                puzzle_key TEXT NOT NULL,
                game_id TEXT NOT NULL UNIQUE,
                consumed_at TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (device_id, puzzle_key)
            );
            CREATE TABLE guesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                guess TEXT NOT NULL,
                truth_feedback TEXT NOT NULL,
                display_feedback TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (game_id, attempt)
            );
            INSERT INTO devices VALUES (
                'legacy-device-12345678', '2026-07-28T12:00:00Z'
            );
            INSERT INTO games VALUES (
                'legacy-game', 'legacy-device-12345678', 'practice', NULL, 'crane',
                'playing', 1, '2026-07-28T12:00:00Z',
                '2026-07-28T12:00:00Z'
            );
            INSERT INTO guesses(
                game_id, attempt, guess, truth_feedback,
                display_feedback, created_at
            ) VALUES (
                'legacy-game', 1, 'slate', 'BBGBG', 'BBGBG',
                '2026-07-28T12:00:00Z'
            );
            """
        )

    settings = Settings(
        db_path=db_path,
        daily_seed="legacy",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_row=2,
        fixed_session_seed="legacy-session",
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        client.cookies.set(
            "deception_device", "legacy-device-12345678"
        )
        response = client.post(
            "/api/games/legacy-game/guesses",
            json={"guess": "crane"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "won"
    assert "deception" not in response.json()
    with sqlite3.connect(db_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        rules_version = connection.execute(
            "SELECT rules_version FROM games WHERE id = 'legacy-game'"
        ).fetchone()[0]
        legacy_reason = connection.execute(
            """
            SELECT deception_reason FROM guesses
            WHERE game_id = 'legacy-game' AND attempt = 1
            """
        ).fetchone()[0]
        assert version == 10
    assert rules_version == 1
    assert legacy_reason == "legacy_unknown"


def test_in_progress_version_two_game_keeps_its_stored_schedule(
    tmp_path: Path, clock
) -> None:
    settings = Settings(
        db_path=tmp_path / "version-two.sqlite",
        daily_seed="version-two",
        answer_list_version="test-v1",
        data_dir=DEFAULT_DATA_DIR,
        fixed_answer="crane",
        fixed_lie_row=2,
        fixed_session_seed="seed-0",
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        first = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        )
        assert first.json()["feedback"] == "BBGBG"

        with sqlite3.connect(settings.db_path) as connection:
            connection.execute(
                "UPDATE games SET rules_version = 2 WHERE id = ?",
                (game["gameId"],),
            )
            connection.execute(
                """
                UPDATE deception_schedules
                SET strategy_version = 1
                WHERE game_id = ?
                """,
                (game["gameId"],),
            )

        second = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "fight"},
        )

    assert second.status_code == 200
    assert second.json()["feedback"] == "BYBBB"


def test_unknown_and_finished_games_use_consistent_errors(
    client: TestClient,
) -> None:
    missing = client.post(
        "/api/games/not-a-game/guesses",
        json={"guess": "crane"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "GAME_NOT_FOUND"

    game = start_game(client)
    client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": "crane"},
    )
    finished = client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": "crane"},
    )
    assert finished.status_code == 409
    assert finished.json()["error"]["code"] == "GAME_FINISHED"


def test_framework_validation_uses_error_contract(client: TestClient) -> None:
    response = client.post("/api/games", json={})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "The request body is missing or invalid.",
        }
    }


def test_low_information_feedback_guarantees_reverse_entry(
    tmp_path: Path, clock
) -> None:
    app = create_app(
        settings=reverse_entry_settings(tmp_path, fixed_roll=1.0),
        now_provider=clock,
    )

    with TestClient(app) as client:
        game = start_game(client)
        trigger = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "fight"},
        )
        resolved = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "etals"},
        )
        ordinary = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "mould"},
        )

    assert trigger.status_code == 200
    assert trigger.json()["feedback"].count("B") >= 4
    assert trigger.json()["reverseEntry"] == {"state": "activated"}
    assert resolved.status_code == 200
    assert resolved.json()["guess"] == "slate"
    assert resolved.json()["reverseEntry"] == {"state": "resolved"}
    assert ordinary.status_code == 200
    assert "reverseEntry" not in ordinary.json()


def test_reverse_entry_chance_uses_ten_percent_threshold(
    tmp_path: Path, clock
) -> None:
    activated_app = create_app(
        settings=reverse_entry_settings(tmp_path, fixed_roll=0.099),
        now_provider=clock,
    )
    skipped = reverse_entry_settings(tmp_path, fixed_roll=0.10)
    skipped_app = create_app(
        settings=Settings(
            **{
                **skipped.__dict__,
                "db_path": tmp_path / "reverse-entry-skipped.sqlite",
            }
        ),
        now_provider=clock,
    )

    with TestClient(activated_app) as client:
        game = start_game(client)
        activated_result = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        ).json()
    with TestClient(skipped_app) as client:
        game = start_game(client)
        skipped_result = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        ).json()

    assert activated_result["feedback"].count("B") == 3
    assert activated_result["reverseEntry"] == {"state": "activated"}
    assert "reverseEntry" not in skipped_result


def test_invalid_reversed_word_does_not_consume_punishment(
    tmp_path: Path, clock
) -> None:
    settings = reverse_entry_settings(tmp_path, fixed_roll=1.0)
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "fight"},
        )
        invalid = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "zzzzz"},
        )
        accepted = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "enarc"},
        )

    assert invalid.status_code == 400
    assert invalid.json() == {
        "error": {
            "code": "INVALID_REVERSED_WORD",
            "message": "That guess isn’t accepted.",
        }
    }
    assert accepted.status_code == 200
    assert accepted.json()["guess"] == "crane"
    assert accepted.json()["status"] == "won"
    assert accepted.json()["reverseEntry"] == {"state": "resolved"}

    with sqlite3.connect(settings.db_path) as connection:
        row = connection.execute(
            """
            SELECT status, trigger_attempt, consumed_attempt
            FROM reverse_entry_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()
    assert row == ("consumed", 1, 2)


def test_terminal_guess_never_arms_reverse_entry(
    tmp_path: Path, clock
) -> None:
    app = create_app(
        settings=reverse_entry_settings(tmp_path, fixed_roll=0.0),
        now_provider=clock,
    )

    with TestClient(app) as client:
        game = start_game(client)
        result = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "crane"},
        ).json()

    assert result["status"] == "won"
    assert "reverseEntry" not in result


def test_guess_timer_is_secretly_scheduled_with_45_percent_boundary(
    tmp_path: Path, clock
) -> None:
    skipped_settings = guess_timer_settings(
        tmp_path,
        fixed_roll=0.45,
    )
    app = create_app(settings=skipped_settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)

    assert "timer" not in game
    with sqlite3.connect(skipped_settings.db_path) as connection:
        state = connection.execute(
            """
            SELECT status, scheduled_attempt, duration_seconds
            FROM guess_timer_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()
    assert state == ("skipped", None, None)


def test_timer_activation_takes_priority_over_reverse_entry(
    tmp_path: Path, clock
) -> None:
    settings = guess_timer_settings(
        tmp_path,
        duration=30,
        attempt=2,
        reverse_entry_enabled=True,
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        result = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        )

    assert result.status_code == 200
    assert result.json()["timer"] == {
        "state": "activated",
        "durationSeconds": 30,
        "startsAt": "2026-07-28T12:00:01Z",
        "deadlineAt": "2026-07-28T12:00:31Z",
    }
    assert "reverseEntry" not in result.json()

    with sqlite3.connect(settings.db_path) as connection:
        reverse_state = connection.execute(
            """
            SELECT status, trigger_attempt
            FROM reverse_entry_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()
        timer_state = connection.execute(
            """
            SELECT status, scheduled_attempt, duration_seconds
            FROM guess_timer_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()
    assert reverse_state == ("armed", None)
    assert timer_state == ("active", 2, 30)


def test_timer_deadline_starts_after_deception_processing(
    tmp_path: Path, clock, monkeypatch
) -> None:
    settings = replace(
        guess_timer_settings(tmp_path, duration=10, attempt=2),
        fixed_lie_row=1,
    )
    app = create_app(settings=settings, now_provider=clock)
    choose_feedback = app.state.service.deception_engine.choose_feedback

    def delayed_choose_feedback(**kwargs):
        clock.current += timedelta(seconds=15)
        return choose_feedback(**kwargs)

    monkeypatch.setattr(
        app.state.service.deception_engine,
        "choose_feedback",
        delayed_choose_feedback,
    )

    with TestClient(app) as client:
        game = start_game(client)
        result = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        )

    assert result.status_code == 200
    assert result.json()["timer"] == {
        "state": "activated",
        "durationSeconds": 10,
        "startsAt": "2026-07-28T12:00:16Z",
        "deadlineAt": "2026-07-28T12:00:26Z",
    }


def test_timer_expiration_consumes_guess_and_is_idempotent(
    tmp_path: Path, clock
) -> None:
    settings = guess_timer_settings(tmp_path, duration=10, attempt=2)
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        activated = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        )
        invalid = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "zzzzz"},
        )
        clock.current += timedelta(seconds=12)
        expired = client.post(
            f"/api/games/{game['gameId']}/timer/expire"
        )
        repeated = client.post(
            f"/api/games/{game['gameId']}/timer/expire"
        )
        won = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "crane"},
        )

    assert activated.json()["timer"]["durationSeconds"] == 10
    assert invalid.status_code == 400
    assert expired.status_code == 200
    assert expired.json() == {
        "timedOut": True,
        "attempt": 2,
        "status": "playing",
        "timer": {"state": "expired"},
    }
    assert repeated.json() == expired.json()
    assert won.json()["attempt"] == 3
    assert won.json()["status"] == "won"

    with sqlite3.connect(settings.db_path) as connection:
        game_row = connection.execute(
            "SELECT guess_count, status FROM games WHERE id = ?",
            (game["gameId"],),
        ).fetchone()
        timer_row = connection.execute(
            """
            SELECT status, resolved_attempt
            FROM guess_timer_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()
        attempts = connection.execute(
            """
            SELECT attempt FROM guesses
            WHERE game_id = ?
            ORDER BY attempt
            """,
            (game["gameId"],),
        ).fetchall()
    assert game_row == (3, "won")
    assert timer_row == ("expired", 2)
    assert attempts == [(1,), (3,)]


def test_late_guess_is_converted_to_a_timed_out_attempt(
    tmp_path: Path, clock
) -> None:
    settings = guess_timer_settings(tmp_path, duration=10, attempt=2)
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        )
        clock.current += timedelta(seconds=12)
        late_guess = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "crane"},
        )

    assert late_guess.status_code == 200
    assert late_guess.json() == {
        "timedOut": True,
        "attempt": 2,
        "status": "playing",
        "timer": {"state": "expired"},
    }


def test_blackout_activates_after_its_selected_late_game_row(
    tmp_path: Path, clock
) -> None:
    settings = blackout_settings(tmp_path, attempt=3)
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        first = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        ).json()
        second = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "fight"},
        ).json()
        third = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "picky"},
        ).json()

    assert "blackout" not in first
    assert "blackout" not in second
    assert third["blackout"] == {"state": "activated"}
    with sqlite3.connect(settings.db_path) as connection:
        state = connection.execute(
            """
            SELECT status, scheduled_attempt
            FROM blackout_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()
    assert state == ("activated", 3)


def test_blackout_uses_twenty_percent_selection_boundary(
    tmp_path: Path, clock
) -> None:
    settings = replace(
        blackout_settings(tmp_path, attempt=4),
        db_path=tmp_path / "blackout-boundary.sqlite",
        fixed_blackout_roll=0.20,
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)

    with sqlite3.connect(settings.db_path) as connection:
        state = connection.execute(
            """
            SELECT status, scheduled_attempt
            FROM blackout_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()
    assert state == ("skipped", None)


def test_winning_guess_cancels_a_scheduled_blackout(
    tmp_path: Path, clock
) -> None:
    settings = blackout_settings(tmp_path, attempt=3)
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        for guess in ("slate", "fight"):
            client.post(
                f"/api/games/{game['gameId']}/guesses",
                json={"guess": guess},
            )
        result = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "crane"},
        ).json()

    assert result["status"] == "won"
    assert "blackout" not in result


def test_blackout_reserves_its_row_and_following_row_from_other_punishments(
    tmp_path: Path, clock
) -> None:
    settings = blackout_settings(
        tmp_path,
        attempt=3,
        reverse_entry_enabled=True,
        guess_timer_enabled=True,
        timer_attempt=3,
    )
    app = create_app(settings=settings, now_provider=clock)

    with TestClient(app) as client:
        game = start_game(client)
        first = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "slate"},
        ).json()
        second = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "fight"},
        ).json()
        third = client.post(
            f"/api/games/{game['gameId']}/guesses",
            json={"guess": "picky"},
        ).json()

    assert "reverseEntry" not in second
    assert "reverseEntry" not in third
    assert third["blackout"] == {"state": "activated"}
    with sqlite3.connect(settings.db_path) as connection:
        timer_attempt = connection.execute(
            """
            SELECT scheduled_attempt FROM guess_timer_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()[0]
        reverse_state = connection.execute(
            """
            SELECT status, trigger_attempt FROM reverse_entry_states
            WHERE game_id = ?
            """,
            (game["gameId"],),
        ).fetchone()
    assert timer_attempt not in {3, 4}
    assert reverse_state == ("armed", None)
