"""Extraction tests. Inputs are real strings from CPSC and openFDA records (source noted)."""

from datetime import date

import pytest

from recallradar_ingest.extract import codes, dates, gtin, labelers, restrictions
from recallradar_ingest.extract.codes import CodeKind, DateKind
from recallradar_ingest.extract.restrictions import RestrictionKind
from recallradar_ingest.extract.text import clean, code_key, sentences


class TestText:
    def test_clean_drops_lost_character_markers(self) -> None:
        # openFDA H-1398-2026
        assert clean("Salata Salad Kitchen Jalapen¿o Avocado  Dressing.") == (
            "Salata Salad Kitchen Jalapeno Avocado Dressing."
        )

    def test_code_key_ignores_case_and_punctuation(self) -> None:
        assert code_key("TS-1462-2.5-4") == code_key("ts 1462 25 4") == "TS1462254"


class TestGtin:
    @pytest.mark.parametrize(
        "code", ["036000291452", "0036000291452", "00036000291452", "96385074"]
    )
    def test_valid_codes_normalise_to_gtin14(self, code: str) -> None:
        result = gtin.normalize(code)
        assert result is not None and len(result.gtin14) == 14 and not result.inferred

    def test_upca_and_ean13_forms_compare_equal(self) -> None:
        a, b = gtin.normalize("036000291452"), gtin.normalize("0036000291452")
        assert a is not None and b is not None and a.gtin14 == b.gtin14

    def test_bad_check_digit_is_rejected(self) -> None:
        assert gtin.normalize("036000291453") is None

    def test_missing_check_digit_only_inferred_when_allowed(self) -> None:
        assert gtin.normalize("23114800000") is None
        inferred = gtin.normalize("23114800000", allow_inferred=True)
        assert inferred is not None and inferred.inferred and inferred.gtin14 == "00231148000007"

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("8 oz. wedges, UPC  8 54089 00108 9;", ["00854089001089"]),  # spaced
            ("UPC:7-37094-23027-2  Good & Gather", ["00737094230272"]),  # dashed
            (
                "6 x 9 oz. UPC: 716519067013 MNN, MCC 4 x 2 lbs. UPC: 716519020308 - SS",
                ["00716519067013", "00716519020308"],
            ),
            ("UDI-DI: (01)20888937009433. Lot Code: 550019722", ["20888937009433"]),  # GS1 AI
            # Flattened CPSC table: only check-digit-valid numbers count, item numbers don't.
            (
                "Item Number UPC 61896 792363618960 46319 193175340764",
                ["00792363618960", "00193175340764"],
            ),
        ],
    )
    def test_extracts_barcodes_written_many_ways(self, text: str, expected: list[str]) -> None:
        assert [g.gtin14 for g in gtin.extract(text)] == expected

    def test_numbers_without_a_barcode_label_are_ignored(self) -> None:
        assert gtin.extract("Serial numbers 999400100961 thru 999400100973") == []

    def test_label_does_not_bleed_into_lot_codes(self) -> None:
        found = gtin.extract("UPC 7539101240 || Lot code: 8005538-1, 8005540-1")
        assert [g.gtin14 for g in found] == ["00075391012406"]
        assert found[0].inferred


class TestDates:
    @pytest.mark.parametrize(
        ("text", "first", "last"),
        [
            ("Use By: 12/31/2029", date(2029, 12, 31), date(2029, 12, 31)),
            ("EXP: 8/17/21", date(2021, 8, 17), date(2021, 8, 17)),
            ("Best Before dates: 11.30.2016", date(2016, 11, 30), date(2016, 11, 30)),
            ("Use By Date Range 2016-03-31", date(2016, 3, 31), date(2016, 3, 31)),
            ("Best By June 10, 2026", date(2026, 6, 10), date(2026, 6, 10)),
            ("Expiration dates: 10JUL2025", date(2025, 7, 10), date(2025, 7, 10)),
            ("Exp. Date Jul-27", date(2027, 7, 1), date(2027, 7, 31)),
            ("Exp Date 10/2026", date(2026, 10, 1), date(2026, 10, 31)),
            ("Range: February 2023", date(2023, 2, 1), date(2023, 2, 28)),
        ],
    )
    def test_parses_formats_seen_in_notices(self, text: str, first: date, last: date) -> None:
        (match,) = dates.find_dates(text)
        assert (match.value.first_day(), match.value.last_day()) == (first, last)

    def test_impossible_dates_are_not_dates(self) -> None:
        assert dates.find_dates("ratio 13/45/2020 and 2/30/2021") == []

    @pytest.mark.parametrize(
        ("text", "window"),
        [
            # CPSC Retailers field
            (
                "Online at Amazon.com from September 2025 through April 2026 for between $11 "
                "to $15.",
                (date(2025, 9, 1), date(2026, 4, 30)),
            ),
            (
                "Home Depot stores sold the chandeliers from September 2013 through February 2017."
                " Home Depot stores nationwide sold the Collection from March 2015 to June 2016",
                (date(2013, 9, 1), date(2017, 2, 28)),
            ),
            (
                "Exclusively at Home Depot in June 2019 for $80.",
                (date(2019, 6, 1), date(2019, 6, 30)),
            ),
            ("Sold at hardware stores nationwide.", (None, None)),
        ],
    )
    def test_sold_window(self, text: str, window: tuple[date | None, date | None]) -> None:
        assert dates.sold_window(text) == window


class TestCodeScan:
    def test_lot_list_continues_past_expiry_dates(self) -> None:
        # openFDA D-0870-2026
        result = codes.scan(
            "Lot #: RL25G02, RL25G03, RL25G04, Exp. Date Jul-27; RL25H02, RL25H03, RL25H04, "
            "Exp. Date Aug-27; RL25K01"
        )
        assert result.lots == [
            "RL25G02", "RL25G03", "RL25G04", "RL25H02", "RL25H03", "RL25H04", "RL25K01",
        ]  # fmt: skip
        assert [d.kind for d in result.dates] == [DateKind.EXPIRATION, DateKind.EXPIRATION]

    def test_size_notes_in_parentheses_are_skipped(self) -> None:
        # openFDA H-1404-2026
        result = codes.scan(
            "Lot No: SAL2-24JB (1/4, 1/2, and 1 lb.); TS-1462-2.5-4 (2.5 lb. only); "
            "TS-1462-5-3 (5 lb. only) Use By: 12/31/2029"
        )
        assert result.lots == ["SAL2-24JB", "TS-1462-2.5-4", "TS-1462-5-3"]
        assert [(d.kind, d.text) for d in result.dates] == [(DateKind.USE_BY, "12/31/2029")]

    def test_model_and_sku_in_prose(self) -> None:
        result = codes.scan(
            "The affected Model No. is DGL0915. The SKU is 30732353. The Model No. and SKU "
            "appear on the price tag affixed to the product packaging."
        )
        assert result.models == ["DGL0915", "30732353"]

    def test_list_ends_when_prose_resumes(self) -> None:
        result = codes.scan(
            "The model number J04402 or J04411 can be found on a label on the underside of "
            "the 2020 activity table."
        )
        assert result.models == ["J04402", "J04411"]

    def test_flattened_table_codes_are_kept_separately(self) -> None:
        result = codes.scan(
            "The following model numbers are included in this recall. Brand Model Product "
            "Description UPC Code Troybilt 41AD252S766 41CDZ25C766 TB252S"
        )
        assert result.models == []
        assert result.table_codes == ["41AD252S766", "41CDZ25C766", "TB252S"]
        assert result.table_columns == {CodeKind.MODEL, CodeKind.GTIN}

    def test_device_model_udi_and_serials(self) -> None:
        # openFDA Z-3314-2026
        result = codes.scan(
            "1. Model number (REF): 781260 (1.5T); UDI-DI: 00884838095076; "
            "Serial Numbers: 5479, 5490, 8057, 8118"
        )
        assert result.models == ["781260"]
        assert result.serials == ["5479", "5490", "8057", "8118"]

    def test_ranges(self) -> None:
        result = codes.scan(
            "The recalled vehicles have date codes ranging from G2015 through L0515."
        )
        assert result.date_codes == ["G2015", "L0515"]
        assert [(r.kind, r.start, r.end) for r in result.ranges] == [
            (CodeKind.DATE_CODE, "G2015", "L0515")
        ]

    def test_date_label_covers_both_ends_of_a_range(self) -> None:
        result = codes.scan("Use By Date Range 2016-03-31 to 2016-10-31")
        assert [d.kind for d in result.dates] == [DateKind.USE_BY, DateKind.USE_BY]

    def test_purchase_order_and_case_numbers_are_not_identifiers(self) -> None:
        result = codes.scan(
            "Style #A8248, PO numbers: 8044696, 8044697 and Lot Numbers 050124, 052324 "
            "Case numbers WU-0857177"
        )
        assert result.models == ["A8248"]
        assert result.lots == ["050124", "052324"]

    @pytest.mark.parametrize(
        "token", ["20oz", "10ml", "2.5lb", "1/4", "16GB", "2700K", "2-pack", "9-Drawer"]
    )
    def test_sizes_and_units_are_not_codes(self, token: str) -> None:
        assert not codes.is_code_like(token, kind=CodeKind.MODEL)


class TestRestrictions:
    def test_fda_all_lots_means_every_unit(self) -> None:
        for text in ["All lot codes", "all lots within expiry", "None", "", "N/A"]:
            assert restrictions.fda_restrictions(text, codes.scan(text)) == [], text

    def test_fda_qualified_all_still_restricts(self) -> None:
        # openFDA H-1239-2026
        text = (
            "all product with an expiration date prior to Feb 9, 2028 (Best by Date Feb 09, 2028)"
        )
        found = restrictions.fda_restrictions(text, codes.scan(text))
        assert found and found[0].kind is RestrictionKind.DATE

    def test_fda_lot_list_restricts(self) -> None:
        text = "Lot: DJ25134, Exp 11/30/2028"
        kinds = {r.kind for r in restrictions.fda_restrictions(text, codes.scan(text))}
        assert kinds == {RestrictionKind.LOT, RestrictionKind.DATE}

    def test_cpsc_date_code_sentence_is_kept_as_the_detail(self) -> None:
        text = (
            "The recalled wands have a manufacturing date code printed in white on the bottom "
            "portion of the wand. Only magic wands with date codes between March 2023 and "
            "June 2023 are included."
        )
        found = restrictions.cpsc_restrictions(text, codes.scan(text))
        (date_code,) = [r for r in found if r.kind is RestrictionKind.DATE_CODE]
        assert date_code.detail.startswith("Only magic wands")

    def test_cpsc_where_the_serial_is_printed_is_not_a_restriction(self) -> None:
        # CPSC recall 10853 (Cuisinart CGG-6331): every unit is recalled.
        text = (
            "This recall includes the stainless-steel Cuisinart Propel+ Four Burner 3-in-1 Gas "
            "Grill. The model number CGG-6331 can be found on the label on the inside of the "
            "right-hand metal door, along with the serial number."
        )
        assert restrictions.cpsc_restrictions(text, codes.scan(text)) == []

    def test_cpsc_serial_restriction_uses_the_sentence_that_restricts(self) -> None:
        # CPSC recall 10311 (Anker A1263).
        text = (
            'The model number "A1263" and serial number "SN" are printed on the bottom. '
            "Only model number A1263 power banks sold in the U.S. with qualifying serial numbers "
            "are included in the recall."
        )
        found = restrictions.cpsc_restrictions(text, codes.scan(text))
        (serial,) = [r for r in found if r.kind is RestrictionKind.SERIAL]
        assert serial.detail.startswith("Only model number A1263")

    def test_cpsc_all_lots_included_is_not_a_restriction(self) -> None:
        text = (
            'The lot number is printed beneath the words "Made in China." '
            "All lot numbers are included in this recall."
        )
        found = restrictions.cpsc_restrictions(text, codes.scan(text))
        assert RestrictionKind.LOT not in {r.kind for r in found}

    def test_cpsc_plain_model_recall_is_unrestricted(self) -> None:
        text = (
            "This recall involves Agrish adult portable bed rails, model numbers BR-1 and BR-2. "
            "The model number is printed on a label on the rail."
        )
        assert restrictions.cpsc_restrictions(text, codes.scan(text)) == []

    def test_where_to_look(self) -> None:
        text = (
            "This recall involves leaf vacuums. The model number is printed on a white label on "
            "the left side of the unit. They were sold in green."
        )
        assert restrictions.where_to_look(text) == [
            "The model number is printed on a white label on the left side of the unit."
        ]


class TestLabelers:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # Real openFDA product descriptions (drug recall 91621, food and drug samples).
            (
                "Artificial Tears Lubricant Eye Drops, 1/2 fl oz (15 ml) bottle, Distributed by. "
                "EzriCare, LLC, Lakewood, NJ, NDC 79503-0101-15.",
                ["EzriCare"],
            ),
            ("Distributed by: Walgreen Co., 200 Wilmot Rd., Deerfield, IL 60015", ["Walgreen"]),
            ("DISTRIBUTED BY THE KROGER CO., CINCINNATI, OHIO 45202.", ["THE KROGER"]),
            (
                "Manufactured by: Wockhardt Limited, Mumbai, India. Distributed by: Wockhardt "
                "USA LLC, Parsippany, NJ",
                ["Wockhardt"],  # "USA" and "LLC" are dropped, so the two names are one
            ),
            ("Packed for: Mrs. Gerry's, Albert Lea, MN 56007", ["Mrs. Gerry's"]),
            ("Dist. by: Target Corporation, Minneapolis, MN 55403.", ["Target"]),
            ("Spicy Tuna Roll, 7.8oz, Keep refrigerated", []),
        ],
    )
    def test_labelers(self, text: str, expected: list[str]) -> None:
        assert labelers.labelers(text) == expected


class TestSentences:
    def test_abbreviations_do_not_end_sentences(self) -> None:
        text = (
            "The U.S. Department of Agriculture is issuing an alert. The products bear "
            "establishment number EST. NO. G-01 inside the mark. Dr. Smith said so."
        )
        assert sentences(text) == [
            "The U.S. Department of Agriculture is issuing an alert.",
            "The products bear establishment number EST. NO. G-01 inside the mark.",
            "Dr. Smith said so.",
        ]
