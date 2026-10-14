"""Fields the real CPSC and openFDA data called for: identifiers keyed for exact matching,
unit restrictions, notice type, FDA classification, and per-product raw records.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13 16:57:56.915274
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recall", sa.Column("reference", sa.Text(), nullable=True))
    op.add_column(
        "recall",
        sa.Column(
            "notice_type",
            sa.Enum(
                "recall",
                "warning",
                name="notice_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            server_default="recall",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_recall_notice_type"), "recall", "notice_type IN ('recall', 'warning')"
    )
    op.add_column("recall", sa.Column("published_date", sa.Date(), nullable=True))
    op.add_column("recall", sa.Column("firm", sa.Text(), nullable=True))
    op.add_column("recall", sa.Column("classification", sa.Text(), nullable=True))
    op.add_column("recall", sa.Column("distribution", sa.Text(), nullable=True))
    op.create_index(op.f("ix_recall_published_date"), "recall", ["published_date"], unique=False)
    # NOT NULL without a default is safe: no environment held recall data before this migration.
    op.add_column("recall_product", sa.Column("source_product_id", sa.Text(), nullable=False))
    op.add_column(
        "recall_product",
        sa.Column(
            "model_keys",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "recall_product",
        sa.Column(
            "lot_keys",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "recall_product",
        sa.Column(
            "weak_model_keys",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "recall_product",
        sa.Column(
            "categories",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "recall_product",
        sa.Column("safety_critical", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "recall_product",
        sa.Column("unit_restricted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "recall_product",
        sa.Column(
            "restrictions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "recall_product",
        sa.Column(
            "where_to_look",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column("recall_product", sa.Column("quantity", sa.Text(), nullable=True))
    op.add_column(
        "recall_product", sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column("recall_product", sa.Column("content_hash", sa.Text(), nullable=False))
    op.drop_index(
        op.f("ix_recall_product_model_numbers"), table_name="recall_product", postgresql_using="gin"
    )
    op.create_index(
        op.f("ix_recall_product_lot_keys"),
        "recall_product",
        ["lot_keys"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_recall_product_model_keys"),
        "recall_product",
        ["model_keys"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_recall_product_weak_model_keys"),
        "recall_product",
        ["weak_model_keys"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_unique_constraint(
        op.f("uq_recall_product_recall_id_source_product_id"),
        "recall_product",
        ["recall_id", "source_product_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_recall_product_recall_id_source_product_id"), "recall_product", type_="unique"
    )
    op.drop_index(
        op.f("ix_recall_product_weak_model_keys"),
        table_name="recall_product",
        postgresql_using="gin",
    )
    op.drop_index(
        op.f("ix_recall_product_model_keys"), table_name="recall_product", postgresql_using="gin"
    )
    op.drop_index(
        op.f("ix_recall_product_lot_keys"), table_name="recall_product", postgresql_using="gin"
    )
    op.create_index(
        op.f("ix_recall_product_model_numbers"),
        "recall_product",
        ["model_numbers"],
        unique=False,
        postgresql_using="gin",
    )
    op.drop_column("recall_product", "content_hash")
    op.drop_column("recall_product", "raw")
    op.drop_column("recall_product", "quantity")
    op.drop_column("recall_product", "where_to_look")
    op.drop_column("recall_product", "restrictions")
    op.drop_column("recall_product", "unit_restricted")
    op.drop_column("recall_product", "safety_critical")
    op.drop_column("recall_product", "categories")
    op.drop_column("recall_product", "weak_model_keys")
    op.drop_column("recall_product", "lot_keys")
    op.drop_column("recall_product", "model_keys")
    op.drop_column("recall_product", "source_product_id")
    op.drop_index(op.f("ix_recall_published_date"), table_name="recall")
    op.drop_column("recall", "distribution")
    op.drop_column("recall", "classification")
    op.drop_column("recall", "firm")
    op.drop_column("recall", "published_date")
    op.drop_constraint(op.f("ck_recall_notice_type"), "recall", type_="check")
    op.drop_column("recall", "notice_type")
    op.drop_column("recall", "reference")
