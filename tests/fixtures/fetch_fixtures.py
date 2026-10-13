"""Re-fetch the real API responses used as test fixtures.

    uv run python tests/fixtures/fetch_fixtures.py

Records were chosen to cover the cases parsers must handle (UPC lists, model numbers in free text,
lot/expiry codes, sold-at date windows, device UDI codes, oversized code fields, ...). Every file
is an unmodified API response; manifest.json records the exact URL and fetch time of each.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).parent
CPSC_URL = "https://www.saferproducts.gov/RestWebServices/Recall"
OPENFDA_URL = "https://api.fda.gov/{kind}/enforcement.json"

CPSC_RECALL_IDS = {
    10585: "ProductUPCs list",
    10664: "ProductUPCs list",
    10541: "model numbers in description",
    10540: "model numbers in description",
    10551: "date codes / manufacture window",
    10557: "date codes",
    10549: "sold-at window, Amazon, title without 'Recalls'",
    10548: "sold-at window, Amazon",
    10543: "infant product (safety-critical)",
    10545: "infant product (safety-critical)",
    10957: "Product Type set",
    10956: "Product Type set",
    10553: "joint recall with Health Canada",
}

OPENFDA_RECALL_NUMBERS = {
    "food": [
        "H-1398-2026",  # batch numbers with EXP dates
        "H-1403-2026",  # lot + best-by
        "H-1242-2026",  # no lot codes; pack-date range
        "H-1239-2026",  # all product before an expiration date
        "H-1015-2026",  # UPC in description; product of a 30+ product event
    ],
    "drug": [
        "D-0010-2027",  # lot + exp; has openfda (NDC) block
        "D-0876-2026",  # many lots with exp dates
        "D-0854-2026",  # OTC sunscreen
        "D-0870-2026",  # OTC eye drops, lot lists
    ],
    "device": [
        "Z-3314-2026",  # model (REF), UDI-DI, serial numbers
        "Z-3333-2026",  # REF + UDI-DI in description
        "Z-3139-2026",  # infant CPAP: model numbers, UDI-DI, lot codes
        "Z-3248-2026",  # contact lenses (consumer)
        "Z-0099-2026",  # has more_code_info
        "Z-3270-2026",  # code_info at openFDA's 32,600-character cap
    ],
}

manifest: list[dict[str, Any]] = []


def save(relative: str, payload: Any, url: str, note: str) -> None:
    path = HERE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload)
    else:
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    manifest.append(
        {"file": relative, "url": url, "fetched_at": datetime.now(UTC).isoformat(), "note": note}
    )


def main() -> None:
    with httpx.Client(timeout=120, headers={"User-Agent": "RecallRadar fixture fetcher"}) as client:
        records = []
        for recall_id, why in CPSC_RECALL_IDS.items():
            response = client.get(CPSC_URL, params={"format": "json", "RecallID": recall_id})
            response.raise_for_status()
            body = response.json()
            assert len(body) == 1, f"RecallID={recall_id} returned {len(body)} records ({why})"
            records.extend(body)
        save(
            "cpsc/recalls_by_id.json",
            records,
            f"{CPSC_URL}?format=json&RecallID=<id> for ids {list(CPSC_RECALL_IDS)}",
            "one request per RecallID, concatenated in that order",
        )

        params = {
            "format": "json",
            "LastPublishDateStart": "2026-10-01",
            "LastPublishDateEnd": "2026-10-08",
        }
        response = client.get(CPSC_URL, params=params)
        response.raise_for_status()
        save("cpsc/last_publish_window.json", response.json(), str(response.url), "full window")

        for kind, numbers in OPENFDA_RECALL_NUMBERS.items():
            # openFDA only ORs values grouped under one field; repeating the field returns
            # just the last match, and unquoted values match thousands of unrelated records.
            search = "recall_number:(" + " ".join(f'"{n}"' for n in numbers) + ")"
            response = client.get(
                OPENFDA_URL.format(kind=kind), params={"search": search, "limit": 100}
            )
            response.raise_for_status()
            save(
                f"openfda/{kind}_by_recall_number.json",
                response.json(),
                str(response.url),
                "full response incl. meta",
            )

        # One whole recall event (6+ products sharing an event_id).
        response = client.get(
            OPENFDA_URL.format(kind="food"), params={"search": "event_id:99887", "limit": 100}
        )
        response.raise_for_status()
        save("openfda/food_event_99887.json", response.json(), str(response.url), "one event")

        # Paging: a small first page and its Link header (search_after).
        params = {
            "search": "report_date:[20260901 TO 20261007]",
            "limit": 3,
            "sort": "report_date:asc",
        }
        response = client.get(OPENFDA_URL.format(kind="food"), params=params)
        response.raise_for_status()
        save("openfda/food_page_limit3.json", response.json(), str(response.url), "first page")
        save(
            "openfda/food_page_limit3.link.txt",
            response.headers.get("link", "") + "\n",
            str(response.url),
            "Link response header of the page above",
        )

        # openFDA answers a search with no results with HTTP 404 and an error body.
        response = client.get(
            OPENFDA_URL.format(kind="food"), params={"search": 'recall_number:"NOPE-0000-0000"'}
        )
        assert response.status_code == 404, response.status_code
        save("openfda/no_matches_404.json", response.json(), str(response.url), "HTTP 404 body")

    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"saved {len(manifest)} fixtures")


if __name__ == "__main__":
    main()
