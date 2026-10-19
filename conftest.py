"""Shared pytest fixtures. Database tests run against throwaway databases created per session.

The server comes from TEST_DATABASE_URL (default: the local compose database), never from
DATABASE_URL, so a production URL in someone's environment can't be touched by tests.
DB tests are skipped when Postgres isn't reachable, unless REQUIRE_DB_TESTS=1 (set in CI),
in which case they fail loudly instead of silently passing.
"""

import json
import os
import uuid
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from recallradar_core.db.migrate import upgrade_to_head
from recallradar_core.enums import RecallSource
from recallradar_core.settings import LOCAL_DATABASE_URL, Settings
from recallradar_ingest import store
from recallradar_ingest.sources import cpsc, fsis, nhtsa, openfda
from recallradar_matching.embed import Embedder, embed_missing


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


FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="session")
def embedder() -> Embedder:
    return Embedder(Settings().model_cache_dir)


def load_fixture_recalls(url: str, embedder: Embedder) -> None:
    """Migrate `url` and fill it with every real fixture recall (all sources), embedded."""
    upgrade_to_head(url)
    engine = create_engine(url)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    records = [cpsc.parse(raw) for raw in load_fixture("cpsc/recalls_by_id.json")]
    for source, name in [
        (RecallSource.FDA_FOOD, "openfda/food_by_recall_number.json"),
        (RecallSource.FDA_DRUG, "openfda/drug_by_recall_number.json"),
        (RecallSource.FDA_DEVICE, "openfda/device_by_recall_number.json"),
    ]:
        records += openfda.parse_events(source, load_fixture(name)["results"])
    rows = (FIXTURES / "nhtsa" / "flat_rcl_sample.txt").read_text(encoding="utf-8").splitlines()
    campaigns = nhtsa.read(iter(rows), start=date(2010, 1, 1), end=date(2030, 1, 1))
    records += [nhtsa.parse(campaign) for campaign in campaigns.values()]
    notices = fsis.english(
        load_fixture("fsis/recalls_sample.json"), start=date(2014, 1, 1), end=date(2030, 1, 1)
    )
    records += [fsis.parse(notice) for notice in notices]
    with sessions.begin() as session:
        store.upsert(session, records)
    embed_missing(sessions, embedder, batch_size=64)
    engine.dispose()


@pytest.fixture(scope="session")
def loaded_database_url(create_database: Callable[[], str], embedder: Embedder) -> str:
    """A database holding every fixture recall, shared by the session: don't write to it."""
    url = create_database()
    load_fixture_recalls(url, embedder)
    return url


@pytest.fixture
def writable_database_url(create_database: Callable[[], str], embedder: Embedder) -> str:
    """A fresh database with the fixture recalls, for tests that write."""
    url = create_database()
    load_fixture_recalls(url, embedder)
    return url
