"""Embeddings in a separate database, as in production (a second Neon project)."""

from collections.abc import Callable

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from recallradar_core.db import ProductVector, RecallProduct
from recallradar_core.db.session import ensure_vector_schema
from recallradar_core.enums import RecallSource
from recallradar_identify.text import parse_text
from recallradar_matching.embed import Embedder, embed_missing
from recallradar_matching.engine import Tier, check, embed_query
from recallradar_matching.vectors import VectorStore

pytestmark = [pytest.mark.db, pytest.mark.model]


def test_check_finds_products_through_a_separate_vector_database(
    writable_database_url: str, create_database: Callable[[], str], embedder: Embedder
) -> None:
    main = create_engine(writable_database_url)
    vector_engine = create_engine(create_database())
    ensure_vector_schema(vector_engine)
    ensure_vector_schema(vector_engine)  # idempotent: the embed job runs it every time
    sessions = sessionmaker(bind=main, expire_on_commit=False)
    store = VectorStore(sessionmaker(bind=vector_engine, expire_on_commit=False))

    # Move every embedding to the vector database; the main one keeps none.
    with sessions.begin() as session:
        session.execute(text("TRUNCATE product_vector"))
        session.execute(text("UPDATE recall_product SET needs_embedding = vehicle_make IS NULL"))
    embedded = embed_missing(sessions, embedder, batch_size=64, vector_store=store)
    with sessions() as session:
        products = session.scalar(select(func.count()).where(RecallProduct.vehicle_make.is_(None)))
        assert session.scalar(select(func.count()).select_from(ProductVector)) == 0
        assert not session.scalar(select(func.bool_or(RecallProduct.needs_embedding)))
    with store.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ProductVector)) == embedded
    assert embedded == products

    # A description with no identifier: found by its meaning, from the other database.
    query = parse_text("Nuna Rava convertible car seat")
    with sessions() as session:
        result = check(
            session,
            query,
            embedding=embed_query(embedder, query),
            ingested=list(RecallSource),
            vector_store=store,
        )
    assert result.verdict is Tier.CHECK_UNIT
    assert [m.recall.source_recall_id for m in result.matches] == ["24C002000"]
    assert result.matches[0].signals.vector_similarity > 0.5
    main.dispose()
    vector_engine.dispose()
