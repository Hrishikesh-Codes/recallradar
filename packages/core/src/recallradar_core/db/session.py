from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from recallradar_core.db.base import Base
from recallradar_core.db.models import ProductVector
from recallradar_core.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: Neon suspends idle computes, which silently drops pooled connections.
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@lru_cache
def get_vector_engine() -> Engine | None:
    """The vector database, or None when the main database holds the vectors."""
    url = get_settings().vector_database_url
    return create_engine(url, pool_pre_ping=True, pool_size=5) if url else None


@lru_cache
def get_vector_sessionmaker() -> sessionmaker[Session] | None:
    engine = get_vector_engine()
    return sessionmaker(bind=engine, expire_on_commit=False) if engine else None


def ensure_vector_schema(engine: Engine) -> None:
    """Create the vector table in a separate vector database (idempotent).

    The main database gets the same table from its migrations; a vector database holds only
    this one table, so it has no migration history of its own.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.tables[ProductVector.__tablename__].create(connection, checkfirst=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """A session that commits on success and rolls back on any exception."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
