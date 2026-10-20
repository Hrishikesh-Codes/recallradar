"""Watched items: check one against every recall, and remember which recalls match it.

Used when a user saves an item (API) and whenever new recalls arrive (alerts job). Each check
re-parses what the user originally typed or scanned, so parser improvements reach old items.

M1 re-checks every watched item after a sync that added recalls. That is fine for thousands of
items; M3 replaces it with a reverse lookup (new recall -> candidate items) and benchmarks it.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from recallradar_core.db import BarcodeLookup, WatchItem, WatchMatch
from recallradar_core.enums import RecallSource
from recallradar_identify.barcode import BarcodeInfo, Lookup
from recallradar_identify.parse import InputKind, parse_input
from recallradar_identify.query import ProductQuery
from recallradar_identify.vin import Decoder
from recallradar_matching.embed import Embedder
from recallradar_matching.engine import CheckResult, Match, Tier, check, embed_query
from recallradar_matching.vectors import VectorStore

_MATCHING = frozenset({Tier.RECALLED, Tier.CHECK_UNIT})


def cached_lookup(session: Session) -> Lookup:
    """Barcode names from the lookup cache only: re-checks never call Open Food Facts."""

    def lookup(gtin14: str) -> BarcodeInfo | None:
        row = session.get(BarcodeLookup, gtin14)
        if row is None or not row.found:
            return None
        return BarcodeInfo(row.gtin14, row.source, row.product_name, row.brand, row.is_food)

    return lookup


_KINDS: dict[str, InputKind] = {
    "link": "link",
    "barcode": "barcode",
    "vin": "vin",
    "label": "label",
}


def item_query(
    session: Session, item: WatchItem, decode_vin: Decoder | None = None
) -> ProductQuery:
    kind = _KINDS.get(item.input_type, "text")
    query = parse_input(kind, item.input_value, cached_lookup(session), decode_vin)
    if item.purchase_date is not None:
        query.purchase_date = item.purchase_date
    return query


@dataclass
class Refresh:
    result: CheckResult
    verdict: Tier
    new_matches: list[Match] = field(default_factory=list)


def item_verdict(result: CheckResult, dismissed: set[int]) -> Tier:
    """The item's verdict once the user's "Not my product" answers are taken out."""
    active = [m for m in result.matches if m.recall.id not in dismissed and m.tier]
    if active:
        return active[0].tier or Tier.ALL_CLEAR
    return Tier.ALL_CLEAR if result.verdict in _MATCHING else result.verdict


def refresh(
    session: Session,
    item: WatchItem,
    *,
    embedder: Embedder,
    ingested: Sequence[RecallSource],
    query: ProductQuery | None = None,
    decode_vin: Decoder | None = None,
    vector_store: VectorStore | None = None,
) -> Refresh:
    """Re-check `item`, store its current matches, and report the ones that are new."""
    query = query or item_query(session, item, decode_vin)
    result = check(
        session,
        query,
        embedding=embed_query(embedder, query),
        ingested=ingested,
        vector_store=vector_store,
    )
    stored = {
        m.recall_id: m
        for m in session.scalars(select(WatchMatch).where(WatchMatch.item_id == item.id))
    }
    current = {m.recall.id: m for m in result.matches if m.tier}
    new: list[Match] = []
    for recall_id, match in current.items():
        tier = (match.tier or Tier.CHECK_UNIT).value
        row = stored.get(recall_id)
        if row is None:
            session.add(
                WatchMatch(item_id=item.id, recall_id=recall_id, tier=tier, reasons=match.reasons)
            )
            new.append(match)
        elif (row.tier, row.reasons) != (tier, match.reasons):
            row.tier, row.reasons = tier, match.reasons
    # A recall that no longer matches (the matcher improved) is dropped, unless the user
    # answered for it: their "Not my product" must survive re-checks.
    stale = [rid for rid, row in stored.items() if rid not in current and row.dismissed_at is None]
    if stale:
        session.execute(
            delete(WatchMatch).where(WatchMatch.item_id == item.id, WatchMatch.recall_id.in_(stale))
        )
    dismissed = {rid for rid, row in stored.items() if row.dismissed_at is not None}
    verdict = item_verdict(result, dismissed)
    item.verdict = verdict.value
    item.last_checked_at = datetime.now(UTC)
    return Refresh(result=result, verdict=verdict, new_matches=new)
