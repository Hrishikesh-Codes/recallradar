"""Search indexes sized for Neon's free tier: trigram on the first 200 characters of product
names (FDA descriptions run to 2,000), and an HNSW index for embedding search.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_recall_product_product_name_trgm", table_name="recall_product")
    op.execute(
        "CREATE INDEX ix_recall_product_name_prefix_trgm ON recall_product "
        "USING gin (left(product_name, 200) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_recall_product_embedding_hnsw ON recall_product "
        "USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_index("ix_recall_product_embedding_hnsw", table_name="recall_product")
    op.drop_index("ix_recall_product_name_prefix_trgm", table_name="recall_product")
    op.execute(
        "CREATE INDEX ix_recall_product_product_name_trgm ON recall_product "
        "USING gin (product_name gin_trgm_ops)"
    )
