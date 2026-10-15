"""Vehicle recalls (NHTSA), matched on make, model, and model year, never on name similarity.

A query is a vehicle when it comes from a decoded VIN, or when its text names a make NHTSA has
recalled and either one of that make's recalled models or a model year ("2019 Honda Civic",
"Ford Mustang"). "Honda generator" names a make but no vehicle model, so it isn't one.

NHTSA recalls cover certain vehicles by VIN, and the public API can't say whether a given VIN
is included, so a match is "Check your unit" with a link to NHTSA's VIN search.
"""

import re
import threading
import time
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from recallradar_core.categories import Category
from recallradar_core.db import Recall, RecallProduct
from recallradar_identify.query import ProductQuery
from recallradar_ingest.extract.text import code_key
from recallradar_matching.text import tokens

# What people type vs NHTSA's make names.
MAKE_ALIASES = {
    "CHEVY": "CHEVROLET",
    "VW": "VOLKSWAGEN",
    "MERCEDES": "MERCEDESBENZ",
    "BENZ": "MERCEDESBENZ",
    "MERCEDESBENZ": "MERCEDESBENZ",
    "LANDROVER": "LANDROVER",
    "HARLEY": "HARLEYDAVIDSON",
}
_YEAR = re.compile(r"^(19[89]\d|20[0-3]\d)$")
# Words that describe a vehicle but aren't part of its model name.
_FILLER = frozenset(
    "car cars truck trucks suv van minivan sedan coupe pickup vehicle my our the a an "
    "motorcycle bike".split()
)
MAKES_TTL_SECONDS = 600.0
# NHTSA's flat file starts with reports received in 2010; older vehicles may have older recalls.
FIRST_COVERED_YEAR = 2010


@dataclass
class VehicleQuery:
    make: str  # normalised, e.g. "HONDA"
    model_words: list[str]  # e.g. ["civic", "ex"]
    year: int | None
    explicit: bool  # from a VIN, or the text clearly describes a vehicle


@dataclass
class VehicleResult:
    query: VehicleQuery
    rows: list[tuple[RecallProduct, Recall]] = field(default_factory=list)
    model: str | None = None  # the NHTSA model key that matched, if any
    model_known: bool = False  # NHTSA has recalled this make + model at some point
    exact_ids: set[int] = field(default_factory=set)  # products named exactly as the query


class _Makes:
    """Makes with at least one vehicle recall, cached per database for a few minutes."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, frozenset[str]]] = {}
        self._lock = threading.Lock()

    def get(self, session: Session) -> frozenset[str]:
        key = str(session.get_bind().engine.url)
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < MAKES_TTL_SECONDS:
                return hit[1]
        makes = frozenset(
            m
            for m in session.scalars(
                select(RecallProduct.vehicle_make)
                .where(RecallProduct.vehicle_make.is_not(None))
                .distinct()
            )
            if m
        )
        with self._lock:
            self._cache[key] = (time.monotonic(), makes)
        return makes


_makes = _Makes()


def _find_make(words: list[str], makes: frozenset[str]) -> tuple[str, int, int] | None:
    """(make key, start, end) of the first make named in `words`; two-word makes first."""
    for size in (2, 1):
        for start in range(len(words) - size + 1):
            key = code_key("".join(words[start : start + size]))
            key = MAKE_ALIASES.get(key, key)
            if key in makes:
                return key, start, start + size
    return None


def vehicle_query(session: Session, query: ProductQuery) -> VehicleQuery | None:
    makes = _makes.get(session)
    if not makes:
        return None  # NHTSA isn't ingested
    if query.vehicle is not None:
        make = code_key(query.vehicle.make)
        return VehicleQuery(
            make=MAKE_ALIASES.get(make, make),
            model_words=tokens(query.vehicle.model),
            year=query.vehicle.year,
            explicit=True,
        )
    words = tokens(query.search_text())
    found = _find_make(words, makes)
    if found is None:
        return None
    make, _, end = found
    years = [int(w) for w in words if _YEAR.match(w)]
    model_words = [w for w in words[end:] if not _YEAR.match(w) and w not in _FILLER]
    return VehicleQuery(
        make=make,
        model_words=model_words,
        year=years[0] if years else None,
        explicit=Category.VEHICLE in query.categories or bool(years),
    )


def _model_rows(session: Session, make: str, model: str, *, prefix: bool) -> list[RecallProduct]:
    condition = (
        RecallProduct.vehicle_model.startswith(model, autoescape=True)
        if prefix
        else RecallProduct.vehicle_model == model
    )
    return list(
        session.scalars(select(RecallProduct).where(RecallProduct.vehicle_make == make, condition))
    )


def find(session: Session, vq: VehicleQuery) -> VehicleResult | None:
    """Recalls for the vehicle; None if the text only named a make and isn't a vehicle."""
    result = VehicleResult(query=vq)
    exact: list[RecallProduct] = []
    # Longest model name first: "civic type r" before "civic".
    for size in range(len(vq.model_words), 0, -1):
        key = code_key("".join(vq.model_words[:size]))
        if key and (exact := _model_rows(session, vq.make, key, prefix=False)):
            result.model = key
            break
    # NHTSA often files the variant ("SILVERADO 1500", "SILVERADO 2500HD"), so also look for
    # models that start with the name; prefer exact names when they cover the model year.
    prefix: list[RecallProduct] = []
    first = code_key(vq.model_words[0]) if vq.model_words else ""
    if len(first) >= 3:
        prefix = _model_rows(session, vq.make, result.model or first, prefix=True)
        result.model = result.model or (first if prefix else None)
    # Exact names first, then variants. Every vehicle match is "Check your unit", so including
    # "RAV4 HYBRID" for a "RAV4" costs a line on the screen, while leaving it out could miss it.
    seen = {p.id for p in exact}
    products = exact + [p for p in prefix if p.id not in seen]
    if not exact and not prefix and not vq.explicit:
        return None  # e.g. "Honda generator": a make, but not a vehicle
    result.model_known = bool(products)
    result.exact_ids = {p.id for p in exact}
    if vq.year is not None:
        products = [p for p in products if vq.year in p.model_years]
    if products:
        recalls = {
            r.id: r
            for r in session.scalars(
                select(Recall).where(Recall.id.in_({p.recall_id for p in products}))
            )
        }
        rows = [(p, recalls[p.recall_id]) for p in products]
        # Exact model names first, then newest recall first; undated last.
        rows.sort(key=lambda pr: pr[1].recall_date or date.min, reverse=True)
        rows.sort(key=lambda pr: pr[0].id not in result.exact_ids)
        result.rows = rows
    return result
