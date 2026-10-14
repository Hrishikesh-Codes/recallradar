"""Scanned or typed barcodes. The browser decodes the image; this validates the digits and, for
food, looks up the product's name on Open Food Facts.

A barcode alone can match a recall directly when the recall lists UPCs. The name is only needed
for matching by name when it doesn't.

Open Food Facts (https://openfoodfacts.github.io/openfoodfacts-server/api/): open data (ODbL),
no key, a custom User-Agent required, 15 product reads per minute per IP. Lookups run on our
server and are cached, so users' IP addresses aren't shared with it.
"""

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from recallradar_core.categories import Category, classify
from recallradar_identify.query import InputType, ProductQuery
from recallradar_ingest.extract import gtin

OFF_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
USER_AGENT = "RecallRadar/0.1 (https://github.com/Hrishikesh-Codes/recallradar)"


@dataclass(frozen=True)
class BarcodeInfo:
    gtin14: str
    source: str
    product_name: str | None
    brand: str | None
    is_food: bool


Lookup = Callable[[str], BarcodeInfo | None]


def lookup_open_food_facts(client: httpx.Client, gtin14: str) -> BarcodeInfo | None:
    """Name and brand for a food barcode, or None if Open Food Facts doesn't know it."""
    code = gtin14.lstrip("0").zfill(13) if len(gtin14.lstrip("0")) <= 13 else gtin14
    response = client.get(
        OFF_URL.format(code=code),
        params={"fields": "product_name,brands,categories_tags"},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("status") != 1:
        return None
    product = body.get("product") or {}
    brand = (product.get("brands") or "").split(",")[0].strip() or None
    return BarcodeInfo(
        gtin14=gtin14,
        source="open_food_facts",
        product_name=(product.get("product_name") or "").strip() or None,
        brand=brand,
        is_food=True,
    )


def parse_barcode(code: str, lookup: Lookup | None = None) -> ProductQuery:
    normalized = gtin.normalize(code)
    if normalized is None:
        return ProductQuery(
            input_type=InputType.BARCODE,
            raw=code[:64],
            notes=[
                "That doesn't look like a valid barcode. Try scanning again or type the digits."
            ],
        )
    info = lookup(normalized.gtin14) if lookup else None
    name = info.product_name if info else None
    categories = classify(f"{info.brand or ''} {name or ''}") if info else set()
    if info and info.is_food:
        categories.add(Category.FOOD)
    notes = []
    if info is None:
        notes.append(
            "We checked this barcode against every recall that lists one. To also check by name, "
            "tell us what the product is."
        )
    return ProductQuery(
        input_type=InputType.BARCODE,
        raw=code[:64],
        upcs=[normalized.gtin14],
        product_name=name,
        brand=info.brand if info else None,
        categories=sorted(categories, key=str),
        confidence={"upcs": 1.0} | ({"product_name": 0.8} if name else {}),
        notes=notes,
    )
