"""The migrations are the production schema; these tests keep them honest against the models."""

from collections.abc import Callable, Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from recallradar_core.db import EMBEDDING_DIM, Base, Recall, RecallProduct
from recallradar_core.db.migrate import alembic_config
from recallradar_core.enums import RecallSource

pytestmark = pytest.mark.db


@pytest.fixture
def engine(migrated_database_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after the test."""
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


def _recall(source_recall_id: str = "24-123", **overrides: object) -> Recall:
    fields: dict[str, object] = {
        "source": RecallSource.CPSC,
        "source_recall_id": source_recall_id,
        "title": "Example rocker recalled due to suffocation hazard",
        "raw": {"RecallID": source_recall_id},
        "content_hash": "0" * 64,
    }
    fields.update(overrides)
    return Recall(**fields)


def _product(**overrides: object) -> RecallProduct:
    fields: dict[str, object] = {
        "source_product_id": "1",
        "product_name": "Infant Sleeper Rocker",
        "content_hash": "0" * 64,
    }
    fields.update(overrides)
    return RecallProduct(**fields)


def test_models_match_migrations(engine: Engine) -> None:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_downgrade_to_base_and_upgrade_again(create_database: Callable[[], str]) -> None:
    config = alembic_config(create_database())
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_source_recall_id_is_unique_per_source(session: Session) -> None:
    session.add(_recall())
    session.flush()
    session.add(_recall())
    with pytest.raises(IntegrityError):
        session.flush()


def test_the_same_id_may_exist_in_two_sources(session: Session) -> None:
    session.add_all([_recall(), _recall(source=RecallSource.FDA_FOOD)])
    session.flush()


def test_unknown_source_is_rejected_by_the_database(session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_recall_source"):
        session.execute(
            text(
                "INSERT INTO recall (source, source_recall_id, title, raw, content_hash)"
                " VALUES ('walmart', '1', 't', '{}', 'h')"
            )
        )


def test_product_search_text_and_embedding_roundtrip(session: Session) -> None:
    recall = _recall()
    recall.products.append(
        _product(brand="Example Brand", model_keys=["FP1234"], embedding=[0.5] * EMBEDDING_DIM)
    )
    session.add(recall)
    session.flush()

    matched = session.scalar(
        select(RecallProduct.id).where(
            RecallProduct.search_text.op("@@")(text("websearch_to_tsquery('english', 'rockers')"))
        )
    )
    assert matched == recall.products[0].id

    stored = session.scalar(select(RecallProduct.embedding))
    assert stored == [0.5] * EMBEDDING_DIM
    assert session.scalar(select(RecallProduct.model_keys)) == ["FP1234"]
    assert session.scalar(select(RecallProduct.restrictions)) == []


def test_deleting_a_recall_deletes_its_products(session: Session) -> None:
    recall = _recall()
    recall.products.append(_product(product_name="Rocker"))
    session.add(recall)
    session.flush()

    session.execute(text("DELETE FROM recall WHERE id = :id"), {"id": recall.id})
    assert session.scalar(text("SELECT count(*) FROM recall_product")) == 0
