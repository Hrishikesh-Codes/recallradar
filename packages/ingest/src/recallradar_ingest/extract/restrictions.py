"""Does a recall cover every unit of a product, or only some lots, dates, or serial numbers?

This decides between "Recalled" and "Check your unit" (SPEC §6.4): an identifier match on a
recall restricted to certain units must not be reported as a confirmed recall. When in doubt we
say "restricted", because the cost of that mistake is a user checking a label, not a missed recall.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from recallradar_ingest.extract.codes import CodeKind, CodeScan
from recallradar_ingest.extract.text import clean, sentences, truncate


class RestrictionKind(StrEnum):
    LOT = "lot"
    SERIAL = "serial"
    DATE_CODE = "date_code"
    DATE = "date"  # best-by, use-by, expiration, packed, manufactured windows
    MODEL_YEAR = "model_year"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Restriction:
    kind: RestrictionKind
    detail: str


_CPSC_PATTERNS: list[tuple[RestrictionKind, re.Pattern[str]]] = [
    (RestrictionKind.SERIAL, re.compile(r"\bserial\s+(?:numbers?|nos?\.?|#|range)", re.I)),
    (
        RestrictionKind.DATE_CODE,
        re.compile(r"\b(?:date|production|manufactur\w*)\s+codes?\b", re.I),
    ),
    (RestrictionKind.LOT, re.compile(r"\b(?:lot|batch)\s+(?:numbers?|nos?\.?|#|codes?)\b", re.I)),
    (
        RestrictionKind.DATE,
        re.compile(
            r"\b(?:manufactured|made|produced|built|assembled)\s+(?:between|from|in|during|before|"
            r"after|prior\s+to|on)\b[^.]{0,60}\b(?:19|20)\d{2}\b",
            re.I,
        ),
    ),
    (RestrictionKind.MODEL_YEAR, re.compile(r"\bmodel\s+years?\s+(?:19|20)\d{2}\b", re.I)),
    (
        RestrictionKind.OTHER,
        re.compile(
            r"\bonly\s+(?:those\s+)?(?:units|products|models|items|ones|\w+s)\b[^.]{0,80}\b"
            r"(?:with|having|that\s+have|manufactured|made|sold|bearing|marked)\b",
            re.I,
        ),
    ),
]
# "All lot numbers are included in this recall." says the opposite of a restriction.
_ALL_INCLUDED = re.compile(
    r"\ball\s+(?:lot|batch|serial|date|production)\s+(?:numbers?|codes?)\s+(?:are|were)\s+"
    r"(?:included|affected|recalled|part\s+of)",
    re.I,
)

_LOCATION = re.compile(
    r"\b(?:printed|located|found|stamped|molded|moulded|engraved|embossed|appears?|listed|marked|"
    r"labeled|labelled|sewn|etched|imprinted)\b[^.]{0,80}\b(?:on|in|inside|under|beneath|near|"
    r"along)\b",
    re.I,
)

# openFDA code_info meaning "every unit": "All lot codes", "all lots within expiry", "None".
_FDA_ALL_UNITS = re.compile(
    r"^\s*(?:all\s+(?:lots?|lot\s+(?:codes?|numbers?)|codes?|product\s+codes?|products?|units|"
    r"batches|sizes|serial\s+numbers?|expiration\s+dates?|code\s+dates?)"
    r"(?:\s*(?:and|&|,)\s*(?:all\s+)?(?:lots?|codes?|sizes|code\s+dates?|expiration\s+dates?))*"
    r"(?:\s+(?:within|in)\s+(?:expiry|date|code))?(?:\s+(?:are|were)\s+(?:included|affected))?"
    r"|none|n/?a|not\s+applicable|-+)?\s*\.?\s*$",
    re.I,
)
_DETAIL_CHARS = 400


def where_to_look(text: str, limit: int = 3) -> list[str]:
    """Sentences telling the reader where an identifier is on the product."""
    return [truncate(s, 300) for s in sentences(text) if _LOCATION.search(s)][:limit]


def _kinds_from_scan(codes: CodeScan) -> list[RestrictionKind]:
    kinds: list[RestrictionKind] = []
    if codes.lots or CodeKind.LOT in codes.table_columns:
        kinds.append(RestrictionKind.LOT)
    if codes.serials or CodeKind.SERIAL in codes.table_columns:
        kinds.append(RestrictionKind.SERIAL)
    if codes.date_codes or CodeKind.DATE_CODE in codes.table_columns:
        kinds.append(RestrictionKind.DATE_CODE)
    if codes.dates:
        kinds.append(RestrictionKind.DATE)
    return kinds


def cpsc_restrictions(description: str, codes: CodeScan) -> list[Restriction]:
    """Unit restrictions stated in a CPSC recall description."""
    found: dict[RestrictionKind, Restriction] = {}
    for sentence in sentences(description):
        if _ALL_INCLUDED.search(sentence):
            continue
        for kind, pattern in _CPSC_PATTERNS:
            if kind not in found and pattern.search(sentence):
                found[kind] = Restriction(kind, truncate(sentence, 300))
    for kind in _kinds_from_scan(codes):
        if kind not in found and kind is not RestrictionKind.DATE:
            found[kind] = Restriction(
                kind, f"Only some {kind.value.replace('_', ' ')}s are covered."
            )
    return list(found.values())


def fda_restrictions(code_info: str, codes: CodeScan) -> list[Restriction]:
    """Unit restrictions in an openFDA `code_info` field. Anything but "all units" restricts."""
    text = clean(code_info)
    if _FDA_ALL_UNITS.match(text):
        return []
    detail = truncate(text, _DETAIL_CHARS)
    kinds = _kinds_from_scan(codes) or [RestrictionKind.OTHER]
    return [Restriction(kind, detail) for kind in kinds]
