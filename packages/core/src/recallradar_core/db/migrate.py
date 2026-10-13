"""Run Alembic migrations from code (tests, jobs). The CLI equivalent is `make migrate`."""

from alembic import command
from alembic.config import Config


def alembic_config(database_url: str | None = None) -> Config:
    """Config pointing at the packaged migrations; uses DATABASE_URL unless a URL is given."""
    config = Config()
    config.set_main_option("script_location", "recallradar_core:migrations")
    if database_url is not None:
        config.attributes["database_url"] = database_url
    return config


def upgrade_to_head(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")
