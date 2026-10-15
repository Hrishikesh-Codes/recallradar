"""VINs: validate, then decode with NHTSA's vPIC service into make, model, and model year.

vPIC (https://vpic.nhtsa.dot.gov/api/) is free and needs no key. The check digit (9th
character) is mandatory for North American VINs only, so a failed check is a warning, not a
rejection. VINs are decoded and then forgotten: a check never stores them.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from recallradar_core.categories import Category
from recallradar_identify.query import InputType, ProductQuery, Vehicle

VPIC_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}"
_VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
# Check-digit transliteration: A and J count 1, B, K and S count 2, and so on.
_GROUPS = ("", "AJ", "BKS", "CLT", "DMU", "ENV", "FW", "GPX", "HY", "RZ")
_VALUES = {char: value for value, chars in enumerate(_GROUPS) for char in chars}
_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)


@dataclass(frozen=True)
class Decoded:
    make: str | None
    model: str | None
    year: int | None
    error: str | None


Decoder = Callable[[str], Decoded | None]


def normalize(raw: str) -> str | None:
    vin = re.sub(r"[\s-]", "", raw).upper()
    return vin if _VIN.match(vin) else None


def check_digit_ok(vin: str) -> bool:
    total = 0
    for char, weight in zip(vin, _WEIGHTS, strict=True):
        total += (int(char) if char.isdigit() else _VALUES[char]) * weight
    expected = total % 11
    return vin[8] == ("X" if expected == 10 else str(expected))


def decode_vpic(client: httpx.Client, vin: str) -> Decoded | None:
    response = client.get(VPIC_URL.format(vin=vin), params={"format": "json"}, timeout=15)
    response.raise_for_status()
    results = response.json().get("Results") or []
    if not results:
        return None
    row = results[0]
    year = str(row.get("ModelYear") or "").strip()
    return Decoded(
        make=(row.get("Make") or "").strip() or None,
        model=(row.get("Model") or "").strip() or None,
        year=int(year) if year.isdigit() else None,
        error=None if str(row.get("ErrorCode", "0")).strip() == "0" else row.get("ErrorText"),
    )


def parse_vin(raw: str, decode: Decoder | None) -> ProductQuery:
    vin = normalize(raw)
    if vin is None:
        return ProductQuery(
            input_type=InputType.VIN,
            raw=raw[:64],
            notes=[
                "A VIN is 17 letters and numbers (never I, O, or Q). It's on the lower left of "
                "the windshield and on your registration."
            ],
        )
    notes = []
    if not check_digit_ok(vin):
        notes.append("This VIN's check digit doesn't add up; check it for typos.")
    decoded = decode(vin) if decode else None
    if decoded is None or decoded.make is None:
        notes.append("We couldn't decode this VIN. Check it, or type the year, make, and model.")
        return ProductQuery(input_type=InputType.VIN, raw=vin, notes=notes)
    name = " ".join(str(p) for p in (decoded.year, decoded.make, decoded.model) if p)
    notes.append(f"We read this VIN as a {name}.")
    return ProductQuery(
        input_type=InputType.VIN,
        raw=vin,
        product_name=name,
        brand=decoded.make,
        categories=[Category.VEHICLE],
        vehicle=Vehicle(make=decoded.make, model=decoded.model, year=decoded.year),
        confidence={"vehicle": 1.0 if not notes[:-1] else 0.7},
        notes=notes,
    )
