"""Run one ingester: fetch a window, parse, upsert in batches, and record a `sync_run`."""

import logging
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from recallradar_core.db import SyncRun
from recallradar_core.enums import RecallSource, SyncMode, SyncStatus
from recallradar_ingest import store
from recallradar_ingest.records import RecallRecord
from recallradar_ingest.sources import cpsc, fsis, nhtsa, openfda

logger = logging.getLogger("recallradar.ingest.sync")

# SPEC §4.2: backfill at least 10 years where available.
DEFAULT_BACKFILL_START = date(2015, 1, 1)
# Cars stay on the road for decades, so NHTSA goes back as far as its flat file does.
BACKFILL_START = {RecallSource.NHTSA: date(2010, 1, 1)}
# Re-read a little history every time: CPSC edits notices; openFDA corrects past reports weekly;
# NHTSA adds models to campaigns as manufacturers amend their reports.
INCREMENTAL_OVERLAP = {
    RecallSource.CPSC: timedelta(days=3),
    RecallSource.FDA_FOOD: timedelta(days=35),
    RecallSource.FDA_DRUG: timedelta(days=35),
    RecallSource.FDA_DEVICE: timedelta(days=35),
    RecallSource.NHTSA: timedelta(days=60),
    RecallSource.FSIS: timedelta(days=60),
}
# FSIS refuses automated requests (see sources/fsis.py), so `--source all` skips it; it's
# imported from a file saved in a browser until FSIS grants access.
AUTOMATED = tuple(source for source in INCREMENTAL_OVERLAP if source is not RecallSource.FSIS)
FDA_SOURCES = frozenset({RecallSource.FDA_FOOD, RecallSource.FDA_DRUG, RecallSource.FDA_DEVICE})
SUPPORTED = tuple(INCREMENTAL_OVERLAP)
BATCH = 200


@dataclass
class ExtractionStats:
    """How much the extractors found, logged per run so coverage changes are visible."""

    products: int = 0
    with_upcs: int = 0
    with_model_numbers: int = 0
    with_lot_codes: int = 0
    with_weak_codes_only: int = 0
    unit_restricted: int = 0
    safety_critical: int = 0

    def count(self, records: list[RecallRecord]) -> None:
        for record in records:
            for product in record.products:
                self.products += 1
                self.with_upcs += bool(product.upcs)
                self.with_model_numbers += bool(product.model_numbers)
                self.with_lot_codes += bool(product.lot_codes)
                self.with_weak_codes_only += bool(product.weak_codes) and not product.model_numbers
                self.unit_restricted += product.unit_restricted
                self.safety_critical += product.safety_critical


@dataclass
class SyncResult:
    run_id: int
    window: tuple[date, date]
    fetched: int = 0
    upserts: store.UpsertStats = field(default_factory=store.UpsertStats)
    extraction: ExtractionStats = field(default_factory=ExtractionStats)


def _window(session: Session, source: RecallSource, mode: SyncMode, since: date | None) -> date:
    if since is not None:
        return since
    backfill_start = BACKFILL_START.get(source, DEFAULT_BACKFILL_START)
    if mode is SyncMode.BACKFILL:
        return backfill_start
    last = session.scalar(
        select(SyncRun.started_at)
        .where(SyncRun.source == source, SyncRun.status == SyncStatus.SUCCEEDED)
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    return (last.date() - INCREMENTAL_OVERLAP[source]) if last else backfill_start


def _pages(
    client: httpx.Client,
    source: RecallSource,
    *,
    mode: SyncMode,
    start: date,
    end: date,
    openfda_api_key: str | None,
    file: Path | None = None,
) -> Iterator[list[RecallRecord]]:
    if source is RecallSource.CPSC:
        for raw in cpsc.fetch(
            client, start=start, end=end, by_last_publish=mode is SyncMode.INCREMENTAL
        ):
            yield [cpsc.parse(record) for record in raw]
    elif source is RecallSource.NHTSA:
        for campaigns in nhtsa.fetch(client, start=start, end=end):
            yield [nhtsa.parse(campaign) for campaign in campaigns]
    elif source is RecallSource.FSIS:
        raw = fsis.load_file(file) if file else fsis.fetch(client)
        notices = list(fsis.english(raw, start=start, end=end))
        for offset in range(0, len(notices), BATCH):
            yield [fsis.parse(record) for record in notices[offset : offset + BATCH]]
    else:
        for raw in openfda.fetch(client, source, start=start, end=end, api_key=openfda_api_key):
            yield openfda.parse_events(source, raw)


def run(
    session_factory: Callable[[], Session],
    source: RecallSource,
    mode: SyncMode,
    *,
    client: httpx.Client,
    since: date | None = None,
    until: date | None = None,
    openfda_api_key: str | None = None,
    file: Path | None = None,
) -> SyncResult:
    with session_factory() as session:
        start = _window(session, source, mode, since)
        end = until or datetime.now(UTC).date()
        sync_run = SyncRun(source=source, mode=mode, status=SyncStatus.RUNNING)
        session.add(sync_run)
        session.commit()
        result = SyncResult(run_id=sync_run.id, window=(start, end))

    logger.info(
        "sync started",
        extra={"source": source.value, "mode": mode.value, "start": start, "end": end},
    )
    try:
        pages = _pages(
            client,
            source,
            mode=mode,
            start=start,
            end=end,
            openfda_api_key=openfda_api_key,
            file=file,
        )
        for records in pages:
            result.fetched += sum(len(r.products) for r in records)
            result.extraction.count(records)
            for offset in range(0, len(records), BATCH):
                batch = records[offset : offset + BATCH]
                with session_factory() as session, session.begin():
                    result.upserts.add(store.upsert(session, batch))
                    if source in FDA_SOURCES:
                        store.refresh_fda_rollups(
                            session, source, [r.source_recall_id for r in batch]
                        )
    except Exception as error:
        _finish(session_factory, result, SyncStatus.FAILED, error=repr(error))
        logger.exception("sync failed", extra={"source": source.value})
        raise
    _finish(session_factory, result, SyncStatus.SUCCEEDED)
    logger.info(
        "sync finished",
        extra={"source": source.value, "fetched": result.fetched, **asdict(result.upserts)},
    )
    return result


def _finish(
    session_factory: Callable[[], Session],
    result: SyncResult,
    status: SyncStatus,
    error: str | None = None,
) -> None:
    details: dict[str, Any] = {
        "window": [result.window[0].isoformat(), result.window[1].isoformat()],
        "upserts": asdict(result.upserts),
        "extraction": asdict(result.extraction),
    }
    with session_factory() as session, session.begin():
        sync_run = session.get_one(SyncRun, result.run_id)
        sync_run.status = status
        sync_run.finished_at = datetime.now(UTC)
        sync_run.fetched = result.fetched
        sync_run.inserted = result.upserts.products_inserted
        sync_run.updated = result.upserts.products_updated
        sync_run.unchanged = result.upserts.products_unchanged
        sync_run.error = error
        sync_run.details = details
