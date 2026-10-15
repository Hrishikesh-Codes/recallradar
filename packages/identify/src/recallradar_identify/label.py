"""Text read from a photo of a product label (OCR runs in the user's browser; the photo never
leaves their device). OCR text is noisy: the product name comes from the cleanest lines, and
model numbers, lot codes, dates, and barcodes from the same extractors as typed text.
"""

import re

from recallradar_identify.query import InputType, ProductQuery
from recallradar_identify.text import parse_text
from recallradar_ingest.extract.text import clean

_WORDY = re.compile(r"[A-Za-z]{3,}")
# Lines that label a code rather than name the product.
_FIELD = re.compile(
    r"^\s*(?:model|mod|serial|s/?n|lot|batch|mfd|mfg|manufactured|date|exp|best|use by|upc|"
    r"sku|item|part|p/?n|ref|cat|catalog|type|rating|input|output)\b",
    re.I,
)
_MAX_NAME = 160


def _name_lines(text: str) -> list[str]:
    """Lines that read like words (brand, product), not codes or OCR debris."""
    lines = []
    for raw in text.splitlines():
        line = clean(raw).strip(" .,:;|-_")
        if not line or _FIELD.match(line):
            continue
        letters = sum(c.isalpha() for c in line)
        if _WORDY.search(line) and letters >= 0.6 * len(line.replace(" ", "")):
            lines.append(line)
    return lines


def parse_label(text: str) -> ProductQuery:
    raw = text[:2000]
    query = parse_text(" \n".join(clean(line) for line in raw.splitlines() if line.strip()))
    name = " ".join(_name_lines(raw)[:3])[:_MAX_NAME].strip()
    query.input_type = InputType.LABEL_PHOTO
    query.raw = raw
    query.product_name = name or None
    query.confidence = {key: min(value, 0.5) for key, value in query.confidence.items()}
    query.notes.append("Read from your photo. Fix anything we misread before checking.")
    return query
