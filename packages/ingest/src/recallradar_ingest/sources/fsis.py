"""USDA FSIS recalls and public health alerts (meat, poultry, and egg products).

- The Recall API (https://www.fsis.usda.gov/fsis/api/recall/v/1, documented at
  /science-data/developer-resources/recall-api) returns every notice since 2014 in one JSON array,
  English and Spanish versions as separate records. No paging, GET only.
- FSIS's CDN refuses scripted clients (HTTP 403 from this project's network and from GitHub's
  runners, 2026-10-15) while browsers get the data. We don't disguise requests to get past it:
  `fetch` reports the refusal, and `load_file` imports a copy saved from a browser.
- Products are bullet items ("5-lb. packages of “Daisyfield Brand FRESH PORK SAUSAGE” with
  production dates ..."). Most notices give the establishment number printed inside the USDA mark
  of inspection ("EST. 818", "P-46684"), the best identifier on a meat package.
- Company and media contacts (names, phones, emails) are never stored.
"""

import html
import json
import re
from collections.abc import Iterable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from recallradar_core.categories import Category
from recallradar_core.enums import NoticeType, RecallSource, RecallStatus, RemedyType
from recallradar_ingest.extract import codes, restrictions
from recallradar_ingest.extract.restrictions import Restriction, RestrictionKind
from recallradar_ingest.extract.text import clean, sentences, truncate
from recallradar_ingest.http import get_json
from recallradar_ingest.records import ProductRecord, RecallRecord, barcodes, content_hash

URL = "https://www.fsis.usda.gov/fsis/api/recall/v/1"


class BlockedError(RuntimeError):
    """FSIS refused an automated request. Import a copy saved from a browser instead."""


_TAG = re.compile(r"<[^>]+>")
_BULLET = re.compile(r"^[\s•·\-*]+")
_FIRM = re.compile(r"^(?P<firm>.+?)\s+(?:Recalls|Expands|Retira)\b")
# "EST. 818", "EST. M46684", "EST. NO G-01", "P-46684", "G1804".
_ESTABLISHMENT = re.compile(
    r"\b(?:EST\.?\s*(?:NO\.?\s*)?(?P<est>[A-Z]{0,2}-?\d{1,6}[A-Z]?)"
    r"|(?P<plain>[PMVG]-?\d{3,6}[A-Z]?))\b",
    re.I,
)
# Quotes and apostrophes as FSIS prints them: straight or curly (\u201c, \u2019).
_BRAND = re.compile(
    "[\u201c\"](?P<brand>[A-Z][\\w'\u2019&.-]*(?:\\s+[\\w'\u2019&.-]+){0,3})\\s+Brand\\b"
)
_ALL_DATES = re.compile(r"regardless of the product date|all\b[^.]*\bproduct dates?\b", re.I)
_PRODUCED = re.compile(
    r"\b(?:were|was)\s+(?:produced|packaged|processed|slaughtered)\s+(?:on|from|between|prior)",
    re.I,
)
# The product names inside an item: "... packages of “Oscar Mayer Turkey BACON ORIGINAL” and UPC".
_QUOTED = re.compile('[\u201c"]([^\u201d"]{3,120})[\u201d"]')
# Older titles name the firm generically: "Oklahoma Firm Recalls ...".
_GENERIC_FIRM = re.compile(r"\b(?:firm|establishment|company|facility)$", re.I)
# Quoted dates and codes ("18 JUL 2025", "RS40") aren't product names.
_CODE_ONLY = re.compile(
    r"^(?:[\dA-Z\s/.:-]{1,14}|(?:use|best|sell|packed|pack|freeze|enjoy|exp\w*|est)\b.*)$", re.I
)
_REMEDY = re.compile(r"\burged not to consume|thrown away or returned|not to serve\b", re.I)
# "WASHINGTON, Oct. 02, 2026 - " with a hyphen, en dash, or em dash.
# Sentences naming a company or media contact (email or phone): not stored.
_CONTACT = re.compile(r"@|\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b|\bcontact\b", re.I)
_DATE_LINE = re.compile("^WASHINGTON,[^\u2013\u2014-]*[\u2013\u2014-]\\s*", re.I)
_HAZARD = re.compile(
    r"\b(may|might|could)\b.*\b(contain|contaminated|adulterated)|\bbecause\b|\bdue to\b", re.I
)
# "There have been no confirmed reports of illness ... due to consumption" isn't the hazard.
_NO_REPORTS = re.compile(r"\bno (?:confirmed )?reports?\b", re.I)
# "FSIS is issuing a public health alert for ... illegally imported from ...": says what's wrong
# when no sentence names a hazard.
_ANNOUNCE = re.compile(r"\b(?:is|are) (?:issuing|recalling)\b", re.I)


def fetch(client: httpx.Client) -> list[dict[str, Any]]:
    try:
        records = get_json(client, URL)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 403:
            raise BlockedError(
                "FSIS refused the request (403). Save the API response from a browser and run "
                "`recallradar-sync --source fsis --file <path>`."
            ) from error
        raise
    if not isinstance(records, list):
        raise ValueError(f"expected a JSON array from FSIS, got {type(records).__name__}")
    return records


def load_file(path: Path) -> list[dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"{path} is not the FSIS API's JSON array")
    return records


def english(
    records: Iterable[dict[str, Any]], *, start: date, end: date
) -> Iterator[dict[str, Any]]:
    """English notices with a recall date in the window (Spanish copies repeat them)."""
    first, last = start.isoformat(), end.isoformat()
    for record in records:
        when = str(record.get("field_recall_date") or "")
        if record.get("langcode") == "English" and first <= when <= last:
            yield record


def _text(value: Any) -> str:
    """HTML or a list of HTML fragments -> clean plain text."""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value)
    return clean(html.unescape(_TAG.sub(" ", str(value or ""))))


def _list(value: Any) -> list[str]:
    items = value if isinstance(value, list) else [value] if value else []
    return [t for t in (_text(v) for v in items) if t]


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def establishments(text: str) -> list[str]:
    found = []
    for match in _ESTABLISHMENT.finditer(text):
        number = (match.group("est") or match.group("plain") or "").upper()
        if any(c.isdigit() for c in number):
            found.append(number)
    return list(dict.fromkeys(found))


def parse(record: dict[str, Any]) -> RecallRecord:
    number = str(record["field_recall_number"]).strip()
    title = _text(record.get("field_title"))
    summary = _text(record.get("field_summary"))
    prose = [s for s in sentences(_DATE_LINE.sub("", summary)) if not _CONTACT.search(s)]
    kind = str(record.get("field_recall_type") or "")
    alert = kind == "Public Health Alert" or number.upper().startswith("PHA")
    firm_match = _FIRM.match(title)
    establishment_names = _list(record.get("field_establishment"))
    firm = firm_match.group("firm") if firm_match else None
    if (firm is None or _GENERIC_FIRM.search(firm)) and establishment_names:
        firm = establishment_names[0]

    reasons = _list(record.get("field_recall_reason"))
    hazard_sentence = next(
        (s for s in prose if _HAZARD.search(s) and not _NO_REPORTS.search(s)), None
    ) or next((s for s in prose if _ANNOUNCE.search(s)), None)
    hazard = hazard_sentence or ("; ".join(reasons) or None)
    remedy = " ".join(s for s in prose if _REMEDY.search(s)) or None
    est_numbers = establishments(summary)
    whole_notice_dates = not _ALL_DATES.search(summary)
    produced = next((s for s in prose if _PRODUCED.search(s)), None)

    items = _list(record.get("field_product_items")) or [title]
    products = []
    for index, raw_item in enumerate(items):
        item = _BULLET.sub("", raw_item).strip()
        scan = codes.scan(item)
        found = restrictions.cpsc_restrictions(item, scan) if whole_notice_dates else []
        if (
            produced
            and whole_notice_dates
            and not any(r.kind is RestrictionKind.DATE for r in found)
        ):
            found.append(Restriction(RestrictionKind.DATE, truncate(produced, 300)))
        brand = _BRAND.search(item)
        where = []
        if est_numbers:
            where.append(
                f"Look for establishment number {' or '.join(est_numbers[:3])} inside the USDA "
                "mark of inspection on the package."
            )
        if scan.dates or "date" in item.lower():
            where.append("The dates are printed on the label or package.")
        # Lead with the product's own name, where a brand usually comes first ("Oscar Mayer ...").
        names = [n.strip(" .,") for n in _QUOTED.findall(item) if not n.strip().isdigit()]
        names = [n for n in dict.fromkeys(names) if not _CODE_ONLY.match(n)]
        name = f"{'; '.join(names[:3])} | {item}" if names else item
        products.append(
            ProductRecord(
                source_product_id=str(index),
                product_name=truncate(name, 2000),
                brand=brand.group("brand") if brand else None,
                manufacturer=firm,
                lot_codes=scan.lots,
                weak_codes=est_numbers,
                upcs=barcodes(item),
                categories=[Category.MEAT_POULTRY_EGG],
                restrictions=found,
                where_to_look=where,
            )
        )

    active = str(record.get("field_active_notice")) == "True"
    official = str(record.get("field_recall_url") or "").replace("http://", "https://", 1)
    raw = {
        "type": kind,
        "risk_level": record.get("field_risk_level"),
        "reasons": reasons,
        "processing": _list(record.get("field_processing")),
        "outbreak": str(record.get("field_related_to_outbreak")) == "True",
        "closed_year": record.get("field_closed_year") or None,
        "quantity_recovered": _text(record.get("field_qty_recovered")) or None,
        "establishments": est_numbers,
        "text": content_hash([title, summary, items]),
    }
    return RecallRecord(
        source=RecallSource.FSIS,
        source_recall_id=number,
        reference=number,
        notice_type=NoticeType.ALERT if alert else NoticeType.RECALL,
        title=truncate(title, 300),
        description=truncate(" ".join(prose), 6000) or None,
        hazard=truncate(hazard, 1000) if hazard else None,
        remedy=remedy,
        remedy_type=RemedyType.DISPOSE if remedy else RemedyType.OTHER,
        recall_date=_day(record.get("field_recall_date")),
        published_date=_day(record.get("field_recall_date")),
        status=RecallStatus.ONGOING if active else RecallStatus.COMPLETED,
        official_url=official or None,
        firm=firm,
        classification=_text(record.get("field_recall_classification")) or None,
        distribution=", ".join(_list(record.get("field_states"))) or None,
        raw=raw,
        products=products,
    )
