"""Find and parse the date formats that appear in recall notices.

Formats seen in real CPSC and openFDA text: 12/31/2029, 8/17/21, 11.30.2016, 2016-03-31,
June 10, 2026, Feb 19 2025, 10JUL2025, Jul-27, 10/2026, February 2023. US month-first order.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {
    name: index
    for index in range(1, 13)
    for name in (calendar.month_name[index].lower(), calendar.month_abbr[index].lower())
}
_MONTHS["sept"] = 9
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)


@dataclass(frozen=True, slots=True)
class PartialDate:
    """A date known to day, month, or year precision."""

    year: int
    month: int | None = None
    day: int | None = None

    def first_day(self) -> date:
        return date(self.year, self.month or 1, self.day or 1)

    def last_day(self) -> date:
        if self.day is not None and self.month is not None:
            return date(self.year, self.month, self.day)
        month = self.month or 12
        return date(self.year, month, calendar.monthrange(self.year, month)[1])


@dataclass(frozen=True, slots=True)
class DateMatch:
    start: int
    end: int
    text: str
    value: PartialDate


def _year(raw: str) -> int:
    value = int(raw)
    return 2000 + value if value < 100 else value


def _valid(year: int, month: int | None, day: int | None) -> bool:
    if not 1950 <= year <= 2100 or (month is not None and not 1 <= month <= 12):
        return False
    if day is None:
        return True
    return month is not None and 1 <= day <= calendar.monthrange(year, month)[1]


def _month(name: str) -> int:
    key = name.lower().rstrip(".")
    return _MONTHS.get(key) or _MONTHS[key[:3]]


# Ordered most specific first; each yields (year, month, day).
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4}|\d{2})\b"), "mdy"),
    (re.compile(rf"\b(\d{{1,2}})[\s-]?({_MONTH})[\s-]?(\d{{4}}|\d{{2}})\b", re.I), "d_mon_y"),
    (
        re.compile(rf"\b({_MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I),
        "mon_d_y",
    ),
    (re.compile(rf"\b({_MONTH})\.?,?\s+(\d{{4}})\b", re.I), "mon_y"),
    (re.compile(rf"\b({_MONTH})[-\s](\d{{2}})\b(?![/\d])", re.I), "mon_yy"),
    (re.compile(r"\b(\d{1,2})/(\d{4})\b"), "m_y"),
]


def _parse(kind: str, groups: tuple[str, ...]) -> PartialDate | None:
    year: int
    month: int | None
    day: int | None
    match kind:
        case "ymd":
            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
        case "mdy":
            year, month, day = _year(groups[2]), int(groups[0]), int(groups[1])
        case "d_mon_y":
            year, month, day = _year(groups[2]), _month(groups[1]), int(groups[0])
        case "mon_d_y":
            year, month, day = int(groups[2]), _month(groups[0]), int(groups[1])
        case "mon_y":
            year, month, day = int(groups[1]), _month(groups[0]), None
        case "mon_yy":
            year, month, day = _year(groups[1]), _month(groups[0]), None
        case "m_y":
            year, month, day = int(groups[1]), int(groups[0]), None
        case _:  # pragma: no cover - patterns and kinds are defined together above
            raise ValueError(kind)
    return PartialDate(year, month, day) if _valid(year, month, day) else None


def find_dates(text: str) -> list[DateMatch]:
    """All non-overlapping dates in `text`, in order of appearance."""
    found: list[DateMatch] = []
    taken: list[tuple[int, int]] = []
    for pattern, kind in _PATTERNS:
        for match in pattern.finditer(text):
            if any(match.start() < end and start < match.end() for start, end in taken):
                continue
            value = _parse(kind, match.groups())
            if value is None:
                continue
            taken.append((match.start(), match.end()))
            found.append(DateMatch(match.start(), match.end(), match.group(0), value))
    return sorted(found, key=lambda m: m.start)


_RANGE_LINK = re.compile(r"^\s*(?:through|thru|to|until|till|and|-|\u2013)\s*$", re.I)
_RANGE_LEAD = re.compile(r"(?:from|between|beginning(?: in)?|starting(?: in)?)\s*$", re.I)
_SINGLE_LEAD = re.compile(r"(?:\bin|\bduring|\bsince|\bbeginning in|\bstarting in)\s*$", re.I)


def sold_window(text: str) -> tuple[date | None, date | None]:
    """The overall sold-from/to window in CPSC retailer text, e.g.
    "... nationwide from November 2014 through February 2017 for about $60."

    Several windows (one per product line) are merged into the widest span.
    """
    starts: list[date] = []
    ends: list[date] = []
    dates = find_dates(text)
    for index, current in enumerate(dates):
        before = text[max(0, current.start - 25) : current.start]
        following = dates[index + 1] if index + 1 < len(dates) else None
        if (
            following is not None
            and _RANGE_LEAD.search(before)
            and _RANGE_LINK.match(text[current.end : following.start])
        ):
            starts.append(current.value.first_day())
            ends.append(following.value.last_day())
        elif _SINGLE_LEAD.search(before) and not (
            index > 0 and _RANGE_LINK.match(text[dates[index - 1].end : current.start])
        ):
            starts.append(current.value.first_day())
            ends.append(current.value.last_day())
    return (min(starts) if starts else None, max(ends) if ends else None)
