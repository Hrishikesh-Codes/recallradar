"""CPSC recalls via the SaferProducts.gov Recall Retrieval web service.

Official guide: "Recall Retrieval Web Services Programmer's Guide", v1.4 (2018-09-17).
- No paging: a request returns every match, so backfills go one calendar year at a time.
- A misspelled parameter is silently ignored and returns the whole database, so parameter names
  are checked against the documented list and oversized responses are rejected.
- Since 2015, every record has exactly one `Products` entry, its `Model` field is always empty,
  and only 6% list `ProductUPCs`; model numbers live in the free-text `Description`.
"""

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import httpx

from recallradar_core.categories import Category, classify
from recallradar_core.enums import NoticeType, RecallSource, RemedyType
from recallradar_ingest.extract import codes, dates, restrictions
from recallradar_ingest.extract.text import clean
from recallradar_ingest.http import get_json
from recallradar_ingest.records import ProductRecord, RecallRecord, barcodes, split_barcodes

URL = "https://www.saferproducts.gov/RestWebServices/Recall"

# From the programmer's guide. Anything else would be ignored and return all ~9,000 recalls.
DOCUMENTED_PARAMETERS = frozenset(
    {
        "RecallID", "RecallNumber", "RecallDateStart", "RecallDateEnd", "LastPublishDateStart",
        "LastPublishDateEnd", "RecallURL", "RecallTitle", "ConsumerContact", "RecallDescription",
        "ProductName", "InconjunctionURL", "ImageURL", "Injury", "Manufacturer", "Retailer",
        "Importer", "Distributor", "ManufacturerCountry", "UPC", "Hazard", "Remedy",
        "RemedyOption", "format",
    }
)  # fmt: skip
# Busiest year on record is well under 600; a response this big means a filter was ignored.
MAX_PLAUSIBLE_WINDOW = 3000

_REMEDIES = {
    "refund": RemedyType.REFUND,
    "repair": RemedyType.REPAIR,
    "replace": RemedyType.REPLACE,
    "dispose": RemedyType.DISPOSE,
}
_FIRM_IN_TITLE = re.compile(
    r"^(?P<firm>.+?)\s+(?:Recalls|Reannounces|Expands|Announces|Issues|Re-announces)\b"
)
_COMPANY_SUFFIX = re.compile(r",?\s+of\s+[^,]+(?:,\s*[^,]+)?$")
# CPSC product types that point at specific categories.
_TYPE_CATEGORIES = {
    "toys": Category.INFANT_CHILD,
    "cribs": Category.INFANT_CHILD,
    "strollers": Category.INFANT_CHILD,
    "nursery": Category.INFANT_CHILD,
    "children": Category.INFANT_CHILD,
    "baby": Category.INFANT_CHILD,
}


class SuspiciousResponseError(RuntimeError):
    """The API returned far more records than any real window holds (a filter was ignored)."""


def fetch(
    client: httpx.Client, *, start: date, end: date, by_last_publish: bool = False
) -> Iterator[list[dict[str, Any]]]:
    """Yield batches of raw recalls, one calendar year per request."""
    prefix = "LastPublishDate" if by_last_publish else "RecallDate"
    for year in range(start.year, end.year + 1):
        window_start = max(start, date(year, 1, 1))
        window_end = min(end, date(year, 12, 31))
        params = {
            "format": "json",
            f"{prefix}Start": window_start.isoformat(),
            f"{prefix}End": window_end.isoformat(),
        }
        unknown = set(params) - DOCUMENTED_PARAMETERS
        if unknown:  # pragma: no cover - guards future edits
            raise ValueError(f"undocumented CPSC parameters {unknown}")
        records = get_json(client, URL, params)
        if not isinstance(records, list):
            raise SuspiciousResponseError(f"expected a list, got {type(records).__name__}")
        if len(records) > MAX_PLAUSIBLE_WINDOW:
            raise SuspiciousResponseError(f"{len(records)} recalls for {params}")
        yield records


def _names(items: list[dict[str, Any]] | None, key: str = "Name") -> list[str]:
    return [
        clean(str(item.get(key) or "")) for item in items or [] if (item.get(key) or "").strip()
    ]


def _company(name: str) -> str:
    """'KTM Motorrad AG, of Austria' -> 'KTM Motorrad AG'."""
    return _COMPANY_SUFFIX.sub("", name).strip()


def _parse_day(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def _firm(record: dict[str, Any], title: str) -> str | None:
    if title.startswith("CPSC "):
        named = None
    elif match := _FIRM_IN_TITLE.match(title):
        named = match.group("firm")
    else:
        named = None
    if named:
        return named
    for key in ("Manufacturers", "Importers", "Distributors"):
        names = _names(record.get(key))
        if names:
            return _company(names[0])
    return None


def _categories(product_type: str, text: str) -> list[Category]:
    found = classify(text)
    for word, category in _TYPE_CATEGORIES.items():
        if word in product_type.lower():
            found.add(category)
    if not found or found <= {Category.INFANT_CHILD}:
        found.add(Category.CONSUMER_PRODUCT)
    # Stable order, most specific first.
    return sorted(found, key=list(Category).index)


def _retailers(text: str) -> list[str]:
    """Store names from retailer text: "Target, Kmart and juvenile stores nationwide from ..."."""
    text = re.sub(r"^sold\s+(?:online\s+)?at:\s*", "", text, flags=re.I)
    head = re.split(r"\s+(?:nationwide|from|for|in|between|exclusively)\b", text, maxsplit=1)[0]
    head = re.sub(
        r"^(?:sold\s+)?(?:online\s+)?(?:exclusively\s+)?(?:at|on)\s+", "", head, flags=re.I
    )
    parts = re.split(r",\s*|\s+and\s+(?:online\s+at\s+)?|\s+&\s+", head)
    names = [
        p.strip(" .")
        for p in parts
        if 2 < len(p.strip()) <= 40 and not re.match(r"(?:of|and|the)\b", p.strip(), re.I)
    ]
    return list(dict.fromkeys(names))[:8]


def parse(record: dict[str, Any]) -> RecallRecord:
    title = clean(record.get("Title"))
    description = clean(record.get("Description"))
    retail_text = " ".join(_names(record.get("Retailers")))
    scan = codes.scan(description)
    models, coded_barcodes = split_barcodes(scan.models)
    lots, weak = scan.lots, scan.table_codes
    remedy_options = [o.lower() for o in _names(record.get("RemedyOptions"), "Option")]
    remedy_type = next((_REMEDIES[o] for o in remedy_options if o in _REMEDIES), None)
    if remedy_type is None and remedy_options:
        remedy_type = RemedyType.OTHER
    sold_start, sold_end = dates.sold_window(retail_text)
    firm = _firm(record, title)
    manufacturers = [_company(n) for n in _names(record.get("Manufacturers"))]

    products = []
    for index, product in enumerate(record.get("Products") or [{}]):
        name = clean(product.get("Name")) or title
        products.append(
            ProductRecord(
                source_product_id=str(record["RecallID"]) + (f"-{index}" if index else ""),
                product_name=name,
                # CPSC has no brand field; the recalling firm named in the title is the closest.
                brand=firm,
                manufacturer=manufacturers[0] if manufacturers else None,
                model_numbers=models,
                lot_codes=lots,
                weak_codes=weak,
                upcs=barcodes(
                    description,
                    listed=[str(u.get("UPC")) for u in record.get("ProductUPCs") or []]
                    + coded_barcodes,
                ),
                sold_start_date=sold_start,
                sold_end_date=sold_end,
                retailers=_retailers(retail_text),
                categories=_categories(str(product.get("Type") or ""), f"{title} {name}"),
                restrictions=restrictions.cpsc_restrictions(description, scan),
                where_to_look=restrictions.where_to_look(description),
                quantity=clean(product.get("NumberOfUnits")) or None,
            )
        )

    last_publish = record.get("LastPublishDate")
    compact = {k: v for k, v in record.items() if k != "Images"}
    compact["Images"] = (record.get("Images") or [])[:3]
    return RecallRecord(
        source=RecallSource.CPSC,
        source_recall_id=str(record["RecallID"]),
        reference=str(record.get("RecallNumber") or "") or None,
        notice_type=NoticeType.WARNING if title.startswith("CPSC Warns") else NoticeType.RECALL,
        title=title,
        description=description or None,
        hazard="; ".join(_names(record.get("Hazards"))) or None,
        remedy=" ".join(_names(record.get("Remedies"))) or None,
        remedy_type=remedy_type,
        recall_date=_parse_day(record.get("RecallDate")),
        published_date=_parse_day(record.get("RecallDate")),
        last_updated=(
            datetime.fromisoformat(last_publish).replace(tzinfo=UTC) if last_publish else None
        ),
        official_url=record.get("URL") or None,
        firm=firm,
        distribution=retail_text or None,
        raw=compact,
        products=products,
    )
