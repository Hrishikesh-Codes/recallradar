"""Idempotent upserts of parsed recalls (SPEC §4.2).

Recalls are keyed on (source, source_recall_id), products on (recall, source_product_id). A row
whose content hash is unchanged is left alone. A changed product keeps its embedding unless the
text it was computed from (name, brand, category) changed; then the embed job recomputes it.
Nothing is deleted: FDA events gain products week by week.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import case, func, insert, null, or_, select, text, update
from sqlalchemy.orm import Session

from recallradar_core.db import Recall, RecallProduct
from recallradar_core.enums import RecallSource
from recallradar_ingest.records import ProductRecord, RecallRecord

# Neon's free plan stores 1 GB per project. Device recalls can list thousands of lot or serial
# codes; past these caps the full list stays in the restriction text and on the official notice.
MAX_CODES = 300
MAX_WEAK_CODES = 100


@dataclass
class UpsertStats:
    recalls_inserted: int = 0
    recalls_updated: int = 0
    recalls_unchanged: int = 0
    products_inserted: int = 0
    products_updated: int = 0
    products_unchanged: int = 0

    def add(self, other: "UpsertStats") -> None:
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))


def _recall_values(record: RecallRecord) -> dict[str, Any]:
    return {
        "source": record.source,
        "source_recall_id": record.source_recall_id,
        "reference": record.reference,
        "notice_type": record.notice_type,
        "title": record.title,
        "description": record.description,
        "hazard": record.hazard,
        "remedy": record.remedy,
        "remedy_type": record.remedy_type,
        "recall_date": record.recall_date,
        "published_date": record.published_date,
        "last_updated": record.last_updated,
        "status": record.status,
        "official_url": record.official_url,
        "firm": record.firm,
        "classification": record.classification,
        "distribution": record.distribution,
        "raw": record.raw,
        "content_hash": record.hash(),
    }


def _product_values(product: ProductRecord, recall_id: int) -> dict[str, Any]:
    return {
        "recall_id": recall_id,
        "source_product_id": product.source_product_id,
        "product_name": product.product_name,
        "brand": product.brand,
        "manufacturer": product.manufacturer,
        "model_numbers": product.model_numbers[:MAX_CODES],
        "lot_codes": product.lot_codes[:MAX_CODES],
        "upcs": product.upcs[:MAX_CODES],
        "model_keys": product.model_keys[:MAX_CODES],
        "lot_keys": product.lot_keys[:MAX_CODES],
        "weak_model_keys": product.weak_model_keys[:MAX_WEAK_CODES],
        "sold_start_date": product.sold_start_date,
        "sold_end_date": product.sold_end_date,
        "retailers": product.retailers,
        "category": product.category,
        "categories": [c.value for c in product.categories],
        "safety_critical": product.safety_critical,
        "unit_restricted": product.unit_restricted,
        "restrictions": [{"kind": r.kind.value, "detail": r.detail} for r in product.restrictions],
        "where_to_look": product.where_to_look,
        "quantity": product.quantity,
        "raw": product.raw,
        "content_hash": product.hash(),
    }


def upsert(session: Session, records: Iterable[RecallRecord]) -> UpsertStats:
    """Insert new recalls/products and update changed ones. Caller commits."""
    stats = UpsertStats()
    by_key: dict[tuple[RecallSource, str], RecallRecord] = {
        (r.source, r.source_recall_id): r for r in records
    }
    if not by_key:
        return stats

    existing: dict[tuple[RecallSource, str], tuple[int, str]] = {}
    for source in {source for source, _ in by_key}:
        ids = [rid for src, rid in by_key if src is source]
        rows = session.execute(
            select(Recall.source_recall_id, Recall.id, Recall.content_hash).where(
                Recall.source == source, Recall.source_recall_id.in_(ids)
            )
        )
        existing.update({(source, rid): (pk, digest) for rid, pk, digest in rows})

    new = [key for key in by_key if key not in existing]
    recall_ids: dict[tuple[RecallSource, str], int] = {k: v[0] for k, v in existing.items()}
    if new:
        inserted = session.execute(
            insert(Recall).returning(Recall.id, sort_by_parameter_order=True),
            [_recall_values(by_key[key]) for key in new],
        ).scalars()
        recall_ids.update(zip(new, inserted, strict=True))
        stats.recalls_inserted = len(new)
    for key, (pk, digest) in existing.items():
        values = _recall_values(by_key[key])
        if values["content_hash"] == digest:
            stats.recalls_unchanged += 1
            continue
        session.execute(
            update(Recall).where(Recall.id == pk).values(**values, updated_at=func.now())
        )
        stats.recalls_updated += 1

    known_products: dict[tuple[int, str], tuple[int, str]] = {
        (rid, spid): (pk, digest)
        for rid, spid, pk, digest in session.execute(
            select(
                RecallProduct.recall_id,
                RecallProduct.source_product_id,
                RecallProduct.id,
                RecallProduct.content_hash,
            ).where(RecallProduct.recall_id.in_(list(recall_ids.values())))
        )
    }
    to_insert: list[dict[str, Any]] = []
    for key, record in by_key.items():
        recall_id = recall_ids[key]
        for product in record.products:
            values = _product_values(product, recall_id)
            found = known_products.get((recall_id, product.source_product_id))
            if found is None:
                to_insert.append(values)
            elif found[1] == values["content_hash"]:
                stats.products_unchanged += 1
            else:
                # SET expressions see the row's old values.
                text_changed = or_(
                    RecallProduct.product_name.is_distinct_from(values["product_name"]),
                    RecallProduct.brand.is_distinct_from(values["brand"]),
                    RecallProduct.category.is_distinct_from(values["category"]),
                )
                session.execute(
                    update(RecallProduct)
                    .where(RecallProduct.id == found[0])
                    .values(
                        **values,
                        embedding=case((text_changed, null()), else_=RecallProduct.embedding),
                        updated_at=func.now(),
                    )
                )
                stats.products_updated += 1
    if to_insert:
        session.execute(insert(RecallProduct), to_insert)
        stats.products_inserted = len(to_insert)
    return stats


# An FDA event's products can arrive in different weekly reports, so the event-level status,
# classification, and publication date are recomputed from all of its stored products.
_FDA_ROLLUP = text(
    """
    UPDATE recall AS r
    SET status = rollup.status,
        classification = rollup.classification,
        published_date = rollup.published_date
    FROM (
        SELECT p.recall_id,
               CASE
                   WHEN bool_or(lower(p.raw->>'status') = 'ongoing') THEN 'ongoing'
                   WHEN bool_or(lower(p.raw->>'status') = 'completed') THEN 'completed'
                   WHEN bool_or(lower(p.raw->>'status') = 'terminated') THEN 'terminated'
                   ELSE 'unknown'
               END AS status,
               CASE min(CASE p.raw->>'classification'
                            WHEN 'Class I' THEN 1 WHEN 'Class II' THEN 2 WHEN 'Class III' THEN 3
                        END)
                   WHEN 1 THEN 'Class I' WHEN 2 THEN 'Class II' WHEN 3 THEN 'Class III'
               END AS classification,
               min(to_date(p.raw->>'report_date', 'YYYYMMDD')) AS published_date
        FROM recall_product AS p
        WHERE p.recall_id = ANY(:recall_ids)
        GROUP BY p.recall_id
    ) AS rollup
    WHERE r.id = rollup.recall_id
      AND (r.status, r.classification, r.published_date)
          IS DISTINCT FROM (rollup.status, rollup.classification, rollup.published_date)
    """
)


def refresh_fda_rollups(
    session: Session, source: RecallSource, source_recall_ids: list[str]
) -> None:
    ids = list(
        session.scalars(
            select(Recall.id).where(
                Recall.source == source, Recall.source_recall_id.in_(source_recall_ids)
            )
        )
    )
    if ids:
        session.execute(_FDA_ROLLUP, {"recall_ids": ids})
