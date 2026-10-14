"""UPC / EAN / GTIN barcodes: validation, normalisation, and extraction from free text.

Everything is normalised to GTIN-14 (left-padded with zeros) so a scanned UPC-A, an EAN-13, and
a device UDI-DI compare equal when they encode the same item.

Recall text writes barcodes many ways: "8 54089 00108 9", "7-37094-23027-2", "0007203695132",
"(01)20888937009433", and sometimes without the check digit ("UPC 23114800000", 11 digits) or
without the number-system digit too (10 digits). Digit strings only count as barcodes near a
barcode label, or anywhere in text that mentions one if they pass the check digit.
"""

import re
from dataclasses import dataclass

VALID_LENGTHS = (8, 12, 13, 14)

_LABEL = re.compile(r"\b(?:upcs?|gtins?|eans?|udi(?:-di)?|bar\s?codes?|plu)\b", re.I)
_STOP = re.compile(
    r"\b(?:lots?|batch|exp|expiration|best|use by|sell by|serial|model|item|sku|ndc|ref|catalog|"
    r"manufactured|packed|case|po)\b|[.](?=\s+[A-Z])|\|\|",
    re.I,
)
# A run of digits that may contain single spaces or dashes ("0 44984 60023 8").
_DIGIT_RUN = re.compile(r"(?<![\w])(?:\(01\)\s?)?\d(?:[ \-]?\d)*(?![\w])")
_GS1_AI_01 = re.compile(r"\(01\)\s?(\d{14})\b")
_REGION_CHARS = 400


@dataclass(frozen=True, slots=True)
class Gtin:
    gtin14: str
    raw: str
    #: True when we added a missing check digit (and maybe a leading zero) ourselves.
    inferred: bool = False


def check_digit(body: str) -> int:
    """GS1 check digit for the digits before the check digit."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10


def is_valid(digits: str) -> bool:
    return (
        digits.isdigit()
        and len(digits) in VALID_LENGTHS
        and check_digit(digits[:-1]) == int(digits[-1])
        and int(digits) != 0
    )


def normalize(raw: str, *, allow_inferred: bool = False) -> Gtin | None:
    """GTIN-14 for a scanned or typed code, or None if it isn't a valid barcode."""
    digits = re.sub(r"\D", "", raw)
    if is_valid(digits):
        return Gtin(digits.zfill(14), raw)
    if allow_inferred and len(digits) in (10, 11) and int(digits) != 0:
        body = digits.zfill(11)  # UPC-A without its check digit (and maybe number system)
        return Gtin((body + str(check_digit(body))).zfill(14), raw, inferred=True)
    return None


def _split_run(run: str, *, allow_inferred: bool) -> list[Gtin]:
    """A digit run may hold one spaced-out barcode or several barcodes in a row."""
    parts = re.split(r"[ \-]", run.removeprefix("(01)").strip())
    found: list[Gtin] = []
    i = 0
    while i < len(parts):
        best: tuple[int, Gtin] | None = None
        for j in range(i + 1, min(i + 6, len(parts)) + 1):
            joined = "".join(parts[i:j])
            if len(joined) > 14:
                break
            if is_valid(joined):
                best = (j, Gtin(joined.zfill(14), " ".join(parts[i:j])))
        if best is None and allow_inferred and len(parts[i]) in (10, 11):
            inferred = normalize(parts[i], allow_inferred=True)
            if inferred is not None:
                best = (i + 1, inferred)
        if best is None:
            i += 1
            continue
        i, gtin = best
        found.append(gtin)
    return found


def extract(text: str) -> list[Gtin]:
    """Barcodes in recall text, deduplicated by GTIN-14, in order of appearance."""
    found: dict[str, Gtin] = {}

    def add(gtins: list[Gtin]) -> None:
        for gtin in gtins:
            existing = found.get(gtin.gtin14)
            if existing is None or (existing.inferred and not gtin.inferred):
                found[gtin.gtin14] = gtin

    for match in _GS1_AI_01.finditer(text):
        if is_valid(match.group(1)):
            add([Gtin(match.group(1), match.group(0))])

    # Near a label: also accept codes missing their check digit.
    for label in _LABEL.finditer(text):
        region = text[label.end() : label.end() + _REGION_CHARS]
        stop = _STOP.search(region)
        region = region[: stop.start()] if stop else region
        for run in _DIGIT_RUN.finditer(region):
            add(_split_run(run.group(0), allow_inferred=True))

    # Anywhere in text that mentions barcodes (flattened tables): only check-digit-valid codes.
    if _LABEL.search(text):
        for run in _DIGIT_RUN.finditer(text):
            add(_split_run(run.group(0), allow_inferred=False))

    return list(found.values())
