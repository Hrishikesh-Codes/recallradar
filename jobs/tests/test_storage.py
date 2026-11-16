"""The storage report: real sizes from Postgres, and the limit check."""

from collections.abc import Callable

import pytest
from sqlalchemy import create_engine

from recallradar_jobs.storage_cli import database_mb, over_limit


@pytest.mark.db
def test_database_size_is_measured(create_database: Callable[[], str]) -> None:
    engine = create_engine(create_database())
    assert 1 < database_mb(engine) < 100  # an empty database is a few MB
    engine.dispose()


def test_only_databases_past_the_limit_are_reported() -> None:
    assert over_limit({"main": 431.0, "vectors": 180.0}, 430) == ["main"]
    assert over_limit({"main": 380.0, "vectors": 180.0}, 430) == []
