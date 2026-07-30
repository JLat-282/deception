from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from backend.app.config import DEFAULT_DATA_DIR, Settings
from backend.app.main import create_app


def start_game(client: TestClient, mode: str = "practice") -> dict:
    response = client.post("/api/games", json={"mode": mode})
    assert response.status_code == 200
    return response.json()


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
        },
    }
    cookie = response.cookies.get("deception_device")
    assert cookie
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]


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

    short = client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": "cat"},
    )
    unknown = client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": "zzzzz"},
    )

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

    guess = client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": "slate"},
    )

    assert guess.status_code == 200
    assert client.get("/api/bootstrap").json()["daily"]["availability"] == "used"
    blocked = client.post("/api/games", json={"mode": "daily"})
    assert blocked.status_code == 409
    assert blocked.json() == {
        "error": {
            "code": "DAILY_ALREADY_USED",
            "message": "Today’s Daily attempt has already been used.",
        }
    }


def test_daily_attempt_is_isolated_by_anonymous_device(app) -> None:
    with TestClient(app) as first, TestClient(app) as second:
        first_game = start_game(first, "daily")
        first.post(
            f"/api/games/{first_game['gameId']}/guesses",
            json={"guess": "slate"},
        )

        assert first.get("/api/bootstrap").json()["daily"]["availability"] == (
            "used"
        )
        assert second.get("/api/bootstrap").json()["daily"]["availability"] == (
            "available"
        )
        assert start_game(second, "daily")["mode"] == "daily"


def test_new_reset_window_makes_daily_available_again(client, clock) -> None:
    game = start_game(client, "daily")
    client.post(
        f"/api/games/{game['gameId']}/guesses",
        json={"guess": "slate"},
    )

    clock.current = datetime(2026, 7, 29, 3, 0, tzinfo=UTC)
    bootstrap = client.get("/api/bootstrap").json()

    assert bootstrap["daily"]["puzzleKey"] == "2026-07-29"
    assert bootstrap["daily"]["availability"] == "available"


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
        first_answer = connection.execute(
            "SELECT answer FROM daily_puzzles WHERE puzzle_key = '2026-07-28'"
        ).fetchone()[0]

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
        second_answer = connection.execute(
            "SELECT answer FROM daily_puzzles WHERE puzzle_key = '2026-07-28'"
        ).fetchone()[0]

    assert second_answer == first_answer


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
                "scheduledAttempt": 1,
                "change": {
                    "tileIndex": 4,
                    "letter": "e",
                    "truthfulFeedback": "G",
                    "displayedFeedback": "Y",
                },
            }
        ],
    }


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
            "scheduledAttempt": 3,
            "change": {
                "tileIndex": third["feedback"].index("Y"),
                "letter": "picky"[third["feedback"].index("Y")],
                "truthfulFeedback": "B",
                "displayedFeedback": "Y",
            },
        }
    ]


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
                "scheduledAttempt": 1,
                "change": {
                    "tileIndex": 4,
                    "letter": "e",
                    "truthfulFeedback": "G",
                    "displayedFeedback": "Y",
                },
            },
            {
                "outcome": "activated",
                "scheduledAttempt": 2,
                "change": {
                    "tileIndex": 3,
                    "letter": "h",
                    "truthfulFeedback": "B",
                    "displayedFeedback": "Y",
                },
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
        daily_count = connection.execute(
            """
            SELECT COUNT(*) FROM deception_schedules
            WHERE daily_puzzle_key = '2026-07-28'
            """
        ).fetchone()[0]
        practice_count = connection.execute(
            """
            SELECT COUNT(*) FROM deception_schedules
            WHERE game_id IS NOT NULL
            """
        ).fetchone()[0]

    assert daily_count == 2
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
        schedule = connection.execute(
            """
            SELECT scheduled_attempt, seed
            FROM deception_schedules
            WHERE daily_puzzle_key = '2026-07-28'
            ORDER BY scheduled_attempt
            """
        ).fetchall()

    assert schedule == [
        (2, "first-session"),
        (5, "first-session"),
    ]


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
        start_game(first, "daily")

    with sqlite3.connect(settings.db_path) as connection:
        connection.execute(
            """
            DELETE FROM deception_schedules
            WHERE daily_puzzle_key = '2026-07-28' AND ordinal = 2
            """
        )
        connection.execute(
            """
            UPDATE deception_schedules
            SET strategy_version = 1
            WHERE daily_puzzle_key = '2026-07-28'
            """
        )

    with TestClient(app) as second:
        start_game(second, "daily")

    with sqlite3.connect(settings.db_path) as connection:
        schedule = connection.execute(
            """
            SELECT scheduled_attempt, strategy_version
            FROM deception_schedules
            WHERE daily_puzzle_key = '2026-07-28'
            """
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
        assert version == 3
    assert rules_version == 1


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
            "message": "Read backwards, that isn’t an accepted word.",
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
