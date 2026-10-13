import pytest

from recallradar_core.settings import Environment, Settings


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        (
            "postgresql://u:p@host/db?sslmode=require",
            "postgresql+psycopg://u:p@host/db?sslmode=require",
        ),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ],
)
def test_database_url_always_names_the_psycopg_driver(given: str, expected: str) -> None:
    assert Settings(database_url=given).database_url == expected


def test_cors_origins_accepts_a_comma_separated_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example,")
    assert Settings().cors_origins == ["https://a.example", "https://b.example"]


def test_environment_is_parsed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings().environment is Environment.PRODUCTION
