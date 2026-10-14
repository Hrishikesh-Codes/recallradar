"""Typed descriptions: "Fisher-Price baby rocker, 2023", "Instant Pot IP-DUO60", "UPC 0360..."."""

import re
from datetime import date

from recallradar_core.categories import classify
from recallradar_identify.query import InputType, ProductQuery
from recallradar_ingest.extract import codes, gtin
from recallradar_ingest.extract.dates import find_dates
from recallradar_ingest.extract.text import clean

# A standalone token that looks like a model number: letters and digits mixed ("IP-DUO60",
# "BGAAL9", "WL33006DMN"), at least four characters, and not a size ("20oz") or a year.
_MODEL_TOKEN = re.compile(
    r"(?<![\w-])(?=[\w-]*\d)(?=[\w-]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9\-./]{2,}[A-Za-z0-9](?![\w-])"
)
_YEAR = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
_LOT = re.compile(
    r"\blot\s*(?:#|no\.?|number|code)?\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-./]{1,30})", re.I
)


def _model_tokens(text: str) -> list[str]:
    found = []
    for token in _MODEL_TOKEN.findall(text):
        if codes.is_code_like(token, kind=codes.CodeKind.MODEL) and not _YEAR.fullmatch(token):
            found.append(token)
    return found


def _purchase_date(text: str) -> date | None:
    """A month/day date if given ("bought March 2024"), else a bare year ("2023") as Jan 1."""
    dates = find_dates(text)
    if dates:
        return dates[0].value.first_day()
    year = _YEAR.search(text)
    return date(int(year.group(1)), 1, 1) if year else None


def parse_text(raw: str) -> ProductQuery:
    text = clean(raw)
    labelled = codes.scan(text)
    upcs = [g.gtin14 for g in gtin.extract(text)]
    # Bare 12-13 digit numbers with a valid check digit are barcodes even without "UPC".
    for token in re.findall(r"(?<!\d)\d{12,14}(?!\d)", text):
        normalized = gtin.normalize(token)
        if normalized and normalized.gtin14 not in upcs:
            upcs.append(normalized.gtin14)
    barcode_digits = {u.lstrip("0") for u in upcs}
    models = [
        m
        for m in dict.fromkeys(labelled.models + _model_tokens(text))
        if m.lstrip("0") not in barcode_digits
    ]
    lots = list(dict.fromkeys(labelled.lots + _LOT.findall(text)))
    lot_set = set(lots)
    models = [m for m in models if m not in lot_set]

    purchase = _purchase_date(text)
    confidence = {"product_name": 0.6}
    if models:
        confidence["model_numbers"] = 0.9 if labelled.models else 0.6
    if upcs:
        confidence["upcs"] = 0.95
    if purchase:
        confidence["purchase_date"] = 0.5
    return ProductQuery(
        input_type=InputType.TEXT,
        raw=raw[:2000],
        product_name=text or None,
        model_numbers=models,
        upcs=upcs,
        lot_codes=lots,
        purchase_date=purchase,
        categories=sorted(classify(text), key=str),
        confidence=confidence,
    )
