"""FDA enforcement reports (food, drug, device) via openFDA.

Docs: https://open.fda.gov/apis/ (query parameters, paging, authentication).
- Each record is one recalled *product* (`recall_number`); products sharing an `event_id` are one
  recall. Products of one event can be classified in different weeks, so they are upserted one
  by one and never deleted by a sync.
- `skip` paging stops at 26,000 hits; we page with `search_after` via the `Link` header.
- Data is updated weekly and appears only after FDA classifies a recall, so it lags company
  announcements. openFDA asks that it not be used to issue alerts to the public; RecallRadar
  checks products against it but sends email alerts only for CPSC recalls (see DECISIONS.md).
- A search with no results is HTTP 404 with {"error": {"code": "NOT_FOUND"}}.
- Device `more_code_info` can be megabytes of serial numbers (269 MB across 3% of 2015+ records);
  it is dropped from stored raw records, and `code_info` is capped. Extraction sees the full text.
- To OR several values of one field, group them: `recall_number:("A" "B")`. Repeating the field
  returns only the last match, and unquoted values match unrelated records.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from typing import Any

import httpx

from recallradar_core.categories import Category, classify
from recallradar_core.enums import RecallSource, RecallStatus
from recallradar_ingest.extract import codes, restrictions
from recallradar_ingest.extract.text import clean, truncate
from recallradar_ingest.http import NotFoundError, get_json_with_links
from recallradar_ingest.records import ProductRecord, RecallRecord, barcodes, split_barcodes

URL = "https://api.fda.gov/{kind}/enforcement.json"
PAGE_SIZE = 1000
RAW_CODE_INFO_CHARS = 2000
EVENT_URL = "https://www.accessdata.fda.gov/scripts/ires/index.cfm?Event={event_id}"

KINDS: dict[RecallSource, str] = {
    RecallSource.FDA_FOOD: "food",
    RecallSource.FDA_DRUG: "drug",
    RecallSource.FDA_DEVICE: "device",
}
_KIND_CATEGORY = {
    RecallSource.FDA_FOOD: Category.FOOD,
    RecallSource.FDA_DRUG: Category.DRUG,
    RecallSource.FDA_DEVICE: Category.MEDICAL_DEVICE,
}
_STATUS = {
    "ongoing": RecallStatus.ONGOING,
    "completed": RecallStatus.COMPLETED,
    "terminated": RecallStatus.TERMINATED,
}
_EVENT_FIELDS = (
    "event_id", "recalling_firm", "city", "state", "country", "distribution_pattern",
    "voluntary_mandated", "initial_firm_notification", "recall_initiation_date",
    "center_classification_date", "termination_date", "product_type",
)  # fmt: skip
_PRODUCT_FIELDS = (
    "recall_number", "product_description", "code_info", "product_quantity",
    "reason_for_recall", "classification", "status", "report_date",
)  # fmt: skip
_OPENFDA_FIELDS = ("brand_name", "generic_name", "manufacturer_name", "package_ndc", "upc")
_CORPORATE_SUFFIXES = re.compile(r"\b(Llc|Inc|Ltd|Corp|Co|Lp|Llp|Usa|Us|Pllc|Plc|Gmbh|Ag|Sa)\b")


def fetch(
    client: httpx.Client,
    source: RecallSource,
    *,
    start: date,
    end: date,
    api_key: str | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Yield pages of raw enforcement records reported between `start` and `end` (inclusive)."""
    params: dict[str, str | int] = {
        "search": f"report_date:[{start:%Y%m%d} TO {end:%Y%m%d}]",
        "limit": PAGE_SIZE,
        "sort": "report_date:asc",
    }
    if api_key:
        params["api_key"] = api_key
    url: str | None = URL.format(kind=KINDS[source])
    first = True
    while url is not None:
        try:
            body, links = get_json_with_links(client, url, params if first else None)
        except NotFoundError:
            return  # no records in this window
        first = False
        yield list(body.get("results") or [])
        url = links.get("next")


def _day(value: str | None) -> date | None:
    if not value or not re.fullmatch(r"\d{8}", value):
        return None
    return datetime.strptime(value, "%Y%m%d").date()  # noqa: DTZ007 - a calendar date


def _firm(name: str) -> str:
    """'TODD'S SEEDS LLC' -> "Todd's Seeds LLC" (leave mixed-case names alone)."""
    name = clean(name)
    if not name.isupper():
        return name
    titled = re.sub(r"\b([a-z])", lambda m: m.group(1).upper(), name.lower())
    titled = re.sub(r"'S\b", "'s", titled)
    return _CORPORATE_SUFFIXES.sub(lambda m: m.group(1).upper(), titled)


def _short(description: str) -> str:
    first = re.split(
        r"(?<=[a-z0-9)])[.;](?:\s|$)|,\s+(?:packaged|net|in\s+\d)", description, maxsplit=1
    )[0]
    return truncate(first.strip(" ,.;"), 100)


def _compact_product(record: dict[str, Any]) -> dict[str, Any]:
    compact = {key: record.get(key) for key in _PRODUCT_FIELDS}
    code_info = record.get("code_info") or ""
    if len(code_info) > RAW_CODE_INFO_CHARS:
        compact["code_info"] = code_info[:RAW_CODE_INFO_CHARS]
        compact["code_info_truncated_from"] = len(code_info)
    if more := record.get("more_code_info"):
        compact["more_code_info_chars"] = len(more)
    openfda = {k: v for k, v in (record.get("openfda") or {}).items() if k in _OPENFDA_FIELDS}
    if openfda:
        compact["openfda"] = openfda
    return compact


def _categories(source: RecallSource, text: str) -> list[Category]:
    found = classify(text) | {_KIND_CATEGORY[source]}
    if source is not RecallSource.FDA_FOOD:
        found -= {Category.FOOD, Category.MEAT_POULTRY_EGG}
    return sorted(found, key=list(Category).index)


def parse_product(source: RecallSource, record: dict[str, Any], firm: str) -> ProductRecord:
    description = clean(record.get("product_description"))
    code_info = clean(record.get("code_info"))
    scan = codes.scan(code_info)
    # Devices put model/REF/catalog numbers in the description too.
    described = codes.scan(description) if source is RecallSource.FDA_DEVICE else codes.CodeScan()
    openfda = record.get("openfda") or {}
    models, coded_barcodes = split_barcodes(list(dict.fromkeys(described.models + scan.models)))
    return ProductRecord(
        source_product_id=str(record["recall_number"]),
        product_name=truncate(description, 2000) or "Unnamed product",
        brand=(openfda.get("brand_name") or [None])[0],
        manufacturer=firm,
        model_numbers=models,
        lot_codes=scan.lots,
        weak_codes=described.table_codes + scan.table_codes,
        upcs=barcodes(
            description, code_info, listed=list(openfda.get("upc") or []) + coded_barcodes
        ),
        categories=_categories(source, description),
        restrictions=restrictions.fda_restrictions(code_info, scan),
        quantity=clean(record.get("product_quantity")) or None,
        raw=_compact_product(record),
    )


_SEVERITY = {"Class I": 1, "Class II": 2, "Class III": 3}


def _worst(classifications: Iterable[str]) -> str | None:
    """The most serious FDA class among an event's products (Class I is the most serious)."""
    known = [c for c in classifications if c in _SEVERITY]
    return min(known, key=_SEVERITY.__getitem__) if known else None


def _status(statuses: Iterable[str]) -> RecallStatus:
    values = {s.lower() for s in statuses}
    for status in ("ongoing", "completed", "terminated"):
        if status in values:
            return _STATUS[status]
    return RecallStatus.UNKNOWN


def parse_events(source: RecallSource, records: list[dict[str, Any]]) -> list[RecallRecord]:
    """Group product records into one RecallRecord per event_id."""
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_event[str(record["event_id"])].append(record)

    recalls = []
    for event_id, items in by_event.items():
        items.sort(key=lambda r: (r.get("report_date") or "", r.get("recall_number") or ""))
        first = items[0]
        firm = _firm(first.get("recalling_firm") or "Unknown firm")
        products = [parse_product(source, item, firm) for item in items]
        # No product count in the title: an event's products can arrive across several syncs.
        lead = _short(products[0].product_name)
        event_raw = {key: first.get(key) for key in _EVENT_FIELDS}
        recalls.append(
            RecallRecord(
                source=source,
                source_recall_id=event_id,
                reference=event_id,
                title=f"{firm} recalls {lead}",
                description=products[0].product_name,
                hazard=clean(first.get("reason_for_recall")) or None,
                recall_date=_day(first.get("recall_initiation_date")),
                published_date=min(
                    filter(None, (_day(i.get("report_date")) for i in items)), default=None
                ),
                status=_status(str(i.get("status") or "") for i in items),
                official_url=EVENT_URL.format(event_id=event_id),
                firm=firm,
                classification=_worst(str(i.get("classification") or "") for i in items),
                distribution=clean(first.get("distribution_pattern")) or None,
                raw=event_raw,
                products=products,
            )
        )
    return recalls
