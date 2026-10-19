"""Tier rules for one candidate, without a database."""

import pytest

from recallradar_core.db import Recall, RecallProduct
from recallradar_core.enums import NoticeType, RecallSource
from recallradar_identify.text import parse_text
from recallradar_matching.engine import Match, Signals, Tier, _score


def barcode_match(notice_type: NoticeType) -> Match:
    recall = Recall(
        source=RecallSource.FSIS,
        source_recall_id="PHA-1",
        reference="PHA-1",
        notice_type=notice_type,
        title="Example notice",
    )
    product = RecallProduct(
        product_name="Example sausages",
        model_keys=[],
        weak_model_keys=[],
        model_numbers=[],
        restrictions=[],
        where_to_look=["The barcode is on the back of the can."],
        unit_restricted=False,
    )
    return Match(
        product=product, recall=recall, tier=None, signals=Signals(upc=True), brand_match=True
    )


def test_barcode_on_an_unrestricted_recall_is_recalled() -> None:
    match = barcode_match(NoticeType.RECALL)
    _score(match, parse_text("Example sausages"), safety_critical=True)
    assert match.tier is Tier.RECALLED


@pytest.mark.parametrize(
    ("notice_type", "name"),
    [(NoticeType.ALERT, "public health alert"), (NoticeType.WARNING, "warning")],
)
def test_warnings_and_alerts_are_never_recalled(notice_type: NoticeType, name: str) -> None:
    match = barcode_match(notice_type)
    _score(match, parse_text("Example sausages"), safety_critical=True)
    assert match.tier is Tier.CHECK_UNIT
    assert any(f"This is a {name}, not a recall" in reason for reason in match.reasons)
    assert "The barcode is on the back of the can." in match.what_to_check
