"""Product embeddings move to their own table, which can live in a separate database.

Neon's free plan caps a database at 512 MiB and the full dataset is about 530 MB, of which the
vectors and their HNSW index are about 160 MB. `product_vector` holds them here, or in the
database at VECTOR_DATABASE_URL; `recall_product.needs_embedding` replaces "embedding IS NULL".

Existing vectors are copied, so a local database needn't be re-embedded. Run VACUUM FULL
afterwards to give back the dropped column's space.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.create_table(
        "product_vector",
        sa.Column("product_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.HALFVEC(dim=EMBEDDING_DIM), nullable=False),
        sa.PrimaryKeyConstraint("product_id", name=op.f("pk_product_vector")),
    )
    op.execute(
        "INSERT INTO product_vector (product_id, embedding)"
        " SELECT id, embedding FROM recall_product WHERE embedding IS NOT NULL"
    )
    # Parallel index builds use shared memory, which Docker caps at 64 MB by default: the
    # local database fails with "could not resize shared memory segment".
    op.execute("SET LOCAL max_parallel_maintenance_workers = 0")
    op.create_index(
        "ix_product_vector_embedding_hnsw",
        "product_vector",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "halfvec_cosine_ops"},
    )
    # Added as false (no table rewrite), then only the rows still waiting are marked; new rows
    # default to true.
    op.add_column(
        "recall_product",
        sa.Column("needs_embedding", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(
        "UPDATE recall_product SET needs_embedding = true"
        " WHERE embedding IS NULL AND vehicle_make IS NULL"
    )
    op.alter_column("recall_product", "needs_embedding", server_default=sa.text("true"))
    op.drop_index(
        "ix_recall_product_embedding_hnsw",
        table_name="recall_product",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "halfvec_cosine_ops"},
    )
    op.drop_column("recall_product", "embedding")


def downgrade() -> None:
    op.add_column(
        "recall_product",
        sa.Column("embedding", pgvector.sqlalchemy.HALFVEC(dim=EMBEDDING_DIM), nullable=True),
    )
    op.execute(
        "UPDATE recall_product p SET embedding = v.embedding"
        " FROM product_vector v WHERE v.product_id = p.id AND NOT p.needs_embedding"
    )
    op.create_index(
        "ix_recall_product_embedding_hnsw",
        "recall_product",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "halfvec_cosine_ops"},
    )
    op.drop_column("recall_product", "needs_embedding")
    op.drop_index(
        "ix_product_vector_embedding_hnsw",
        table_name="product_vector",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "halfvec_cosine_ops"},
    )
    op.drop_table("product_vector")
