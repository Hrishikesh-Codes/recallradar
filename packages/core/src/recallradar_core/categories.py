"""Product categories, which recall sources cover them, and a keyword classifier.

Used in two places: tagging recall products at ingest, and deciding whether a user's product is
something our sources can check at all (the "can't check yet" coverage guard). The classifier is a
deliberately simple keyword baseline; misses fall through to CONSUMER_PRODUCT, which CPSC covers.
"""

import re
from collections.abc import Iterable
from enum import StrEnum

from recallradar_core.enums import RecallSource


class Category(StrEnum):
    VEHICLE = "vehicle"
    VEHICLE_EQUIPMENT = "vehicle_equipment"  # car seats, tires (NHTSA)
    MEAT_POULTRY_EGG = "meat_poultry_egg"  # USDA FSIS
    FOOD = "food"
    DRUG = "drug"
    MEDICAL_DEVICE = "medical_device"
    INFANT_CHILD = "infant_child"
    CONSUMER_PRODUCT = "consumer_product"


# Which sources hold recalls for each category. FDA also regulates some foods that contain meat,
# so meat/poultry products are checked against FDA too, but only FSIS is authoritative.
CATEGORY_SOURCES: dict[Category, frozenset[RecallSource]] = {
    Category.VEHICLE: frozenset({RecallSource.NHTSA}),
    Category.VEHICLE_EQUIPMENT: frozenset({RecallSource.NHTSA}),
    Category.MEAT_POULTRY_EGG: frozenset({RecallSource.FSIS}),
    Category.FOOD: frozenset({RecallSource.FDA_FOOD}),
    Category.DRUG: frozenset({RecallSource.FDA_DRUG}),
    Category.MEDICAL_DEVICE: frozenset({RecallSource.FDA_DEVICE}),
    Category.INFANT_CHILD: frozenset({RecallSource.CPSC}),
    Category.CONSUMER_PRODUCT: frozenset({RecallSource.CPSC}),
}

# SPEC §6.4: favour recall (fewer misses) for these.
SAFETY_CRITICAL = frozenset(
    {
        Category.INFANT_CHILD,
        Category.VEHICLE_EQUIPMENT,
        Category.FOOD,
        Category.MEAT_POULTRY_EGG,
    }
)

_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.VEHICLE_EQUIPMENT: (
        "car seat",
        "carseat",
        "booster seat",
        "child restraint",
        "infant seat",
        "convertible seat",
        "tire",
        "tires",
    ),
    Category.MEAT_POULTRY_EGG: (
        "beef",
        "pork",
        "chicken",
        "turkey",
        "poultry",
        "ham",
        "bacon",
        "sausage",
        "sausages",
        "hot dog",
        "hot dogs",
        "jerky",
        "salami",
        "pepperoni",
        "bologna",
        "meatball",
        "meatballs",
        "lamb",
        "veal",
        "deli meat",
        "lunch meat",
        "ground meat",
        "steak",
        "egg product",
        "egg products",
        "liquid egg",
        "liquid eggs",
    ),
    Category.INFANT_CHILD: (
        "baby",
        "babies",
        "infant",
        "infants",
        "toddler",
        "toddlers",
        "newborn",
        "crib",
        "cribs",
        "bassinet",
        "bassinets",
        "stroller",
        "strollers",
        "high chair",
        "highchair",
        "play yard",
        "playard",
        "playpen",
        "pacifier",
        "teether",
        "teething",
        "rocker",
        "bouncer",
        "baby swing",
        "baby gate",
        "changing table",
        "sleeper",
        "sleep sack",
        "onesie",
        "nursing pillow",
        "baby bottle",
        "sippy cup",
        "baby monitor",
        "kids",
        "children's",
        "child's",
        "toy",
        "toys",
    ),
    Category.DRUG: (
        "tablet",
        "tablets",
        "capsule",
        "capsules",
        "mg",
        "injection",
        "eye drops",
        "eyedrops",
        "nasal spray",
        "sunscreen",
        "hand sanitizer",
        "ointment",
        "medication",
        "medicine",
        "prescription",
        "ibuprofen",
        "acetaminophen",
        "tylenol",
        "advil",
        "aspirin",
        "antacid",
        "cough syrup",
        "supplement",
        "vitamin",
        "vitamins",
    ),
    Category.MEDICAL_DEVICE: (
        "catheter",
        "cpap",
        "bipap",
        "glucose meter",
        "glucose monitor",
        "test strips",
        "contact lens",
        "contact lenses",
        "thermometer",
        "pulse oximeter",
        "hearing aid",
        "insulin pump",
        "infusion pump",
        "ventilator",
        "nebulizer",
        "syringe",
        "syringes",
        "defibrillator",
        "blood pressure monitor",
        "wheelchair",
    ),
    Category.FOOD: (
        "food",
        "snack",
        "snacks",
        "cheese",
        "milk",
        "yogurt",
        "ice cream",
        "butter",
        "sauce",
        "dressing",
        "salad",
        "spinach",
        "lettuce",
        "sprouts",
        "seeds",
        "cookie",
        "cookies",
        "cracker",
        "crackers",
        "chips",
        "chocolate",
        "candy",
        "peanut",
        "peanuts",
        "almonds",
        "nuts",
        "flour",
        "bread",
        "cereal",
        "pasta",
        "rice",
        "juice",
        "tea",
        "coffee",
        "spice",
        "seasoning",
        "frozen",
        "fruit",
        "berries",
        "blueberries",
        "strawberries",
        "cantaloupe",
        "onion",
        "onions",
        "pepper",
        "peppers",
        "tomato",
        "tomatoes",
        "cucumber",
        "cucumbers",
        "popcorn",
        "honey",
        "baby food",
        "infant formula",
        "formula",
        "eggs",
        "egg",
        "seafood",
        "fish",
        "shrimp",
        "tuna",
        "salmon",
        "crab",
        "oysters",
    ),
}

# Ambiguous makes/models ("RAM 16GB", "Pilot G2 pen", "Explorer backpack") are left out: a vehicle
# needs a make plus a model year, a distinctive model name, a VIN, or an unambiguous noun.
# Generic words like "car" or "truck" are not enough: car chargers and toy trucks are CPSC's.
_VEHICLE_MAKES = (
    "acura|audi|bmw|buick|cadillac|chevrolet|chevy|chrysler|dodge|ferrari|fiat|ford|gmc|honda|"
    "hyundai|infiniti|jaguar|jeep|kia|land rover|lexus|lincoln|mazda|mercedes|mercedes-benz|"
    "mitsubishi|nissan|polestar|porsche|rivian|subaru|tesla|toyota|volkswagen|vw|volvo"
)
_VEHICLE_MODELS = (
    "camry|corolla|civic|rav4|cr-v|f-150|f150|f-250|silverado|tacoma|tundra|highlander|wrangler|"
    "grand cherokee|prius|sienna|pacifica|elantra|sonata|sorento|sportage|impreza|jetta|passat|"
    "tiguan|cx-5|mazda3|telluride|altima|sentra|4runner|yukon|escalade|suburban"
)
_YEAR = r"(?:19[89]\d|20[0-3]\d)"
_VEHICLE_RE = re.compile(
    rf"\b(?:{_VEHICLE_MAKES})\b.*\b{_YEAR}\b"
    rf"|\b{_YEAR}\b.*\b(?:{_VEHICLE_MAKES})\b"
    rf"|\b(?:{_VEHICLE_MODELS})\b"
    r"|\b(?:suv|sedan|minivan|automobile)s?\b"
    r"|\bvin\b"
    # A 17-character VIN (no I, O or Q) containing both letters and digits.
    r"|\b(?=[A-HJ-NPR-Z0-9]*\d)(?=[A-HJ-NPR-Z0-9]*[A-HJ-NPR-Z])[A-HJ-NPR-Z0-9]{17}\b",
    re.IGNORECASE,
)


def _compile(words: Iterable[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.IGNORECASE)


_PATTERNS = {category: _compile(words) for category, words in _KEYWORDS.items()}


def classify(text: str) -> set[Category]:
    """Every category the text plausibly belongs to (empty if nothing matched)."""
    found = {category for category, pattern in _PATTERNS.items() if pattern.search(text)}
    if _VEHICLE_RE.search(text) and Category.VEHICLE_EQUIPMENT not in found:
        found.add(Category.VEHICLE)
    # "Baby food" and "infant formula" are food first; keep the child flag too (safety-critical).
    return found


def sources_for(categories: Iterable[Category]) -> frozenset[RecallSource]:
    sources: set[RecallSource] = set()
    for category in categories:
        sources |= CATEGORY_SOURCES[category]
    return frozenset(sources)


def is_safety_critical(categories: Iterable[Category]) -> bool:
    return any(category in SAFETY_CRITICAL for category in categories)
