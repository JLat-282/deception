from backend.app.config import Settings


def test_database_url_prefers_explicit_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://explicit.example/db")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://integration.example/db")

    assert (
        Settings.from_env().database_url
        == "postgresql://explicit.example/db"
    )


def test_database_url_falls_back_to_vercel_postgres_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_URL", "postgresql://integration.example/db")

    assert (
        Settings.from_env().database_url
        == "postgresql://integration.example/db"
    )


def test_database_url_removes_vercel_supabase_metadata(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "POSTGRES_URL",
        "postgresql://user:password@host:6543/postgres"
        "?sslmode=require&supa=base-pooler.x&application_name=deception",
    )

    assert Settings.from_env().database_url == (
        "postgresql://user:password@host:6543/postgres"
        "?sslmode=require&application_name=deception"
    )


def test_decision_budget_defaults_to_forty_milliseconds(monkeypatch) -> None:
    monkeypatch.delenv("DECEPTION_DECISION_BUDGET_MS", raising=False)

    assert Settings.from_env().deception_decision_budget_ms == 40
