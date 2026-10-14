"""Upserts and sync runs against a real (throwaway) Postgres database."""

import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from recallradar_core.db import Recall, RecallProduct, SyncRun
from recallradar_core.db.migrate import upgrade_to_head
from recallradar_core.enums import RecallSource, SyncMode, SyncStatus
from recallradar_ingest import store, sync
from recallradar_ingest.sources import cpsc, openfda

pytestmark = pytest.mark.db
FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def engine(create_database: Callable[[], str]) -> Iterator[Engine]:
    url = create_database()  # a fresh database per test: these tests commit
    upgrade_to_head(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_upsert_is_idempotent_and_detects_changes(sessions: sessionmaker[Session]) -> None:
    records = [cpsc.parse(raw) for raw in load("cpsc/recalls_by_id.json")]
    with sessions.begin() as session:
        first = store.upsert(session, records)
    assert (first.recalls_inserted, first.products_inserted) == (13, 13)

    with sessions.begin() as session:
        again = store.upsert(session, records)
    assert (again.recalls_unchanged, again.products_unchanged) == (13, 13)

    with sessions.begin() as session:
        session.execute(
            text("UPDATE recall_product SET embedding = array_fill(0.1, ARRAY[384])::halfvec")
        )
    changed = cpsc.parse(load("cpsc/recalls_by_id.json")[0])
    changed.products[0].product_name += " (corrected)"
    changed.raw["Title"] = "edited"
    # A change that doesn't touch the embedded text (name, brand, category) keeps the embedding.
    requantified = cpsc.parse(load("cpsc/recalls_by_id.json")[1])
    requantified.products[0].quantity = "About 1 (edited)"
    with sessions.begin() as session:
        result = store.upsert(session, [changed, requantified])
    assert (result.recalls_updated, result.products_updated) == (1, 2)
    with sessions() as session:
        embeddings = session.execute(
            select(RecallProduct.product_name, RecallProduct.embedding)
        ).all()
    cleared = [name for name, embedding in embeddings if embedding is None]
    assert len(cleared) == 1 and cleared[0].endswith("(corrected)")


def test_stored_products_keep_keys_and_restrictions(sessions: sessionmaker[Session]) -> None:
    records = openfda.parse_events(
        RecallSource.FDA_FOOD, load("openfda/food_event_99887.json")["results"]
    )
    with sessions.begin() as session:
        store.upsert(session, records)
    with sessions() as session:
        product = session.scalars(
            select(RecallProduct).where(RecallProduct.source_product_id == "H-1404-2026")
        ).one()
    assert product.lot_keys == ["SAL224JB", "TS146225 4".replace(" ", ""), "TS146253"]
    assert product.unit_restricted
    assert product.restrictions[0]["kind"] == "lot"
    assert product.categories == ["food"] and product.safety_critical


def test_fda_products_arriving_later_join_their_event(sessions: sessionmaker[Session]) -> None:
    raw = load("openfda/food_event_99887.json")["results"]
    for part in (raw[:2], raw[2:]):  # two weekly reports
        with sessions.begin() as session:
            records = openfda.parse_events(RecallSource.FDA_FOOD, part)
            store.upsert(session, records)
            store.refresh_fda_rollups(session, RecallSource.FDA_FOOD, ["99887"])
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Recall)) == 1
        assert session.scalar(select(func.count()).select_from(RecallProduct)) == 6
        recall = session.scalars(select(Recall)).one()
    assert recall.classification == "Class I"
    assert recall.published_date == date(2026, 10, 7)


def test_sync_run_records_counts_and_extraction(sessions: sessionmaker[Session]) -> None:
    window = load("cpsc/last_publish_window.json")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=window)))
    result = sync.run(
        sessions,
        RecallSource.CPSC,
        SyncMode.INCREMENTAL,
        client=client,
        since=date(2026, 10, 1),
        until=date(2026, 10, 8),
    )
    assert result.fetched == 20 and result.upserts.products_inserted == 20
    with sessions() as session:
        run = session.get_one(SyncRun, result.run_id)
    assert run.status is SyncStatus.SUCCEEDED and run.finished_at is not None
    assert run.details["extraction"]["products"] == 20
    assert run.details["window"] == ["2026-10-01", "2026-10-08"]


def test_failed_sync_is_recorded(sessions: sessionmaker[Session]) -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={})))
    with pytest.raises(httpx.HTTPStatusError):
        sync.run(
            sessions, RecallSource.CPSC, SyncMode.BACKFILL, client=client, since=date(2026, 1, 1)
        )
    with sessions() as session:
        run = session.scalars(select(SyncRun)).one()
    assert run.status is SyncStatus.FAILED and "400" in (run.error or "")


def test_incremental_window_starts_before_the_last_success(sessions: sessionmaker[Session]) -> None:
    with sessions.begin() as session:
        session.add(
            SyncRun(
                source=RecallSource.FDA_FOOD, mode=SyncMode.BACKFILL, status=SyncStatus.SUCCEEDED
            )
        )
    with sessions() as session:
        start = sync._window(session, RecallSource.FDA_FOOD, SyncMode.INCREMENTAL, None)
    # sync_run.started_at is UTC, so compare against the UTC date.
    assert (datetime.now(UTC).date() - start).days == 35
