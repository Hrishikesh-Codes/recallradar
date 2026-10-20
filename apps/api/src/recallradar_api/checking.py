"""One check: read the input, look it up, match it, and describe the result for the web app."""

import logging
import threading
import time
import uuid
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from recallradar_api import schemas
from recallradar_api.ratelimit import RateLimiter
from recallradar_core.db import BarcodeLookup, Event, Recall, RecallProduct, SyncRun
from recallradar_core.enums import SOURCE_LABELS, RecallSource, RemedyType, SyncStatus
from recallradar_identify.barcode import BarcodeInfo, lookup_open_food_facts
from recallradar_identify.parse import parse_input
from recallradar_identify.query import ProductQuery
from recallradar_identify.vin import Decoded, decode_vpic
from recallradar_matching.embed import Embedder
from recallradar_matching.engine import CheckResult, Match, check, embed_query
from recallradar_matching.vectors import VectorStore

logger = logging.getLogger("recallradar.api.check")

FOUND_TTL = timedelta(days=30)
NOT_FOUND_TTL = timedelta(days=3)
MAX_LISTED = 30  # codes per product in a response; the official notice has the full list
COVERAGE_TTL_SECONDS = 60.0


class BarcodeLookups:
    """Open Food Facts lookups, cached in the database and kept under its rate limit.

    Lookups run on our server, so users' IP addresses never reach Open Food Facts.
    """

    def __init__(self, client: httpx.Client, limiter: RateLimiter) -> None:
        self.client = client
        self.limiter = limiter

    def lookup(self, session: Session, gtin14: str) -> BarcodeInfo | None:
        cached = session.get(BarcodeLookup, gtin14)
        now = datetime.now(UTC)
        if cached is not None:
            ttl = FOUND_TTL if cached.found else NOT_FOUND_TTL
            if cached.fetched_at > now - ttl:
                return _info(cached) if cached.found else None
        if not self.limiter.allow("open_food_facts"):
            logger.info("barcode lookup skipped: rate limit")
            return _info(cached) if cached is not None and cached.found else None
        try:
            info = lookup_open_food_facts(self.client, gtin14)
        except (httpx.HTTPError, ValueError):
            logger.warning("barcode lookup failed", exc_info=True)
            return None
        values: dict[str, Any] = {
            "gtin14": gtin14,
            "source": "open_food_facts",
            "found": info is not None,
            "product_name": info.product_name if info else None,
            "brand": info.brand if info else None,
            "is_food": info.is_food if info else False,
            "fetched_at": now,
        }
        statement = insert(BarcodeLookup).values(**values)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[BarcodeLookup.gtin14],
                set_={k: statement.excluded[k] for k in values if k != "gtin14"},
            )
        )
        return info


def _info(row: BarcodeLookup) -> BarcodeInfo:
    return BarcodeInfo(
        gtin14=row.gtin14,
        source=row.source,
        product_name=row.product_name,
        brand=row.brand,
        is_food=row.is_food,
    )


class VinDecoder:
    """vPIC VIN decoding, remembered in memory for a day. VINs are never written to the
    database: a VIN-based check stores nothing about the vehicle."""

    def __init__(self, client: httpx.Client, max_entries: int = 2048) -> None:
        self.client = client
        self.max_entries = max_entries
        self._cache: OrderedDict[str, tuple[float, Decoded | None]] = OrderedDict()
        self._lock = threading.Lock()

    def __call__(self, vin: str) -> Decoded | None:
        with self._lock:
            hit = self._cache.get(vin)
            if hit and time.monotonic() - hit[0] < 86_400:
                return hit[1]
        try:
            decoded = decode_vpic(self.client, vin)
        except (httpx.HTTPError, ValueError):
            logger.warning("VIN decode failed", exc_info=True)
            return None
        with self._lock:
            self._cache[vin] = (time.monotonic(), decoded)
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
        return decoded


def build_query(
    session: Session,
    request: schemas.CheckRequest,
    barcodes: BarcodeLookups | None,
    vins: VinDecoder | None = None,
) -> ProductQuery:
    lookup = (lambda gtin14: barcodes.lookup(session, gtin14)) if barcodes else None
    query = parse_input(request.input.type, request.input.value, lookup, vins)
    if request.purchase_date is not None:
        query.purchase_date = request.purchase_date
    return query


class CoverageCache:
    """Recall counts and sync times per source; cheap, but asked for on every check."""

    def __init__(self) -> None:
        self._value: list[schemas.SourceCoverage] | None = None
        self._at = 0.0
        self._lock = threading.Lock()

    def get(self, session: Session) -> list[schemas.SourceCoverage]:
        with self._lock:
            if self._value is not None and time.monotonic() - self._at < COVERAGE_TTL_SECONDS:
                return self._value
        # Result objects have .keys(), so dict(result) would treat them as mappings.
        counts = {
            source: count
            for source, count in session.execute(
                select(Recall.source, func.count()).group_by(Recall.source)
            )
        }
        synced = {
            source: finished
            for source, finished in session.execute(
                select(SyncRun.source, func.max(SyncRun.finished_at))
                .where(SyncRun.status == SyncStatus.SUCCEEDED)
                .group_by(SyncRun.source)
            )
        }
        value = [
            schemas.SourceCoverage(
                source=source,
                label=SOURCE_LABELS[source],
                recalls=counts[source],
                last_synced_at=synced.get(source),
            )
            for source in RecallSource
            if counts.get(source)
        ]
        with self._lock:
            self._value, self._at = value, time.monotonic()
        return value

    def clear(self) -> None:
        with self._lock:
            self._value = None


def coverage_out(
    sources: list[schemas.SourceCoverage], not_covered: list[RecallSource]
) -> schemas.Coverage:
    synced = [s.last_synced_at for s in sources if s.last_synced_at]
    return schemas.Coverage(
        checked=sources,
        not_covered=not_covered,
        recalls_checked=sum(s.recalls for s in sources),
        # The oldest source's sync: "updated X ago" must hold for everything we checked.
        updated_at=min(synced) if synced else None,
    )


def recall_summary(recall: Recall) -> schemas.RecallSummary:
    images = recall.raw.get("Images") if isinstance(recall.raw, dict) else None
    image_url = None
    if isinstance(images, list) and images and isinstance(images[0], dict):
        image_url = images[0].get("URL")
    return schemas.RecallSummary(
        id=recall.id,
        source=recall.source,
        source_label=SOURCE_LABELS[recall.source],
        source_recall_id=recall.source_recall_id,
        reference=recall.reference,
        notice_type=recall.notice_type,
        title=recall.title,
        hazard=recall.hazard,
        remedy=recall.remedy,
        remedy_type=recall.remedy_type or RemedyType.OTHER,
        recall_date=recall.recall_date,
        status=recall.status,
        classification=recall.classification,
        firm=recall.firm,
        official_url=recall.official_url or "",
        image_url=image_url,
    )


def product_out(product: RecallProduct) -> schemas.ProductOut:
    return schemas.ProductOut(
        product_name=product.product_name,
        brand=product.brand,
        model_numbers=product.model_numbers[:MAX_LISTED],
        upcs=product.upcs[:MAX_LISTED],
        lot_codes=product.lot_codes[:MAX_LISTED],
        sold_start_date=product.sold_start_date,
        sold_end_date=product.sold_end_date,
        unit_restricted=product.unit_restricted,
        restrictions=[schemas.Restriction(**r) for r in product.restrictions],
        where_to_look=product.where_to_look,
        quantity=product.quantity,
    )


def match_out(match: Match) -> schemas.MatchOut:
    return schemas.MatchOut(
        tier=match.tier,
        recall=recall_summary(match.recall),
        product=product_out(match.product),
        reasons=match.reasons,
        what_to_check=match.what_to_check,
        similarity=round(max(match.signals.vector_similarity, match.signals.trigram_similarity), 3),
    )


def query_out(query: ProductQuery) -> schemas.QueryOut:
    return schemas.QueryOut(
        input_type=query.input_type.value,
        product_name=query.product_name,
        brand=query.brand,
        model_numbers=query.model_numbers,
        upcs=query.upcs,
        lot_codes=query.lot_codes,
        purchase_date=query.purchase_date,
        retailer=query.retailer,
        categories=[c.value for c in query.categories],
    )


def run_check(
    session: Session,
    request: schemas.CheckRequest,
    *,
    embedder: Embedder,
    barcodes: BarcodeLookups | None,
    coverage: CoverageCache,
    vins: VinDecoder | None = None,
    vectors: VectorStore | None = None,
) -> schemas.CheckResponse:
    started = time.perf_counter()
    query = build_query(session, request, barcodes, vins)
    sources = coverage.get(session)
    result: CheckResult = check(
        session,
        query,
        embedding=embed_query(embedder, query),
        ingested=[s.source for s in sources],
        vector_store=vectors,
    )
    check_id = uuid.uuid4()
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    # Usage metrics (SPEC §14): what kind of check and its outcome, never what was checked.
    session.add(
        Event(
            name="check",
            properties={
                "check_id": str(check_id),
                "input_type": query.input_type.value,
                "verdict": result.verdict.value,
                "matches": len(result.matches),
                "ms": elapsed_ms,
            },
        )
    )
    return schemas.CheckResponse(
        id=check_id,
        verdict=result.verdict,
        query=query_out(query),
        matches=[match_out(m) for m in result.matches],
        related=[match_out(m) for m in result.related],
        coverage=coverage_out(sources, result.uncovered_sources),
        notes=result.notes,
    )
