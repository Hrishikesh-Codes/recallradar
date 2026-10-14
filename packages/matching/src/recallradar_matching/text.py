"""Tokens for brand and name comparison."""

import re
from collections.abc import Iterable

from recallradar_core.categories import _KEYWORDS

_TOKEN = re.compile(r"[a-z0-9]+")
_POSSESSIVE = re.compile(r"['\u2019]s\b")

# Words that describe what a product is (or are filler), so sharing them says nothing about
# whether two products come from the same brand.
_STOP = frozenset(
    """
    a an and are as at be but by for from has have in into is it its of on or our the their this
    to with without your you my me mine we i new old used set pack kit piece pieces pcs inch inches
    in oz lb lbs ft
    size small medium large xl mini plus pro max ultra series model models edition version
    black white gray grey silver gold red blue green pink purple orange yellow brown beige clear
    product products item items brand brands type style color colour bought purchased sold
    adult adults kids kid men women mens womens girls boys unisex home portable electric
    """.split()
)
_CORPORATE = frozenset(
    """
    inc llc ltd co corp corporation company companies limited lp llp plc gmbh ag sa usa us
    international intl group holdings holding brands products industries enterprises
    manufacturing mfg technology technologies trading import imports importer distributors
    distribution dba doing business as of the and
    """.split()
)
_PRODUCT_WORDS = frozenset(
    word for words in _KEYWORDS.values() for phrase in words for word in phrase.lower().split()
) | frozenset(
    """
    chair chairs table tables lamp lamps light lights charger chargers cable cables battery
    batteries bottle bottles cup cups mug mugs tumbler tumblers bag bags case cases cover
    covers bed beds rail rails dresser dressers chest drawer drawers cabinet cabinets shelf
    heater heaters fan fans cooker cookers pot pots pan pans blender blenders fryer fryers
    oven ovens vacuum vacuums mower mowers saw saws drill drills tool tools helmet helmets
    bike bikes bicycle bicycles scooter scooters seat seats swing swings gate gates mat mats
    pillow pillows blanket blankets jacket jackets shirt shirts pajamas shoes boots lantern
    lanterns flashlight flashlights generator generators washer washers dryer dryers
    pool pools stand stands rack racks mount mounts monitor monitors phone phones
    headphones speaker speakers watch watches camera cameras machine machines device devices
    """.split()
)
GENERIC = _STOP | _PRODUCT_WORDS


def tokens(text: str | None) -> list[str]:
    """Lowercase words and numbers; possessives dropped ("kid's" -> "kid")."""
    return _TOKEN.findall(_POSSESSIVE.sub("", (text or "").lower()).replace("-", " "))


def distinctive_tokens(text: str | None) -> set[str]:
    """Tokens that could name a brand or product line (not sizes, colours, or product types)."""
    return {t for t in tokens(text) if t not in GENERIC and len(t) >= 2 and not t.isdigit()}


def brand_tokens(names: Iterable[str | None]) -> set[str]:
    """Identifying tokens of company/brand names: "Kids II, Inc., of Atlanta" -> {"kids", "ii"}."""
    found: set[str] = set()
    for name in names:
        company = re.split(r",?\s+of\s+[A-Z]", name or "")[0]
        found |= {t for t in tokens(company) if t not in _CORPORATE and len(t) >= 2}
    return found


def stem(token: str) -> str:
    """Crude plural folding, enough to compare product names: "loungers" -> "lounger"."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith(("ches", "shes", "sses", "xes", "zes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def stems(words: Iterable[str]) -> set[str]:
    return {stem(word) for word in words}


# "IKEA Recalls 29 Million MALM ... Dressers Due to ..." -> "29 Million MALM ... Dressers";
# "HALO 1000 Power Stations Recalled Due to ..." -> "HALO 1000 Power Stations".
_TITLE_VERB = re.compile(
    r"\b(?:re-?announces\s+recall\s+of|expands\s+recall\s+of|recalls|recalled|warns)\b", re.I
)
_TITLE_END = re.compile(r"\b(?:due\s+to|because|after|following)\b|;", re.I)
_TITLE_STOP = frozenset(
    "million thousand hundred about approximately nearly more than other certain models model "
    "additional sold exclusively at".split()
)


def title_product_phrase(title: str) -> str:
    """The product part of a recall headline, without the firm, hazard, or counts."""
    verb = _TITLE_VERB.search(title)
    if verb is None:
        return title
    after = title[verb.end() :]
    end = _TITLE_END.search(after)
    phrase = after[: end.start()] if end else after
    if not phrase.strip(" ,:"):  # "X Recalled Due to ...": the product comes first
        phrase = title[: verb.start()]
    return " ".join(w for w in phrase.split() if w.lower() not in _TITLE_STOP)
