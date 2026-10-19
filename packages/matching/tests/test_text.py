"""Text helpers the matcher compares product names with."""

import pytest

from recallradar_matching.text import product_types, title_product_phrase, type_stem


@pytest.mark.parametrize(
    ("word", "expected"),
    [("washer", "wash"), ("washers", "wash"), ("washing", "wash"), ("dressers", "dress")],
)
def test_type_stem_folds_word_forms(word: str, expected: str) -> None:
    assert type_stem(word) == expected


def test_washing_machine_and_washer_are_one_type() -> None:
    assert product_types("Samsung Top-Load Washing Machines") == product_types("top load washer")


def test_connector_and_brand_words_are_not_types() -> None:
    assert product_types("Fisher-Price Rock n Play sleeper", brand={"fisher", "price"}) == {
        "rock",
        "play",
        "sleep",
    }
    assert "and" not in product_types("chests and dressers")


def test_food_types() -> None:
    assert product_types("Oscar Mayer Ham & Cheese LOAF", brand={"oscar", "mayer"}) == {
        "ham",
        "cheese",
    }
    assert product_types("Oscar Mayer bacon", brand={"oscar", "mayer"}) == {"bacon"}


def test_title_product_phrase() -> None:
    title = "IKEA Recalls 29 Million MALM Chests and Dressers Due to Tip-Over Hazard"
    assert title_product_phrase(title) == "29 MALM Chests and Dressers"
