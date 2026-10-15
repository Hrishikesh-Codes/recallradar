"""One entry point for every input method the API accepts."""

from typing import Literal

from recallradar_identify.barcode import Lookup, parse_barcode
from recallradar_identify.link import parse_link
from recallradar_identify.query import ProductQuery
from recallradar_identify.text import parse_text
from recallradar_identify.vin import Decoder, parse_vin

InputKind = Literal["text", "link", "barcode", "vin"]


def parse_input(
    kind: InputKind,
    value: str,
    lookup: Lookup | None = None,
    decode_vin: Decoder | None = None,
) -> ProductQuery:
    """Read typed text, a product link, barcode digits, or a VIN into a ProductQuery."""
    if kind == "text":
        return parse_text(value)
    if kind == "link":
        return parse_link(value)
    if kind == "vin":
        return parse_vin(value, decode_vin)
    return parse_barcode(value, lookup)
