"""Runtime configuration read from environment variables (and a local `.env` in development)."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
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
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Hosts like Neon hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
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
