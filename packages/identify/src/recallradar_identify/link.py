"""Product links: read the URL text only. We never fetch retailer pages (SPEC §0.5, §5.4).

Many retailer URLs carry the product name as a slug ("/Fisher-Price-Rocker/dp/B07XYZ1234"); those
become a typed description. Short links (a.co, amzn.to) and slug-less links can't be read without
visiting the page, so the user is asked for the product name instead.
"""

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from recallradar_identify.query import InputType, ProductQuery
from recallradar_identify.text import parse_text
from recallradar_ingest.extract import codes

SHORT_LINK_HOSTS = frozenset(
    {"a.co", "amzn.to", "amzn.eu", "amzn.asia", "bit.ly", "tinyurl.com", "goo.gl", "ebay.us",
     "wmt.co", "tgt.biz", "t.co", "rb.gy", "spr.ly"}
)  # fmt: skip


@dataclass(frozen=True)
class _Retailer:
    name: str
    host: re.Pattern[str]
    # Regex over the URL path; may define groups "slug" and "id".
    path: re.Pattern[str]


_RETAILERS = [
    _Retailer(
        "Amazon",
        re.compile(r"(?:^|\.)amazon\.[a-z.]+$"),
        re.compile(
            r"^/(?:(?P<slug>[^/]+)/)?(?:dp|gp/product|gp/aw/d|exec/obidos/asin)/"
            r"(?P<id>[A-Z0-9]{10})",
            re.I,
        ),
    ),
    _Retailer(
        "Walmart",
        re.compile(r"(?:^|\.)walmart\.com$"),
        re.compile(r"^/ip/(?:(?P<slug>[^/]+)/)?(?P<id>\d+)"),
    ),
    _Retailer(
        "Target",
        re.compile(r"(?:^|\.)target\.com$"),
        re.compile(r"^/p/(?P<slug>[^/]+)/-/A-(?P<id>\d+)"),
    ),
    _Retailer(
        "The Home Depot",
        re.compile(r"(?:^|\.)homedepot\.com$"),
        re.compile(r"^/p/(?:(?P<slug>[^/]+)/)?(?P<id>\d+)"),
    ),
    _Retailer(
        "Lowe's",
        re.compile(r"(?:^|\.)lowes\.com$"),
        re.compile(r"^/pd/(?P<slug>[^/]+)/(?P<id>\d+)"),
    ),
    _Retailer(
        "Best Buy",
        re.compile(r"(?:^|\.)bestbuy\.com$"),
        re.compile(r"^/site/(?P<slug>[^/]+)/(?P<id>\d+)\.p"),
    ),
    _Retailer(
        "Costco",
        re.compile(r"(?:^|\.)costco\.com$"),
        re.compile(r"^/(?P<slug>[^/]+)\.product\.(?P<id>\d+)\.html"),
    ),
    _Retailer(
        "Wayfair",
        re.compile(r"(?:^|\.)wayfair\.com$"),
        re.compile(r"/pdp/(?P<slug>[^/]+?)-(?P<id>[a-z0-9]+)\.html", re.I),
    ),
    _Retailer(
        "Etsy",
        re.compile(r"(?:^|\.)etsy\.com$"),
        re.compile(r"^/listing/(?P<id>\d+)(?:/(?P<slug>[^/?]+))?"),
    ),
    _Retailer(
        "eBay",
        re.compile(r"(?:^|\.)ebay\.[a-z.]+$"),
        re.compile(r"^/itm/(?:(?P<slug>[^/]+)/)?(?P<id>\d+)"),
    ),
    _Retailer(
        "Kohl's",
        re.compile(r"(?:^|\.)kohls\.com$"),
        re.compile(r"^/product/prd-(?P<id>\d+)/(?P<slug>[^/.]+)"),
    ),
    _Retailer(
        "Macy's", re.compile(r"(?:^|\.)macys\.com$"), re.compile(r"^/shop/product/(?P<slug>[^/?]+)")
    ),
]


# In a slug, hyphens separate words and also sit inside model numbers ("...-Gas-Grill-CGG-6331"):
# a short letter group followed by a number group is rejoined as a model candidate.
_SLUG_MODEL = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2,5})-(\d{3,6}[A-Za-z]{0,2})(?![A-Za-z0-9])")


def _slug_models(slug: str) -> list[str]:
    found = (f"{letters}-{digits}" for letters, digits in _SLUG_MODEL.findall(unquote(slug)))
    return [m.upper() for m in found if codes.is_code_like(m, kind=codes.CodeKind.MODEL)]


def _slug_to_name(slug: str) -> str:
    words = re.split(r"[-_+]+", unquote(slug))
    return " ".join(w for w in words if w and not re.fullmatch(r"ref=.*", w, re.I))


def parse_link(url: str) -> ProductQuery:
    raw = url.strip()
    parts = urlsplit(raw if "://" in raw else f"https://{raw}")
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    notes: list[str] = []

    if host in SHORT_LINK_HOSTS:
        return ProductQuery(
            input_type=InputType.LINK,
            raw=raw[:2000],
            notes=[
                "Short links can't be read without visiting the page, and we never do that. "
                "Paste the full product link, or type the product name."
            ],
            confidence={},
        )

    retailer = next((r for r in _RETAILERS if r.host.search(host)), None)
    slug: str | None = None
    product_id: str | None = None
    if retailer is not None and (match := retailer.path.search(parts.path)):
        slug, product_id = match.groupdict().get("slug"), match.groupdict().get("id")
    elif retailer is None:
        # Unknown store: the longest hyphenated path segment is usually the product name.
        segments = [s for s in parts.path.split("/") if s.count("-") >= 2]
        slug = max(segments, key=len) if segments else None

    name = _slug_to_name(slug) if slug else ""
    if not name:
        notes.append(
            "This link doesn't include the product's name, and we never open retailer pages. "
            "Type the product name or model number to check it."
        )
        return ProductQuery(
            input_type=InputType.LINK,
            raw=raw[:2000],
            retailer=retailer.name if retailer else None,
            notes=notes,
        )

    query = parse_text(name)
    for model in _slug_models(slug or ""):
        if model not in query.model_numbers:
            query.model_numbers.append(model)
    query.input_type = InputType.LINK
    query.raw = raw[:2000]
    query.retailer = retailer.name if retailer else host or None
    query.confidence["product_name"] = 0.7 if retailer else 0.4
    if product_id:
        query.notes.append(f"{retailer.name if retailer else 'Store'} item {product_id}")
    return query
