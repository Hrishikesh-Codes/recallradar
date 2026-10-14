"""Identifier extraction: model/item numbers, lot codes, serial numbers, date codes, and dates.

A small state machine over tokens. Each label ("Model No.", "Lot #:", "Serial Numbers", "Exp.")
sets what the following values are, and values keep that kind until the list visibly ends (a
sentence ends, or several ordinary words appear). A date label only claims the next date, so
"Lot #: RL25G02, RL25G03, Exp. Date Jul-27; RL25H02" keeps RL25H02 as a lot.

Flattened tables ("Brand Model Product Description UPC Code Troybilt 41AD252S766 ...") are
detected by two or more labels in a short header run; their values are kept separately as weaker
`table_codes`, since columns can't be told apart once the table is flattened.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from recallradar_ingest.extract.dates import PartialDate, find_dates


class CodeKind(StrEnum):
    MODEL = "model"  # model, item, SKU, style, part, catalog, REF numbers
    LOT = "lot"  # lot and batch codes
    SERIAL = "serial"
    DATE_CODE = "date_code"
    GTIN = "gtin"  # values handled by the barcode extractor
    IGNORE = "ignore"  # PO numbers, case numbers, NDC


class DateKind(StrEnum):
    EXPIRATION = "expiration"
    USE_BY = "use_by"
    BEST_BY = "best_by"
    SELL_BY = "sell_by"
    PACKED = "packed"
    MANUFACTURED = "manufactured"


_NUM = r"(?:\s*(?:numbers?|nos?\.?|#|no\b))?"
_ID_LABELS: list[tuple[CodeKind, str]] = [
    (CodeKind.SERIAL, rf"serial(?:/lot)?{_NUM}(?:\s+ranges?)?|s/n"),
    (
        CodeKind.DATE_CODE,
        r"(?:manufactur(?:ing|e)\s+)?date\s+codes?|production\s+codes?|julian\s+codes?",
    ),
    (CodeKind.LOT, rf"batch(?:es)?(?:/lots?)?{_NUM}(?:\s+codes?)?|lots?{_NUM}(?:\s+codes?)?"),
    (
        CodeKind.MODEL,
        rf"model(?:s)?{_NUM}|item(?:s)?{_NUM}|skus?{_NUM}|styles?{_NUM}|part{_NUM}"
        rf"|catalog(?:ue)?{_NUM}|cat\.?\s*(?:no\.?|#)|ref\b|material{_NUM}|article{_NUM}"
        rf"|product\s+(?:codes?|numbers?|nos?\.?)|list{_NUM}|reorder{_NUM}",
    ),
    (
        CodeKind.GTIN,
        r"upcs?(?:/plu)?(?:\s*(?:codes?|numbers?|#))?|gtins?|udi(?:-di)?(?:\s+codes?)?|eans?|plu",
    ),
    (CodeKind.IGNORE, rf"po{_NUM}|purchase\s+orders?|case{_NUM}(?:\s+codes?)?|ndcs?{_NUM}"),
]
_DATE_LABELS: list[tuple[DateKind, str]] = [
    (DateKind.EXPIRATION, r"exp(?:iration|iry)?\.?(?:\s+dates?)?(?:\s+range)?|bud"),
    (DateKind.USE_BY, r"use[\s-]+by(?:\s+dates?)?"),
    (DateKind.BEST_BY, r"best[\s-]+(?:by|before|if\s+used\s+by|if\s+enjoyed\s+by)(?:\s+dates?)?"),
    (DateKind.SELL_BY, r"sell[\s-]+by(?:\s+dates?)?"),
    (DateKind.PACKED, r"packed\s+on(?:\s+dates?)?|pack\s+dates?"),
    (DateKind.MANUFACTURED, r"(?:manufactur(?:ed|ing)|mfg\.?|production)\s+dates?"),
]

# Labels must end at a word boundary: "po" (purchase order) must not match inside "Pool".
_LABEL_RE = re.compile(
    "|".join(
        [rf"(?P<id_{kind.value}>\b(?:{pattern})(?![A-Za-z]))" for kind, pattern in _ID_LABELS]
        + [rf"(?P<date_{kind.value}>\b(?:{pattern})(?![A-Za-z]))" for kind, pattern in _DATE_LABELS]
    ),
    re.I,
)
_ID_TOKEN = re.compile(r"#?[A-Za-z0-9][A-Za-z0-9\-./*]*[A-Za-z0-9*]|#?[0-9]")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\u2019]*")
_SENTENCE_END = re.compile(r"\.(?=\s+[A-Z\"(]|\s*$)|\|\|")
_PAREN = re.compile(r"\([^()]{0,80}\)")
_RANGE = re.compile(r"\s*(?:\b(?:through|thru|to)\b|-|\u2013)\s*", re.I)

# Words that can sit inside a list of codes without ending it.
_CONNECTIVES = frozenset(
    [
        "and",
        "or",
        "the",
        "following",
        "are",
        "is",
        "include",
        "includes",
        "including",
        "included",
        "numbers",
        "number",
        "no",
        "nos",
        "codes",
        "code",
        "only",
        "with",
        "of",
        "in",
        "recalled",
        "affected",
        "these",
        "this",
        "recall",
        "range",
        "ranging",
        "from",
        "between",
        "beginning",
        "starting",
        "ending",
        "begin",
        "start",
        "end",
        "listed",
        "below",
        "above",
        "as",
    ]
)
# Sizes like "20oz" or "1500W". Only short numbers: "358015W" is a model number, not 358 kW.
_UNIT = re.compile(
    r"^\d{1,4}(?:\.\d+)?(?:oz|fl|ml|l|lb|lbs|g|kg|mg|mcg|in|inch|cm|mm|ft|v|w|mah|ah|ct|pk|pc|pcs|"
    r"qt|gal|k|hz|gb|tb|mb|x|pack|count)$",
    re.I,
)
# A code that clearly looks like an identifier: letters and digits, five or more characters.
_STRONG_CODE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9\-./]{5,}$")
_LOOKAHEAD_TOKENS = 8
_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_MAX_WORDS_IN_LIST = 2


@dataclass(frozen=True, slots=True)
class CodeRange:
    kind: CodeKind | None  # None inside a flattened table
    start: str
    end: str


@dataclass(frozen=True, slots=True)
class LabeledDate:
    kind: DateKind | None
    value: PartialDate
    text: str


@dataclass
class CodeScan:
    models: list[str] = field(default_factory=list)
    lots: list[str] = field(default_factory=list)
    serials: list[str] = field(default_factory=list)
    date_codes: list[str] = field(default_factory=list)
    table_codes: list[str] = field(default_factory=list)
    ranges: list[CodeRange] = field(default_factory=list)
    dates: list[LabeledDate] = field(default_factory=list)
    #: Label kinds that formed a flattened table header, e.g. {"model", "serial"}.
    table_columns: set[CodeKind] = field(default_factory=set)

    def bucket(self, kind: CodeKind | None) -> list[str] | None:
        return {
            CodeKind.MODEL: self.models,
            CodeKind.LOT: self.lots,
            CodeKind.SERIAL: self.serials,
            CodeKind.DATE_CODE: self.date_codes,
            None: self.table_codes,
        }.get(kind)


def is_code_like(token: str, *, kind: CodeKind | None) -> bool:
    """Could this token be an identifier (rather than a size, price, word, or year)?"""
    token = token.lstrip("#")
    if not any(c.isdigit() for c in token) or _UNIT.match(token):
        return False
    if re.fullmatch(r"\d+/\d+", token):  # fractions like 1/4
        return False
    if re.fullmatch(r"\d{1,3}-[A-Za-z]+", token):  # counts like "2-pack", "9-Drawer"
        return False
    if kind is None and (_YEAR.match(token) or len(token) < 4 or token.isdigit()):
        # Table cells: only mixed letter+digit codes; bare numbers are prices, sizes, counts.
        return False
    return len(token) >= (3 if kind is CodeKind.MODEL else 2)


@dataclass
class _Token:
    kind: str  # "id_label", "date_label", "date", "code", "word", "sep", "end", "range"
    text: str
    code_kind: CodeKind | None = None
    date_kind: DateKind | None = None
    date: PartialDate | None = None


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    dates = {m.start: m for m in find_dates(text)}
    labels = {m.start(): m for m in _LABEL_RE.finditer(text)}
    i = 0
    while i < len(text):
        char = text[i]
        if char.isspace():
            i += 1
            continue
        if i in labels:
            match = labels[i]
            group = next(name for name, value in match.groupdict().items() if value is not None)
            family, value = group.split("_", 1)
            if family == "id":
                tokens.append(_Token("id_label", match.group(0), code_kind=CodeKind(value)))
            else:
                tokens.append(_Token("date_label", match.group(0), date_kind=DateKind(value)))
            i = match.end()
            continue
        if i in dates:
            tokens.append(_Token("date", dates[i].text, date=dates[i].value))
            i = dates[i].end
            continue
        if char == "(" and (paren := _PAREN.match(text, i)):
            i = paren.end()  # size notes like "(1/4, 1/2, and 1 lb.)"
            continue
        if (end := _SENTENCE_END.match(text, i)) is not None:
            tokens.append(_Token("end", end.group(0)))
            i = end.end()
            continue
        if (rng := _RANGE.match(text, i)) is not None and rng.group(0).strip() and tokens:
            tokens.append(_Token("range", rng.group(0)))
            i = rng.end()
            continue
        code = _ID_TOKEN.match(text, i)
        if code is not None and any(c.isdigit() for c in code.group(0)):
            value = code.group(0).rstrip(".")
            tokens.append(_Token("code", value))
            i += len(value)
            continue
        if (word := _WORD.match(text, i)) is not None:
            tokens.append(_Token("word", word.group(0)))
            i = word.end()
            continue
        tokens.append(_Token("sep", char))
        i += 1
    return tokens


def _is_table_header(tokens: list[_Token], start: int) -> set[CodeKind]:
    """Kinds in a header like "Model Number Description UPC Code" starting at tokens[start]."""
    kinds: set[CodeKind] = set()
    gap = 0
    for token in tokens[start:]:
        if token.code_kind is not None:
            kinds.add(token.code_kind)
            gap = 0
        elif token.kind == "date_label":
            gap = 0
        elif token.kind == "word" and gap < 4:
            gap += 1
        else:
            break
    return kinds if len(kinds) >= 2 else set()


def _codes_follow(tokens: list[_Token], i: int) -> bool:
    """Row labels inside a one-column table ("Walk Behind Leaf Vacuum WL33006DMN ...") don't
    end the list: identifier-looking codes appear again within a few tokens."""
    for token in tokens[i + 1 : i + 1 + _LOOKAHEAD_TOKENS]:
        if token.kind == "end":
            return False
        if token.kind == "code" and _STRONG_CODE.match(token.text.lstrip("#")):
            return True
    return False


class _Scanner:
    """Walks the tokens once, tracking which kind of code the next values belong to."""

    def __init__(self, tokens: list[_Token]) -> None:
        self.tokens = tokens
        self.result = CodeScan()
        self.current: CodeKind | None = None
        self.in_table = False
        self.pending_date: DateKind | None = None
        self.words_in_a_row = 0

    def peek(self, i: int, *kinds: str) -> bool:
        """Do tokens i+1, i+2, ... have these kinds?"""
        ahead = self.tokens[i + 1 : i + 1 + len(kinds)]
        return len(ahead) == len(kinds) and all(
            t.kind == k for t, k in zip(ahead, kinds, strict=True)
        )

    def run(self) -> CodeScan:
        i = 0
        while i < len(self.tokens):
            i = self.step(i)
        for name in ("models", "lots", "serials", "date_codes", "table_codes"):
            values: list[str] = getattr(self.result, name)
            setattr(self.result, name, list(dict.fromkeys(values)))
        return self.result

    def step(self, i: int) -> int:
        """Handle tokens[i]; return the index of the next token to handle."""
        token = self.tokens[i]
        if token.kind in ("id_label", "date_label") and not self.in_table:
            header = _is_table_header(self.tokens, i)
            if header:
                self.result.table_columns |= header
                self.in_table, self.current, self.pending_date = True, None, None
                while i < len(self.tokens) and self.tokens[i].kind in (
                    "id_label",
                    "date_label",
                    "word",
                ):
                    i += 1
                return i
        if token.code_kind is not None and not self.in_table:
            self.current, self.pending_date, self.words_in_a_row = token.code_kind, None, 0
        elif token.date_kind is not None:
            self.pending_date, self.words_in_a_row = token.date_kind, 0
        elif token.date is not None:
            self.result.dates.append(LabeledDate(self.pending_date, token.date, token.text))
            # "Use By Date Range 2016-03-31 to 2016-10-31": the label covers both ends.
            if not self.peek(i, "range", "date"):
                self.pending_date = None
        elif token.kind == "code":
            return self.code(i, token)
        elif token.kind == "word":
            self.word(i, token)
        elif token.kind == "end":
            self.current, self.pending_date, self.in_table, self.words_in_a_row = (
                None,
                None,
                False,
                0,
            )
        return i + 1

    def code(self, i: int, token: _Token) -> int:
        self.words_in_a_row = 0
        kind = None if self.in_table else self.current
        bucket = self.result.bucket(kind)
        if bucket is None or not (self.in_table or self.current is not None):
            return i + 1
        if not is_code_like(token.text, kind=kind):
            return i + 1
        value = token.text.lstrip("#")
        # "G2015 through L0515", "1100N10000 - 1100N12173"
        if self.peek(i, "range", "code"):
            end_value = self.tokens[i + 2].text.lstrip("#")
            if is_code_like(end_value, kind=kind):
                self.result.ranges.append(CodeRange(kind, value, end_value))
                bucket.extend([value, end_value])
                return i + 3
        bucket.append(value)
        return i + 1

    def word(self, i: int, token: _Token) -> None:
        if token.text.lower() in _CONNECTIVES:
            return
        self.words_in_a_row += 1
        if (
            self.words_in_a_row > _MAX_WORDS_IN_LIST
            and not self.in_table
            and not _codes_follow(self.tokens, i)
        ):
            self.current = None


def scan(text: str) -> CodeScan:
    """Model numbers, lots, serials, date codes, ranges, and labelled dates in `text`."""
    return _Scanner(_tokenize(text)).run()
