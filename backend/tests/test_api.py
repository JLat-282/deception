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
