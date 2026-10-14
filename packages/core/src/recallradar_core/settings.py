"""Runtime configuration read from environment variables (and a local `.env` in development)."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LOCAL_DATABASE_URL = "postgresql+psycopg://recallradar:recallradar@localhost:5432/recallradar"


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Environment = Environment.LOCAL
    database_url: str = LOCAL_DATABASE_URL
    log_level: str = "INFO"
    sentry_dsn: str | None = None
    # Where downloaded ML models (embeddings) are cached. The API image bakes them in.
    model_cache_dir: Path = Path.home() / ".cache" / "recallradar" / "models"
    # Optional: raises openFDA's limit from 1,000 to 120,000 requests/day.
    openfda_api_key: str | None = None
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Shared with the web server, which signs a short-lived token per request for signed-in
    # users (HS256). Without it, account endpoints are disabled.
    api_token_secret: SecretStr | None = None
    # Public web address, for links in emails.
    web_url: str = "http://localhost:3000"
    # Outgoing mail for alerts: smtp://localhost:1025 (Mailpit) locally, Resend's SMTP in prod.
    smtp_url: SecretStr | None = None
    mail_from: str = "RecallRadar <alerts@localhost>"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Hosts like Neon hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @field_validator("api_token_secret")
    @classmethod
    def _long_enough(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("API_TOKEN_SECRET must be at least 32 characters")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
