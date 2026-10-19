"""The matcher end to end on real CPSC and openFDA records (tests/fixtures), with the real model.

Expected verdicts follow SPEC §6.4: "Recalled" only for an identifier match on a recall that
covers every unit; "Check your unit" for restricted recalls and same-brand product families.
"""

from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from recallradar_core.enums import RecallSource
from recallradar_identify.barcode import parse_barcode
from recallradar_identify.query import ProductQuery
from recallradar_identify.text import parse_text
from recallradar_identify.vin import Decoded, parse_vin
from recallradar_matching.embed import Embedder
from recallradar_matching.engine import CheckResult, Tier, check, embed_query

pytestmark = [pytest.mark.db, pytest.mark.model]
INGESTED = [
    RecallSource.CPSC,
    RecallSource.FDA_FOOD,
    RecallSource.FDA_DRUG,
    RecallSource.FDA_DEVICE,
    RecallSource.NHTSA,
    RecallSource.FSIS,
]


@pytest.fixture(scope="module")
def sessions(loaded_database_url: str) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(loaded_database_url)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def run(
    sessions: sessionmaker[Session], embedder: Embedder
) -> Callable[[ProductQuery], CheckResult]:
    def go(query: ProductQuery, ingested: list[RecallSource] = INGESTED) -> CheckResult:
        with sessions() as session:
            return check(session, query, embedding=embed_query(embedder, query), ingested=ingested)

    return go


def recall_ids(result: CheckResult) -> list[str]:
    return [m.recall.source_recall_id for m in result.matches]


def test_barcode_on_a_whole_product_recall_is_recalled(run: Callable[..., CheckResult]) -> None:
    result = run(parse_barcode("843461115513"))  # BUILT LUUM tumbler, CPSC 10664
    assert result.verdict is Tier.RECALLED
    assert recall_ids(result) == ["10664"]
    assert "barcode" in result.matches[0].reasons[0]


def test_barcode_on_a_restricted_recall_is_check_your_unit(run: Callable[..., CheckResult]) -> None:
    result = run(parse_barcode("039800143341"))  # Energizer lantern, certain date codes only
    assert result.verdict is Tier.CHECK_UNIT
    assert recall_ids(result)[0] == "10557"
    assert result.matches[0].what_to_check


def test_model_and_brand_is_recalled(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("DR Power leaf vacuum WL33006DMN"))
    assert result.verdict is Tier.RECALLED
    assert recall_ids(result)[0] == "10541"


def test_model_without_brand_is_only_check_your_unit(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("WL33006DMN"))
    assert result.verdict is Tier.CHECK_UNIT
    assert recall_ids(result)[0] == "10541"


def test_same_brand_similar_product_is_check_your_unit(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("Yolaah bed rail for adults"))
    assert result.verdict is Tier.CHECK_UNIT
    assert recall_ids(result)[0] == "10549"


def test_other_brand_same_product_type_is_not_a_match(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("Hydro Flask insulated tumbler"))
    assert result.verdict is Tier.ALL_CLEAR
    assert result.matches == []


def test_unlisted_barcode_is_all_clear(run: Callable[..., CheckResult]) -> None:
    result = run(parse_barcode("036000291452"))
    assert result.verdict is Tier.ALL_CLEAR


def test_vehicle_matches_on_make_model_and_year(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("2019 Honda Civic"))
    assert result.verdict is Tier.CHECK_UNIT  # recalls cover certain VINs
    assert recall_ids(result) == ["20V314000"]
    match = result.matches[0]
    assert match.reasons[0] == "The 2019 HONDA CIVIC is listed in NHTSA recall 20V314000."
    assert any("VIN" in tip for tip in match.what_to_check)


def test_vehicle_without_a_recall_that_year_is_all_clear(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("2024 Honda Civic"))  # the fixture recall covers 2018-2020
    assert result.verdict is Tier.ALL_CLEAR


def test_unknown_model_is_not_all_clear(run: Callable[..., CheckResult]) -> None:
    assert run(parse_text("2019 Honda Flibbertigibbet")).verdict is Tier.UNIDENTIFIED


def test_vin_query_uses_the_decoded_vehicle(run: Callable[..., CheckResult]) -> None:
    query = parse_vin("1HGCM82633A004352", lambda vin: Decoded("HONDA", "Civic", 2019, None))
    result = run(query)
    assert recall_ids(result) == ["20V314000"]


def test_do_not_drive_advisory_reaches_the_match(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("2024 Porsche Cayenne"))
    assert result.matches[0].recall.hazard is not None
    assert result.matches[0].recall.hazard.startswith("NHTSA advises: do not drive")


def test_child_seat_matches_by_brand_and_line(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("Nuna Rava convertible car seat"))
    assert result.verdict is Tier.CHECK_UNIT
    assert recall_ids(result) == ["24C002000"]


def test_meat_is_not_covered_without_fsis(run: Callable[..., CheckResult]) -> None:
    without_fsis = [s for s in INGESTED if s is not RecallSource.FSIS]
    result = run(parse_text("Oscar Mayer bacon"), without_fsis)
    assert result.verdict is Tier.NOT_COVERED
    assert RecallSource.FSIS in result.uncovered_sources


def test_meat_matches_by_two_word_brand_and_product_type(run: Callable[..., CheckResult]) -> None:
    # FSIS 025-2025 names "Oscar Mayer Turkey BACON ORIGINAL"; the firm is Kraft Heinz.
    result = run(parse_text("Oscar Mayer turkey bacon"))
    assert result.verdict is Tier.CHECK_UNIT
    assert recall_ids(result) == ["025-2025"]
    assert result.matches[0].brand_words == {"oscar", "mayer"}


def test_meat_barcode_with_lot_codes_is_check_your_unit(run: Callable[..., CheckResult]) -> None:
    result = run(parse_barcode("071871548601"))  # FSIS 025-2025 lists lots for this UPC
    assert result.verdict is Tier.CHECK_UNIT
    assert recall_ids(result) == ["025-2025"]


def test_same_brand_other_product_type_is_not_a_match(run: Callable[..., CheckResult]) -> None:
    result = run(parse_text("Oscar Mayer hot dogs"))
    assert "025-2025" not in recall_ids(result)


def test_vague_input_is_unidentified(run: Callable[..., CheckResult]) -> None:
    assert run(parse_text("blender")).verdict is Tier.UNIDENTIFIED
