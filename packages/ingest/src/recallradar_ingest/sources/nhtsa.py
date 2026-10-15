"""NHTSA recalls (vehicles, equipment, tires, child seats) from NHTSA's recall flat file.

- One download holds every campaign received since 2010: FLAT_RCL_POST_2010.zip (~15 MB zipped,
  ~310 MB of text, refreshed daily). The layout is RCL.txt (tests/fixtures/nhtsa/RCL.txt): one
  tab-separated UTF-8 row per make, model, model year and component; a campaign is `CAMPNO`.
- No paging or keys. Backfills and incremental syncs download the same file and keep the
  campaigns whose report was received (`RCDATE`) in the window.
- Vehicle recalls cover "certain" vehicles, identified by VIN. NHTSA's public API has no VIN
  lookup, so a vehicle match is at most "Check your unit", with a link to NHTSA's VIN search.
"""

import io
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from recallradar_core.categories import Category
from recallradar_core.enums import RecallSource, RemedyType
from recallradar_ingest.extract import codes, restrictions
from recallradar_ingest.extract.restrictions import Restriction, RestrictionKind
from recallradar_ingest.extract.text import clean, truncate
from recallradar_ingest.http import get_bytes
from recallradar_ingest.records import ProductRecord, RecallRecord, content_hash

URL = "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip"
RECALL_URL = "https://www.nhtsa.gov/recalls?nhtsaId={campaign}"
FIELDS = (
    "RECORD_ID", "CAMPNO", "MAKETXT", "MODELTXT", "YEARTXT", "MFGCAMPNO", "COMPNAME", "MFGNAME",
    "BGMAN", "ENDMAN", "RCLTYPECD", "POTAFF", "ODATE", "INFLUENCED_BY", "MFGTXT", "RCDATE",
    "DATEA", "RPNO", "FMVSS", "DESC_DEFECT", "CONEQUENCE_DEFECT", "CORRECTIVE_ACTION", "NOTES",
    "RCL_CMPT_ID", "MFR_COMP_NAME", "MFR_COMP_DESC", "MFR_COMP_PTNO", "DO_NOT_DRIVE",
    "PARK_OUTSIDE",
)  # fmt: skip
# Fields that differ between a campaign's rows; the rest repeat on every row.
_ROW_FIELDS = ("MAKETXT", "MODELTXT", "YEARTXT", "COMPNAME", "MFR_COMP_PTNO")
KINDS = {"V": "Vehicle", "E": "Equipment", "T": "Tire", "C": "Child seat"}
_CATEGORIES = {
    "V": [Category.VEHICLE],
    "E": [Category.VEHICLE_EQUIPMENT],
    "T": [Category.VEHICLE_EQUIPMENT],
    "C": [Category.VEHICLE_EQUIPMENT, Category.INFANT_CHILD],
}
# Paraphrased from NHTSA's recall lookup page and labelling rules.
_WHERE_TO_LOOK = {
    "V": "Your 17-character VIN is on the lower left of the windshield and on your registration.",
    "C": "Car seats carry labels with the model number and the date of manufacture.",
    "T": "The tire's DOT code and size are molded into its sidewall.",
}
_CERTAIN = re.compile(r"\bcertain\b", re.I)
BATCH_CAMPAIGNS = 200


@dataclass
class Campaign:
    """One campaign's shared fields, plus the fields that vary by row."""

    fields: dict[str, str]
    rows: list[dict[str, str]] = field(default_factory=list)


def _parse_day(value: str) -> date | None:
    value = value.strip()
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    except ValueError:
        return None


def read(lines: Iterator[str], *, start: date, end: date) -> dict[str, Campaign]:
    """Group flat-file rows into campaigns whose report was received between start and end."""
    first, last = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    campaigns: dict[str, Campaign] = {}
    for line in lines:
        values = line.rstrip("\r\n").split("\t")
        if len(values) != len(FIELDS):
            continue
        row = dict(zip(FIELDS, values, strict=True))
        if not first <= row["RCDATE"].strip() <= last:
            continue
        number = row["CAMPNO"].strip()
        campaign = campaigns.get(number)
        if campaign is None:
            campaign = campaigns[number] = Campaign(fields=row)
        campaign.rows.append({key: row[key] for key in _ROW_FIELDS})
    return campaigns


def fetch(client: httpx.Client, *, start: date, end: date) -> Iterator[list[Campaign]]:
    """Download the flat file and yield its campaigns in the window, in batches."""
    archive = zipfile.ZipFile(io.BytesIO(get_bytes(client, URL)))
    (member,) = [name for name in archive.namelist() if name.lower().endswith(".txt")]
    with archive.open(member) as raw:
        lines = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
        campaigns = list(read(lines, start=start, end=end).values())
    for offset in range(0, len(campaigns), BATCH_CAMPAIGNS):
        yield campaigns[offset : offset + BATCH_CAMPAIGNS]


def _day(value: date) -> str:
    return f"{value:%B} {value.day}, {value.year}"


def _remedy_type(text: str) -> RemedyType:
    lowered = text.lower()
    if re.search(r"\b(refund|reimburs\w*|repurchase|buy ?back)\b", lowered):
        return RemedyType.REFUND
    if re.search(r"\breplace\w*\b", lowered):
        return RemedyType.REPLACE
    if re.search(
        r"\b(repair\w*|inspect\w*|update\w*|reprogram\w*|install\w*|adjust\w*)\b", lowered
    ):
        return RemedyType.REPAIR
    return RemedyType.OTHER


def _years(values: set[str]) -> list[int]:
    return sorted(int(v) for v in values if v.isdigit() and 1900 < int(v) < 2100)


def _span(years: list[int]) -> str:
    if not years:
        return ""
    return str(years[0]) if years[0] == years[-1] else f"{years[0]}\u2013{years[-1]}"


def _subject(kind: str, models: list[tuple[str, str]], years: list[int]) -> str:
    noun = {"C": "child seats", "T": "tires"}.get(kind, "")
    names = [f"{make} {model}".strip() for make, model in models]
    if kind == "V":
        lead = f"{_span(years)} {names[0]}".strip()
        more = len(names) - 1
        return (
            lead if not more else f"{lead} and {more} more {'vehicle' if more == 1 else 'vehicles'}"
        )
    lead = " and ".join(names[:2]) + (f" and {len(names) - 2} more" if len(names) > 2 else "")
    return f"{lead} {noun}".strip()


def _unit_restrictions(kind: str, fields: dict[str, str], description: str) -> list[Restriction]:
    if kind == "V":
        return [
            Restriction(
                RestrictionKind.OTHER,
                "Only certain vehicles are included, identified by VIN. Check yours with "
                "NHTSA's VIN search.",
            )
        ]
    found = restrictions.cpsc_restrictions(description, codes.scan(description))
    begin, finish = _parse_day(fields["BGMAN"]), _parse_day(fields["ENDMAN"])
    if begin and finish and not any(r.kind is RestrictionKind.DATE for r in found):
        found.append(
            Restriction(
                RestrictionKind.DATE,
                f"Made between {_day(begin)} and {_day(finish)}.",
            )
        )
    if not found and _CERTAIN.search(description):
        found.append(
            Restriction(
                RestrictionKind.OTHER,
                "Only certain units are included; the official notice lists which.",
            )
        )
    return found


def parse(campaign: Campaign) -> RecallRecord:
    fields = campaign.fields
    number = fields["CAMPNO"].strip()
    kind = fields["RCLTYPECD"].strip() or "V"
    firm = clean(fields["MFGNAME"]) or clean(fields["MFGTXT"]) or None
    description = clean(fields["DESC_DEFECT"])
    consequence = clean(fields["CONEQUENCE_DEFECT"])
    remedy = clean(" ".join(filter(None, [fields["CORRECTIVE_ACTION"], fields["NOTES"]])))
    do_not_drive = fields["DO_NOT_DRIVE"].strip().lower().startswith("y")
    park_outside = fields["PARK_OUTSIDE"].strip().lower().startswith("y")
    advisories = []
    if do_not_drive:
        advisories.append("NHTSA advises: do not drive these vehicles until they are repaired.")
    if park_outside:
        advisories.append("NHTSA advises: park outside and away from buildings until repaired.")
    hazard = " ".join([*advisories, consequence]).strip() or None

    grouped: dict[tuple[str, str], dict[str, set[str]]] = {}
    for row in campaign.rows:
        key = (clean(row["MAKETXT"]).upper(), clean(row["MODELTXT"]).upper())
        info = grouped.setdefault(key, {"years": set(), "components": set(), "parts": set()})
        info["years"].add(row["YEARTXT"].strip())
        info["components"].add(clean(row["COMPNAME"]))
        info["parts"].add(clean(row["MFR_COMP_PTNO"]))

    unit_restrictions = _unit_restrictions(kind, fields, description)
    described = codes.scan(description) if kind != "V" else codes.CodeScan()
    # Equipment notices name models without a label: "recalling certain IFS20FT, IFS22FT ...".
    unlabelled = codes.unlabelled_models(description) if kind != "V" else []
    products = []
    all_years: set[int] = set()
    for (make, model), info in grouped.items():
        years = _years(info["years"])
        all_years.update(years)
        # A vehicle recall's part numbers name replacement parts, not what the owner has.
        parts = (
            []
            if kind == "V"
            else [p for p in info["parts"] if codes.is_code_like(p, kind=codes.CodeKind.MODEL)]
        )
        noun = {"C": " child seat", "T": " tires"}.get(kind, "")
        name = f"{make} {model}{noun}".strip()
        if kind == "V" and years:
            name = f"{name}, {_span(years)}"
        products.append(
            ProductRecord(
                source_product_id=f"{make}|{model}"[:300],
                product_name=name,
                brand=make or None,
                manufacturer=clean(fields["MFGTXT"]) or firm,
                model_numbers=list(dict.fromkeys(parts + described.models + unlabelled))[:50],
                lot_codes=described.lots[:50],
                categories=list(_CATEGORIES.get(kind, [Category.VEHICLE_EQUIPMENT])),
                restrictions=unit_restrictions,
                where_to_look=[_WHERE_TO_LOOK[kind]] if kind in _WHERE_TO_LOOK else [],
                vehicle=(make, model) if kind == "V" else None,
                model_years=years,
                raw={"components": sorted(info["components"])[:10]},
            )
        )

    subject = _subject(kind, list(grouped), sorted(all_years))
    component = clean(fields["COMPNAME"]).split(":")[-1].strip().lower()
    title = f"{firm or 'Manufacturer'} recalls {subject}" + (f" ({component})" if component else "")
    raw: dict[str, Any] = {
        "type": kind,
        "units_affected": int(fields["POTAFF"]) if fields["POTAFF"].strip().isdigit() else None,
        "owners_notified": fields["ODATE"].strip() or None,
        "initiated_by": clean(fields["INFLUENCED_BY"]) or None,
        "manufacturer_campaign": clean(fields["MFGCAMPNO"]) or None,
        "do_not_drive": do_not_drive,
        "park_outside": park_outside,
        # Edits to the notice's text change this hash, so updates are picked up.
        "text": content_hash([description, consequence, remedy]),
    }
    received = _parse_day(fields["RCDATE"])
    return RecallRecord(
        source=RecallSource.NHTSA,
        source_recall_id=number,
        reference=number,
        title=truncate(title, 300),
        description=description or None,
        hazard=hazard,
        remedy=remedy or None,
        remedy_type=_remedy_type(remedy),
        recall_date=received,
        published_date=received,
        official_url=RECALL_URL.format(campaign=number),
        firm=firm,
        classification=KINDS.get(kind),
        raw=raw,
        products=products,
    )
