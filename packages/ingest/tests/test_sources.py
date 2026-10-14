"""Parser and fetcher tests against real API responses saved in tests/fixtures."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from recallradar_core.categories import Category
from recallradar_core.enums import NoticeType, RecallSource, RecallStatus, RemedyType
from recallradar_ingest.extract.restrictions import RestrictionKind
from recallradar_ingest.sources import cpsc, openfda

FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="module")
def cpsc_by_id() -> dict[int, dict[str, Any]]:
    return {record["RecallID"]: record for record in load("cpsc/recalls_by_id.json")}


class TestCpscParse:
    def test_every_fixture_record_parses(self) -> None:
        for name in ("cpsc/recalls_by_id.json", "cpsc/last_publish_window.json"):
            for raw in load(name):
                recall = cpsc.parse(raw)
                assert recall.title and recall.official_url and len(recall.products) == 1

    def test_core_fields(self, cpsc_by_id: dict[int, dict[str, Any]]) -> None:
        recall = cpsc.parse(cpsc_by_id[10557])
        assert recall.source is RecallSource.CPSC
        assert (recall.source_recall_id, recall.reference) == ("10557", "26183")
        assert recall.firm == "Energizer"
        assert recall.remedy_type is RemedyType.REFUND
        assert recall.recall_date == recall.published_date == date(2026, 1, 15)
        assert recall.notice_type is NoticeType.RECALL
        assert recall.hazard and recall.remedy

    def test_listed_upcs_are_gtin14(self, cpsc_by_id: dict[int, dict[str, Any]]) -> None:
        (product,) = cpsc.parse(cpsc_by_id[10664]).products
        assert product.upcs[:2] == ["00843461115513", "00843461115551"]

    def test_sku_numbers_that_are_barcodes_become_upcs(
        self, cpsc_by_id: dict[int, dict[str, Any]]
    ) -> None:
        # "The model number of the lantern is BGAAL9 and the SKU number is 039800143341 or ..."
        (product,) = cpsc.parse(cpsc_by_id[10557]).products
        assert product.model_numbers == ["BGAAL9"]
        assert product.upcs == ["00039800143341", "00039800143334"]
        assert {r.kind for r in product.restrictions} >= {RestrictionKind.DATE_CODE}
        assert product.unit_restricted

    def test_models_from_a_flattened_table_with_row_labels(
        self, cpsc_by_id: dict[int, dict[str, Any]]
    ) -> None:
        (product,) = cpsc.parse(cpsc_by_id[10541]).products
        assert len(product.model_numbers) == 60
        assert product.model_numbers[0] == "WL33006DMN"
        assert not product.unit_restricted

    def test_table_model_codes_are_weak_and_barcodes_strong(
        self, cpsc_by_id: dict[int, dict[str, Any]]
    ) -> None:
        (product,) = cpsc.parse(cpsc_by_id[10585]).products
        assert product.model_numbers == []
        assert "358015W" in product.weak_codes
        assert len(product.upcs) == 7

    def test_sold_window_and_retailers(self, cpsc_by_id: dict[int, dict[str, Any]]) -> None:
        (product,) = cpsc.parse(cpsc_by_id[10549]).products
        assert (product.sold_start_date, product.sold_end_date) == (
            date(2025, 9, 1),
            date(2025, 10, 31),
        )
        assert product.retailers == ["Amazon.com"]

    def test_infant_products_are_safety_critical(
        self, cpsc_by_id: dict[int, dict[str, Any]]
    ) -> None:
        for recall_id in (10543, 10545):
            (product,) = cpsc.parse(cpsc_by_id[recall_id]).products
            assert Category.INFANT_CHILD in product.categories and product.safety_critical

    def test_where_to_look_comes_from_the_description(
        self, cpsc_by_id: dict[int, dict[str, Any]]
    ) -> None:
        (product,) = cpsc.parse(cpsc_by_id[10557]).products
        assert any("bottom of the light" in hint for hint in product.where_to_look)

    def test_cpsc_warnings_are_not_called_recalls(self) -> None:
        raw = {
            "RecallID": 1,
            "Title": "CPSC Warns Consumers to Immediately Stop Using BQQZHZ Detectors",
            "Products": [{"Name": "Detectors"}],
        }
        assert cpsc.parse(raw).notice_type is NoticeType.WARNING


class TestCpscFetch:
    def test_one_request_per_year_with_documented_parameters(self) -> None:
        seen: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(dict(request.url.params))
            return httpx.Response(200, json=load("cpsc/last_publish_window.json"))

        client = httpx.Client(transport=httpx.MockTransport(handler))
        batches = list(cpsc.fetch(client, start=date(2024, 6, 1), end=date(2025, 2, 1)))
        assert [len(b) for b in batches] == [20, 20]
        assert seen == [
            {"format": "json", "RecallDateStart": "2024-06-01", "RecallDateEnd": "2024-12-31"},
            {"format": "json", "RecallDateStart": "2025-01-01", "RecallDateEnd": "2025-02-01"},
        ]
        assert set().union(*seen) <= cpsc.DOCUMENTED_PARAMETERS

    def test_rejects_a_response_that_ignored_its_filters(self) -> None:
        everything = [{"RecallID": i} for i in range(cpsc.MAX_PLAUSIBLE_WINDOW + 1)]
        client = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=everything))
        )
        with pytest.raises(cpsc.SuspiciousResponseError):
            list(cpsc.fetch(client, start=date(2025, 1, 1), end=date(2025, 1, 31)))

    def test_provider_error_placeholder_is_retried_then_split(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Real response from 2026-10-14: HTTP 200 with one fake "Error retrieving Recalls" record,
        # which CPSC kept serving for the exact URLs that had failed.
        error = load("cpsc/provider_error.json")
        good = load("cpsc/last_publish_window.json")
        monkeypatch.setattr(cpsc, "_sleep", lambda seconds: None)
        seen: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            window = (request.url.params["RecallDateStart"], request.url.params["RecallDateEnd"])
            seen.append(window)
            # The whole year (and any slightly longer window) keeps failing; halves work.
            failing = window[0] == "2023-01-01" and window[1] >= "2023-12-01"
            return httpx.Response(200, json=error if failing else good[:3])

        client = httpx.Client(transport=httpx.MockTransport(handler))
        (batch,) = list(cpsc.fetch(client, start=date(2023, 1, 1), end=date(2023, 12, 31)))
        assert not cpsc.is_provider_error(batch)
        # Each retry asks for a different URL, then the window is split in two.
        retries = seen[: cpsc.PROVIDER_ERROR_ATTEMPTS]
        assert len(set(retries)) == cpsc.PROVIDER_ERROR_ATTEMPTS
        (first, second) = seen[cpsc.PROVIDER_ERROR_ATTEMPTS :]
        assert first[0] == "2023-01-01" and second[1] == "2023-12-31"
        assert date.fromisoformat(second[0]) == date.fromisoformat(first[1]) + timedelta(days=1)
        assert len(batch) == 6

    def test_provider_error_that_persists_fails_the_fetch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = load("cpsc/provider_error.json")
        monkeypatch.setattr(cpsc, "_sleep", lambda seconds: None)
        client = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=error))
        )
        with pytest.raises(cpsc.ProviderError):
            list(cpsc.fetch(client, start=date(2023, 1, 1), end=date(2023, 1, 31)))


class TestOpenFdaParse:
    def test_an_event_becomes_one_recall_with_its_products(self) -> None:
        (recall,) = openfda.parse_events(
            RecallSource.FDA_FOOD, load("openfda/food_event_99887.json")["results"]
        )
        assert recall.source_recall_id == recall.reference == "99887"
        assert recall.title == "Todd's Seeds LLC recalls Todd's Seeds Alfalfa Sprouting Seeds"
        assert (
            recall.official_url
            == "https://www.accessdata.fda.gov/scripts/ires/index.cfm?Event=99887"
        )
        assert recall.classification == "Class I"
        assert recall.status is RecallStatus.ONGOING
        assert len(recall.products) == 6
        first = recall.products[0]
        assert first.source_product_id == "H-1404-2026"
        assert first.lot_codes == ["SAL2-24JB", "TS-1462-2.5-4", "TS-1462-5-3"]
        assert first.unit_restricted

    def test_all_fixture_records_parse(self) -> None:
        for kind, source in (
            ("food", RecallSource.FDA_FOOD),
            ("drug", RecallSource.FDA_DRUG),
            ("device", RecallSource.FDA_DEVICE),
        ):
            records = load(f"openfda/{kind}_by_recall_number.json")["results"]
            products = [p for r in openfda.parse_events(source, records) for p in r.products]
            assert len(products) == len(records)

    def test_drug_upcs_come_from_the_openfda_block(self) -> None:
        records = load("openfda/drug_by_recall_number.json")["results"]
        recalls = {
            r.source_recall_id: r for r in openfda.parse_events(RecallSource.FDA_DRUG, records)
        }
        (product,) = recalls["99893"].products
        assert product.upcs == ["00327241125027", "00327241126024"]
        assert product.brand == "RANOLAZINE"

    def test_device_models_udis_and_serial_restriction(self) -> None:
        records = load("openfda/device_by_recall_number.json")["results"]
        products = {
            p.source_product_id: p
            for r in openfda.parse_events(RecallSource.FDA_DEVICE, records)
            for p in r.products
        }
        smartpath = products["Z-3314-2026"]
        assert smartpath.model_numbers[:2] == ["781260", "782112"]
        assert "00884838095076" in smartpath.upcs
        assert {r.kind for r in smartpath.restrictions} == {RestrictionKind.SERIAL}
        # Infant nasal CPAP: a device, and safety-critical.
        assert Category.INFANT_CHILD in products["Z-3139-2026"].categories

    def test_oversized_device_fields_are_trimmed_in_raw(self) -> None:
        records = {
            r["recall_number"]: r for r in load("openfda/device_by_recall_number.json")["results"]
        }
        capped = openfda.parse_product(RecallSource.FDA_DEVICE, records["Z-3270-2026"], "Firm")
        assert capped.raw is not None
        assert len(capped.raw["code_info"]) == openfda.RAW_CODE_INFO_CHARS
        assert capped.raw["code_info_truncated_from"] > openfda.RAW_CODE_INFO_CHARS
        more = openfda.parse_product(RecallSource.FDA_DEVICE, records["Z-0099-2026"], "Firm")
        assert more.raw is not None
        assert "more_code_info" not in more.raw and more.raw["more_code_info_chars"] > 0


class TestOpenFdaFetch:
    def test_pages_with_search_after_until_no_next_link(self) -> None:
        page = load("openfda/food_page_limit3.json")
        link = (FIXTURES / "openfda/food_page_limit3.link.txt").read_text().strip()
        calls: list[httpx.URL] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url)
            headers = {"Link": link} if len(calls) == 1 else {}
            return httpx.Response(200, json=page, headers=headers)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        pages = list(
            openfda.fetch(
                client, RecallSource.FDA_FOOD, start=date(2026, 9, 1), end=date(2026, 10, 7)
            )
        )
        assert [len(p) for p in pages] == [3, 3]
        assert calls[0].params["search"] == "report_date:[20260901 TO 20261007]"
        assert "search_after" in calls[1].params

    def test_no_matches_is_an_empty_result(self) -> None:
        body = load("openfda/no_matches_404.json")
        client = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(404, json=body))
        )
        assert (
            list(
                openfda.fetch(
                    client, RecallSource.FDA_FOOD, start=date(2026, 1, 1), end=date(2026, 1, 2)
                )
            )
            == []
        )
