import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from recallradar_core.categories import Category
from recallradar_identify import barcode, link, text, vin
from recallradar_identify.parse import parse_input
from recallradar_identify.query import InputType, Vehicle


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


def test_link_slug_keeps_hyphenated_model_numbers() -> None:
    query = link.parse_link(
        "https://www.homedepot.com/p/Cuisinart-Propel-Four-Burner-3-in-1-Gas-Grill-CGG-6331/000000000"
    )
    assert "CGG-6331" in query.model_numbers
    # Word pairs like "in-1" or "Size-10" aren't models.
    assert not any(m.startswith(("IN-", "SIZE-")) for m in query.model_numbers)


class TestVin:
    FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "nhtsa"

    def decoder(self, name: str) -> vin.Decoder:
        body = json.loads((self.FIXTURES / name).read_text())
        client = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
        )
        return lambda value: vin.decode_vpic(client, value)

    def test_decodes_with_vpic(self) -> None:
        # vPIC's documented sample VIN (a 2003 Honda Accord).
        query = vin.parse_vin(
            " 1hgcm82633a004352 ", self.decoder("vpic_decode_1HGCM82633A004352.json")
        )
        assert query.input_type is InputType.VIN
        assert query.vehicle == Vehicle(make="HONDA", model="Accord", year=2003)
        assert query.product_name == "2003 HONDA Accord"
        assert Category.VEHICLE in query.categories
        assert query.notes == ["We read this VIN as a 2003 HONDA Accord."]

    def test_check_digit(self) -> None:
        assert vin.check_digit_ok("1HGCM82633A004352")
        assert not vin.check_digit_ok("1HGCM82633A004353")
        query = vin.parse_vin("1HGCM82633A004353", self.decoder("vpic_decode_bad_check_digit.json"))
        assert "check digit" in query.notes[0]

    @pytest.mark.parametrize("raw", ["1HGCM82633A00435", "1HGCM82633A00435O", "not a vin"])
    def test_rejects_malformed_vins(self, raw: str) -> None:
        query = vin.parse_vin(raw, lambda value: pytest.fail("must not decode"))
        assert query.vehicle is None
        assert "17 letters and numbers" in query.notes[0]


class TestLabel:
    def test_label_text_gives_name_and_codes(self) -> None:
        # The shape of OCR output from a product's rating sticker: short lines, labels, noise.
        text = "\n".join(
            [
                "DR POWER",
                "LEAF VACUUM",
                "| ~ ;",
                "MODEL: WL33006DMN",
                "SERIAL NO. 18A0042317",
                "MFD 03/2021",
                "120V 60Hz 6.5A",
            ]
        )
        query = parse_input("label", text)
        assert query.input_type is InputType.LABEL_PHOTO
        assert query.product_name == "DR POWER LEAF VACUUM"
        assert query.model_numbers == ["WL33006DMN"]
        assert query.search_text() == "DR POWER LEAF VACUUM"
        assert all(value <= 0.5 for value in query.confidence.values())
        assert "Fix anything we misread" in query.notes[-1]

    def test_barcode_digits_in_label_text_are_found(self) -> None:
        query = parse_input("label", "BUILT\nLUUM TUMBLER\n843461115513")
        assert query.upcs == ["00843461115513"]
