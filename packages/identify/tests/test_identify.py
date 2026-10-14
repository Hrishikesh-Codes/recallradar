from datetime import date

import httpx
import pytest

from recallradar_core.categories import Category
from recallradar_identify import barcode, link, text
from recallradar_identify.query import InputType


class TestText:
    def test_brand_product_and_year(self) -> None:
        query = text.parse_text("Fisher-Price baby rocker, 2023")
        assert query.input_type is InputType.TEXT
        assert query.product_name == "Fisher-Price baby rocker, 2023"
        assert query.model_numbers == []
        assert query.purchase_date == date(2023, 1, 1)
        assert Category.INFANT_CHILD in query.categories

    @pytest.mark.parametrize(
        ("raw", "models"),
        [
            ("Instant Pot IP-DUO60", ["IP-DUO60"]),
            ("Energizer lantern model BGAAL9", ["BGAAL9"]),
            ("DR Power leaf vacuum WL33006DMN bought 2021", ["WL33006DMN"]),
            ("20oz tumbler 2-pack", []),  # sizes and pack counts aren't models
        ],
    )
    def test_model_numbers(self, raw: str, models: list[str]) -> None:
        assert text.parse_text(raw).model_numbers == models

    def test_bare_barcode_digits(self) -> None:
        query = text.parse_text("039800143341")
        assert query.upcs == ["00039800143341"]
        assert query.model_numbers == []

    def test_lot_code(self) -> None:
        query = text.parse_text("Todd's Seeds alfalfa sprouting seeds lot SAL2-24JB")
        assert query.lot_codes == ["SAL2-24JB"]
        assert "SAL2-24JB" not in query.model_numbers

    def test_purchase_month(self) -> None:
        assert text.parse_text("air fryer bought March 2024").purchase_date == date(2024, 3, 1)


class TestLink:
    # URL formats as retailers use them (we never fetch these pages).
    @pytest.mark.parametrize(
        ("url", "retailer", "name"),
        [
            (
                "https://www.amazon.com/Fisher-Price-Infant-Toddler-Rocker-Vibrations/dp/B07ABCDE12/ref=sr_1_3?keywords=rocker",
                "Amazon",
                "Fisher Price Infant Toddler Rocker Vibrations",
            ),
            (
                "https://www.walmart.com/ip/Mainstays-9-Drawer-Fabric-Dresser-Gray/123456789",
                "Walmart",
                "Mainstays 9 Drawer Fabric Dresser Gray",
            ),
            (
                "https://www.target.com/p/built-luum-light-up-tumbler-20oz/-/A-87654321",
                "Target",
                "built luum light up tumbler 20oz",
            ),
            (
                "https://www.homedepot.com/p/DR-Power-Equipment-Leaf-Vacuum-WL33006DMN/312345678",
                "The Home Depot",
                "DR Power Equipment Leaf Vacuum WL33006DMN",
            ),
            (
                "https://www.bestbuy.com/site/insignia-55-class-led-tv/6501234.p?skuId=6501234",
                "Best Buy",
                "insignia 55 class led tv",
            ),
        ],
    )
    def test_reads_the_product_name_from_the_url(self, url: str, retailer: str, name: str) -> None:
        query = link.parse_link(url)
        assert query.input_type is InputType.LINK
        assert query.retailer == retailer
        assert query.product_name == name

    def test_model_numbers_in_the_slug(self) -> None:
        query = link.parse_link(
            "https://www.homedepot.com/p/DR-Power-Equipment-Leaf-Vacuum-WL33006DMN/312345678"
        )
        assert query.model_numbers == ["WL33006DMN"]

    def test_short_links_are_not_followed(self) -> None:
        query = link.parse_link("https://a.co/d/abc1234")
        assert query.product_name is None
        assert "never" in query.notes[0]

    def test_slugless_amazon_link_asks_for_the_name(self) -> None:
        query = link.parse_link("https://www.amazon.com/dp/B07ABCDE12")
        assert query.product_name is None and query.retailer == "Amazon"
        assert query.notes

    def test_unknown_store_uses_the_longest_hyphenated_segment(self) -> None:
        query = link.parse_link(
            "https://shop.example.com/products/kids-wooden-activity-table-j04402"
        )
        assert query.product_name == "kids wooden activity table j04402"
        assert query.model_numbers == ["j04402"]


class TestBarcode:
    def test_invalid_digits(self) -> None:
        query = barcode.parse_barcode("123456789013")  # wrong check digit
        assert query.upcs == [] and query.notes

    def test_valid_code_without_a_name(self) -> None:
        query = barcode.parse_barcode("036000291452")
        assert query.upcs == ["00036000291452"]
        assert query.product_name is None and query.notes

    def test_food_lookup_fills_name_and_brand(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v2/product/3274080005003.json"
            assert "RecallRadar" in request.headers["User-Agent"]
            return httpx.Response(
                200,
                json={
                    "code": "3274080005003",
                    "status": 1,
                    "product": {"product_name": "isabelle", "brands": "Cristaline"},
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        query = barcode.parse_barcode(
            "3274080005003", lambda g: barcode.lookup_open_food_facts(client, g)
        )
        assert (query.product_name, query.brand) == ("isabelle", "Cristaline")
        assert Category.FOOD in query.categories

    def test_unknown_food_barcode(self) -> None:
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200, json={"status": 0, "status_verbose": "product not found"}
                )
            )
        )
        assert barcode.lookup_open_food_facts(client, "00036000291452") is None
