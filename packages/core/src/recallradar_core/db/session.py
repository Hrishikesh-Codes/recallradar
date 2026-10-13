from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from recallradar_core.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: Neon suspends idle computes, which silently drops pooled connections.
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


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
