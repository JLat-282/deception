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
