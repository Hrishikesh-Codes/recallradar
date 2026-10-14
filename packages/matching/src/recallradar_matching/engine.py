"""Baseline matcher (M1): candidate generation, rule-based scoring, and verdict tiers.

Candidates are the union of exact identifier matches, full-text search, trigram name similarity,
and embedding nearest neighbours (SPEC §6.2). Scoring is transparent rules for now; M3 replaces
the scorer with a trained, calibrated model that must beat this one on a labelled test set.

Tiers never overclaim (SPEC §6.4):
- RECALLED only for an exact identifier match (UPC, or model number plus brand) on a recall that
  covers every unit, or whose listed lot the user's lot matches. Decided by code, not ML.
- CHECK_UNIT when the identifier matches but the recall covers only some lots/dates/serials, or
  the same brand's similar product (a product family) is recalled.
- ALL_CLEAR says "no recalls found in the sources we checked", never "safe".
- NOT_COVERED when the product's category belongs to a source we don't ingest yet.
- UNIDENTIFIED when the input is too vague to check.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

from sqlalchemy import String, func, literal, literal_column, or_, select, text
from sqlalchemy.orm import Session

from recallradar_core.categories import is_safety_critical, sources_for
from recallradar_core.db import Recall, RecallProduct
from recallradar_core.enums import SOURCE_LABELS, NoticeType, RecallSource
from recallradar_identify.query import ProductQuery
from recallradar_ingest.extract.text import code_key
from recallradar_matching.embed import Embedder
from recallradar_matching.text import GENERIC, brand_tokens, distinctive_tokens, tokens

CANDIDATES_PER_RETRIEVER = 50
RRF_K = 60
# Name-similarity thresholds (cosine, bge-small-en-v1.5). Initial hand-set values, documented in
# DECISIONS.md and replaced by calibrated thresholds in M3. Lower = more "check your unit".
FAMILY_SIMILARITY = 0.80
FAMILY_SIMILARITY_SAFETY_CRITICAL = 0.76
RELATED_SIMILARITY = 0.70
TRIGRAM_FAMILY = 0.60
MAX_MATCHES = 5
MAX_RELATED = 5
# Brand words are rare: "Graco" is in 3 of 75,000 recalled products, "Multi" in over 1,000.
FREQUENCY_CAP = 1000
MAX_BRAND_FREQUENCY = 500
MAX_FIRST_WORD_FREQUENCY = 100
# A purchase this long before the recalled units went on sale is unlikely to be one of them.
SOLD_WINDOW_SLACK = timedelta(days=60)


class Tier(StrEnum):
    RECALLED = "recalled"
    CHECK_UNIT = "check_unit"
    ALL_CLEAR = "all_clear"
    UNIDENTIFIED = "unidentified"
    NOT_COVERED = "not_covered"


_SEVERITY = [Tier.RECALLED, Tier.CHECK_UNIT]


@dataclass
class Signals:
    upc: bool = False
    model: bool = False
    weak_model: bool = False
    lot: bool = False
    vector_similarity: float = 0.0
    trigram_similarity: float = 0.0
    fused: float = 0.0  # reciprocal-rank fusion across retrievers


@dataclass
class Match:
    product: RecallProduct
    recall: Recall
    tier: Tier | None  # None: related, not a match
    signals: Signals
    brand_match: bool
    reasons: list[str] = field(default_factory=list)
    what_to_check: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    verdict: Tier
    matches: list[Match]
    related: list[Match]
    checked_sources: list[RecallSource]
    uncovered_sources: list[RecallSource]
    notes: list[str]


def _distinctive_key(key: str) -> bool:
    """Specific enough to suggest a match without a brand: "IPDUO60" yes, "2512" no."""
    has_letters = any(c.isalpha() for c in key)
    return len(key) >= 6 or (has_letters and any(c.isdigit() for c in key) and len(key) >= 4)


def _tsquery(words: Sequence[str]) -> str | None:
    terms = [w for w in dict.fromkeys(words) if re.fullmatch(r"[a-z0-9]+", w) and len(w) > 1]
    return " | ".join(terms[:12]) or None


def _retrieve(
    session: Session, query: ProductQuery, embedding: list[float] | None
) -> dict[int, Signals]:
    signals: dict[int, Signals] = {}

    def get(product_id: int) -> Signals:
        return signals.setdefault(product_id, Signals())

    def fuse(ranked: Sequence[int]) -> None:
        for rank, product_id in enumerate(ranked):
            get(product_id).fused += 1.0 / (RRF_K + rank + 1)

    upcs = list(dict.fromkeys(query.upcs))
    model_keys = [k for k in dict.fromkeys(code_key(m) for m in query.model_numbers) if k]
    lot_keys = [k for k in dict.fromkeys(code_key(m) for m in query.lot_codes) if k]

    if upcs or model_keys:
        conditions = []
        if upcs:
            conditions.append(RecallProduct.upcs.overlap(upcs))
        if model_keys:
            conditions += [
                RecallProduct.model_keys.overlap(model_keys),
                RecallProduct.weak_model_keys.overlap(model_keys),
            ]
        identifier_rows = session.execute(
            select(
                RecallProduct.id,
                RecallProduct.upcs.overlap(upcs or ["-"]),
                RecallProduct.model_keys.overlap(model_keys or ["-"]),
                RecallProduct.weak_model_keys.overlap(model_keys or ["-"]),
                RecallProduct.lot_keys.overlap(lot_keys or ["-"]),
            )
            .where(or_(*conditions))
            .limit(200)
        ).all()
        for product_id, upc, model, weak, lot in identifier_rows:
            s = get(product_id)
            s.upc, s.model, s.weak_model, s.lot = bool(upc), bool(model), bool(weak), bool(lot)

    search = query.search_text()
    words = tokens(search)
    if words:
        tsquery = _tsquery(words)
        if tsquery:
            q = func.to_tsquery("english", tsquery)
            ranked = session.scalars(
                select(RecallProduct.id)
                .where(RecallProduct.search_text.op("@@")(q))
                .order_by(func.ts_rank_cd(RecallProduct.search_text, q).desc())
                .limit(CANDIDATES_PER_RETRIEVER)
            ).all()
            fuse(ranked)

        name_prefix = func.left(RecallProduct.product_name, literal_column("200"))
        session.execute(text("SET LOCAL pg_trgm.word_similarity_threshold = 0.45"))
        similarity = func.word_similarity(search, name_prefix)
        trigram_rows = session.execute(
            select(RecallProduct.id, similarity)
            .where(literal(search, String).op("<%")(name_prefix))
            .order_by(similarity.desc())
            .limit(CANDIDATES_PER_RETRIEVER)
        ).all()
        fuse([product_id for product_id, _ in trigram_rows])
        for product_id, score in trigram_rows:
            get(product_id).trigram_similarity = float(score)

    if embedding is not None:
        session.execute(text("SET LOCAL hnsw.ef_search = 400"))
        distance = RecallProduct.embedding.cosine_distance(embedding)
        vector_rows = session.execute(
            select(RecallProduct.id, distance)
            .where(RecallProduct.embedding.is_not(None))
            .order_by(distance)
            .limit(CANDIDATES_PER_RETRIEVER)
        ).all()
        fuse([product_id for product_id, _ in vector_rows])
        for product_id, dist in vector_rows:
            get(product_id).vector_similarity = 1.0 - float(dist)
    return signals


def _plausible_purchase(product: RecallProduct, purchased: date | None) -> bool | None:
    if purchased is None or product.sold_start_date is None:
        return None
    return purchased >= product.sold_start_date - SOLD_WINDOW_SLACK


def _format_window(product: RecallProduct) -> str:
    start, end = product.sold_start_date, product.sold_end_date
    if start and end:
        return f"{start:%b %Y}\u2013{end:%b %Y}"
    return f"from {start:%b %Y}" if start else ""


def _source_label(recall: Recall) -> str:
    kind = "warning" if recall.notice_type is NoticeType.WARNING else "recall"
    return f"{SOURCE_LABELS[recall.source]} {kind} {recall.reference or recall.source_recall_id}"


def _score(match: Match, query: ProductQuery, safety_critical: bool) -> None:
    """Assign a tier and human-readable reasons to one candidate."""
    s, product, recall = match.signals, match.product, match.recall
    label = _source_label(recall)
    model_hits = [m for m in query.model_numbers if code_key(m) in set(product.model_keys)]
    weak_hits = [m for m in query.model_numbers if code_key(m) in set(product.weak_model_keys)]
    identifier = s.upc or (s.model and match.brand_match)

    if s.upc:
        match.reasons.append(f"The barcode matches {label}.")
    if model_hits:
        brand = " and the brand" if match.brand_match else ""
        match.reasons.append(f"Model {', '.join(model_hits)}{brand} match {label}.")
    if weak_hits and not model_hits:
        match.reasons.append(f"Code {', '.join(weak_hits)} appears in {label}'s product table.")

    plausible = _plausible_purchase(product, query.purchase_date)
    window = _format_window(product)
    if plausible is True and window:
        match.reasons.append(f"Bought within the recall's sale period ({window}).")

    restricted_detail = [r.get("detail", "") for r in product.restrictions if r.get("detail")]
    if identifier:
        if product.unit_restricted and not s.lot:
            match.tier = Tier.CHECK_UNIT
            match.reasons.append("The recall covers only some units of this product.")
            match.what_to_check = restricted_detail + list(product.where_to_look)
        elif plausible is False:
            match.tier = Tier.CHECK_UNIT
            match.reasons.append(
                f"You bought it before the recalled units went on sale ({window}); "
                "check the label to be sure."
            )
            match.what_to_check = list(product.where_to_look) or restricted_detail
        else:
            match.tier = Tier.RECALLED
            if s.lot:
                match.reasons.append("Your lot code is one of the recalled lots.")
        return

    family_threshold = FAMILY_SIMILARITY_SAFETY_CRITICAL if safety_critical else FAMILY_SIMILARITY
    similar_name = s.vector_similarity >= family_threshold or s.trigram_similarity >= TRIGRAM_FAMILY
    if (
        (s.model and _any_distinctive(model_hits))
        or ((s.weak_model or s.lot) and match.brand_match)
        or (match.brand_match and similar_name)
    ):
        match.tier = Tier.CHECK_UNIT
        if match.brand_match and not (s.model or s.weak_model):
            match.reasons.append(f"Same brand, similar product to {label}.")
        if s.model and not match.brand_match:
            match.reasons.append("The model number matches, but we couldn't confirm the brand.")
        match.what_to_check = (
            (
                [f"Model numbers in this recall: {', '.join(product.model_numbers[:12])}"]
                if product.model_numbers
                else []
            )
            + restricted_detail
            + list(product.where_to_look)
        )


class _TokenFrequency:
    """How many recalled products mention a word (capped), to tell brands from common words."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[str, int] = {}

    def __call__(self, token: str) -> int:
        if token not in self._cache:
            q = func.plainto_tsquery("english", token)
            hits = (
                select(literal(1))
                .where(RecallProduct.search_text.op("@@")(q))
                .limit(FREQUENCY_CAP)
                .subquery()
            )
            self._cache[token] = self._session.scalar(select(func.count()).select_from(hits)) or 0
        return self._cache[token]


def _brand_match(
    query_brand: set[str], product: RecallProduct, recall: Recall, frequency: _TokenFrequency
) -> bool:
    """Does the query name the recalled product's brand or maker?"""
    named = brand_tokens([product.brand, recall.firm, product.manufacturer])
    # CPSC product names usually start with the brand ("YOLAAH Portable Bed Rails"), which can
    # differ from the firm ("Guangzhou Aowei Technology"). Common first words ("Multi-Point")
    # aren't brands, so the word must be rare across all recalls.
    first_word = set(tokens(product.product_name)[:1]) - GENERIC - named
    model_keys = set(product.model_keys)
    for token in query_brand:
        if code_key(token) in model_keys:
            continue  # a matched model number is already counted; it isn't also the brand
        # Containment covers brands inside company names: "Ninja" in "SharkNinja".
        if any(token == name or (len(token) >= 4 and token in name) for name in named):
            if frequency(token) <= MAX_BRAND_FREQUENCY:
                return True
        elif token in first_word and frequency(token) <= MAX_FIRST_WORD_FREQUENCY:
            return True
    return False


def _any_distinctive(models: list[str]) -> bool:
    return any(_distinctive_key(code_key(m)) for m in models)


def _query_is_specific(query: ProductQuery) -> bool:
    if query.upcs or query.model_numbers or query.brand:
        return True
    return len(distinctive_tokens(query.search_text())) >= 1


def check(
    session: Session,
    query: ProductQuery,
    *,
    embedding: list[float] | None,
    ingested: Sequence[RecallSource],
) -> CheckResult:
    """Check one product against every ingested recall."""
    notes = list(query.notes)
    has_input = bool(
        query.upcs or query.model_numbers or (query.search_text() and tokens(query.search_text()))
    )
    if not has_input:
        return CheckResult(Tier.UNIDENTIFIED, [], [], list(ingested), [], notes)

    signals = _retrieve(session, query, embedding)
    rows = session.execute(
        select(RecallProduct, Recall)
        .join(Recall, Recall.id == RecallProduct.recall_id)
        .where(RecallProduct.id.in_(list(signals)))
    ).all()

    query_brand = (
        brand_tokens([query.brand]) if query.brand else distinctive_tokens(query.search_text())
    )
    safety_critical_query = is_safety_critical(query.categories)
    frequency = _TokenFrequency(session)

    candidates: list[Match] = []
    for product, recall in rows:
        match = Match(
            product=product,
            recall=recall,
            tier=None,
            signals=signals[product.id],
            brand_match=_brand_match(query_brand, product, recall, frequency),
        )
        _score(match, query, safety_critical_query or product.safety_critical)
        match.what_to_check = list(dict.fromkeys(match.what_to_check))
        candidates.append(match)

    needed = sources_for(query.categories)
    uncovered = sorted(needed - set(ingested), key=list(RecallSource).index)
    if needed and not needed & set(ingested):
        # The product belongs to an agency we don't ingest yet (a car seat, bacon). A similar
        # name from another agency's recall is not evidence; only an identifier match is.
        for match in candidates:
            if not (match.signals.upc or match.signals.model):
                match.tier = None
                match.reasons.clear()
                match.what_to_check.clear()

    matches = sorted(
        (m for m in candidates if m.tier is not None),
        key=lambda m: (
            _SEVERITY.index(m.tier) if m.tier in _SEVERITY else 9,
            -m.signals.fused,
            -m.signals.vector_similarity,
        ),
    )
    # One entry per recall: several products of the same recall add nothing for the user.
    matches = _one_per_recall(matches)[:MAX_MATCHES]
    matched_recalls = {m.recall.id for m in matches}
    related = _one_per_recall(
        sorted(
            (
                m
                for m in candidates
                if m.tier is None
                and m.recall.id not in matched_recalls
                and max(m.signals.vector_similarity, m.signals.trigram_similarity)
                >= RELATED_SIMILARITY
            ),
            key=lambda m: -max(m.signals.vector_similarity, m.signals.trigram_similarity),
        )
    )[:MAX_RELATED]

    if matches:
        verdict = matches[0].tier or Tier.ALL_CLEAR
    elif uncovered:
        verdict = Tier.NOT_COVERED
    elif not _query_is_specific(query):
        verdict = Tier.UNIDENTIFIED
        notes.append("Add the brand or model number so we can check it precisely.")
    else:
        verdict = Tier.ALL_CLEAR
    return CheckResult(verdict, matches, related, list(ingested), uncovered, notes)


def embed_query(embedder: Embedder, query: ProductQuery) -> list[float] | None:
    """The query's embedding, or None when it has no words to embed (e.g. a bare barcode)."""
    text = query.search_text()
    return embedder.query(text) if tokens(text) else None


def _one_per_recall(matches: list[Match]) -> list[Match]:
    seen: set[int] = set()
    unique = []
    for match in matches:
        if match.recall.id not in seen:
            seen.add(match.recall.id)
            unique.append(match)
    return unique
