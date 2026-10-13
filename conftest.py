"""Shared pytest fixtures. Database tests run against throwaway databases created per session.

The server comes from TEST_DATABASE_URL (default: the local compose database), never from
DATABASE_URL, so a production URL in someone's environment can't be touched by tests.
DB tests are skipped when Postgres isn't reachable, unless REQUIRE_DB_TESTS=1 (set in CI),
in which case they fail loudly instead of silently passing.
"""

import os
import uuid
from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError

from recallradar_core.db.migrate import upgrade_to_head
from recallradar_core.settings import LOCAL_DATABASE_URL


@pytest.fixture(scope="session")
def create_database() -> Iterator[Callable[[], str]]:
    """Factory for empty databases; every database it creates is dropped after the session."""
    server = make_url(os.environ.get("TEST_DATABASE_URL", LOCAL_DATABASE_URL))
    admin = create_engine(server.set(database="postgres"), isolation_level="AUTOCOMMIT")
    created: list[str] = []

    def create() -> str:
        name = f"rr_test_{uuid.uuid4().hex[:12]}"
        try:
            with admin.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{name}"'))
        except OperationalError as error:
            if os.environ.get("REQUIRE_DB_TESTS") == "1":
                raise
            pytest.skip(f"Postgres not reachable ({error.orig}); run `make up` to start it")
        created.append(name)
        return server.set(database=name).render_as_string(hide_password=False)

    yield create
    with admin.connect() as connection:
        for name in created:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="session")
def migrated_database_url(create_database: Callable[[], str]) -> str:
    """URL of a test database migrated to the latest schema (shared by the whole session)."""
    url = create_database()
    upgrade_to_head(url)
    return url
