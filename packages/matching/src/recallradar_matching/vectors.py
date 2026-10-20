"""Product embeddings: nearest-neighbour search and writes, in whichever database holds them.

Production keeps them in a second Neon project (VECTOR_DATABASE_URL), because Neon's free plan
caps a database at 512 MiB. Locally and in tests they share the main database, and every
function here takes that database's session instead of a `VectorStore`.
"""

from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from recallradar_core.db import ProductVector

# HNSW candidates examined per query: recall@50 0.988 against exact search at 400 (M1).
EF_SEARCH = 400


def nearest(session: Session, embedding: list[float], limit: int) -> list[tuple[int, float]]:
    """(product id, cosine distance) of the closest products, nearest first."""
    session.execute(text(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}"))
    distance = ProductVector.embedding.cosine_distance(embedding)
    rows = session.execute(
        select(ProductVector.product_id, distance).order_by(distance).limit(limit)
    ).all()
    return [(product_id, float(dist)) for product_id, dist in rows]


def save(session: Session, vectors: Sequence[tuple[int, list[float]]]) -> None:
    """Insert or replace embeddings by product id."""
    if not vectors:
        return
    statement = insert(ProductVector).values(
        [{"product_id": product_id, "embedding": vector} for product_id, vector in vectors]
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[ProductVector.product_id],
            set_={"embedding": statement.excluded.embedding},
        )
    )


class VectorStore:
    """Embeddings in their own database."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def nearest(self, embedding: list[float], limit: int) -> list[tuple[int, float]]:
        with self.sessions.begin() as session:
            return nearest(session, embedding, limit)

    def save(self, vectors: Sequence[tuple[int, list[float]]]) -> None:
        with self.sessions.begin() as session:
            save(session, vectors)
