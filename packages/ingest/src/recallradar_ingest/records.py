"""Source-independent recall records produced by the parsers and consumed by the store."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from recallradar_core.categories import Category, is_safety_critical
from recallradar_core.enums import NoticeType, RecallSource, RecallStatus, RemedyType
from recallradar_ingest.extract import gtin
from recallradar_ingest.extract.restrictions import Restriction
from recallradar_ingest.extract.text import code_key


def content_hash(payload: Any) -> str:
    """Stable sha256 of a JSON-able value (keys sorted), used to skip unchanged upserts."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


@dataclass
class ProductRecord:
    source_product_id: str
    product_name: str
    brand: str | None = None
    manufacturer: str | None = None
    model_numbers: list[str] = field(default_factory=list)
    lot_codes: list[str] = field(default_factory=list)
    upcs: list[str] = field(default_factory=list)  # GTIN-14
    weak_codes: list[str] = field(default_factory=list)
    sold_start_date: date | None = None
    sold_end_date: date | None = None
    retailers: list[str] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    restrictions: list[Restriction] = field(default_factory=list)
    where_to_look: list[str] = field(default_factory=list)
    quantity: str | None = None
    raw: dict[str, Any] | None = None

    @property
    def model_keys(self) -> list[str]:
        return _keys(self.model_numbers)

    @property
    def lot_keys(self) -> list[str]:
        return _keys(self.lot_codes)

    @property
    def weak_model_keys(self) -> list[str]:
        strong = set(self.model_keys)
        return [key for key in _keys(self.weak_codes) if key not in strong]

    @property
    def category(self) -> str | None:
        return self.categories[0].value if self.categories else None

    @property
    def safety_critical(self) -> bool:
        return is_safety_critical(self.categories)

    @property
    def unit_restricted(self) -> bool:
        return bool(self.restrictions)

    def hash(self) -> str:
        payload = asdict(self)
        payload["restrictions"] = [asdict(r) for r in self.restrictions]
        return content_hash(payload)


@dataclass
class RecallRecord:
    source: RecallSource
    source_recall_id: str
    title: str
    raw: dict[str, Any]
    reference: str | None = None
    notice_type: NoticeType = NoticeType.RECALL
    description: str | None = None
    hazard: str | None = None
    remedy: str | None = None
    remedy_type: RemedyType | None = None
    recall_date: date | None = None
    published_date: date | None = None
    last_updated: datetime | None = None
    status: RecallStatus = RecallStatus.UNKNOWN
    official_url: str | None = None
    firm: str | None = None
    classification: str | None = None
    distribution: str | None = None
    products: list[ProductRecord] = field(default_factory=list)

    def hash(self) -> str:
        return content_hash(self.raw)


def _keys(values: list[str]) -> list[str]:
    return list(dict.fromkeys(key for key in (code_key(v) for v in values) if key))


def split_barcodes(values: list[str]) -> tuple[list[str], list[str]]:
    """Separate codes that are really barcodes (12-14 digits, valid check digit) from the rest.
    CPSC sometimes labels UPCs as SKU or item numbers."""
    plain: list[str] = []
    barcode: list[str] = []
    for value in values:
        normalized = gtin.normalize(value) if value.isdigit() and len(value) >= 12 else None
        (barcode if normalized else plain).append(normalized.gtin14 if normalized else value)
    return plain, barcode


def barcodes(*texts: str, listed: list[str] | None = None) -> list[str]:
    """GTIN-14s from structured barcode fields plus any found in the given texts."""
    found: dict[str, None] = {}
    for raw in listed or []:
        normalized = gtin.normalize(raw, allow_inferred=True)
        if normalized is not None:
            found[normalized.gtin14] = None
    for text in texts:
        for match in gtin.extract(text):
            found[match.gtin14] = None
    return list(found)
