"""Initial schema: recalls, products, RAG chunks, sync runs, and usage events.

Revision ID: 0001
Revises:
Create Date: 2026-10-13 15:04:56.635404
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector for embeddings, pg_trgm for fuzzy brand/name matching. Left in place on downgrade.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "event",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("anonymous_id", sa.Text(), nullable=True),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event")),
    )
    op.create_index(
        op.f("ix_event_name_occurred_at"), "event", ["name", "occurred_at"], unique=False
    )
    op.create_table(
        "recall",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "cpsc",
                "fda_food",
                "fda_drug",
                "fda_device",
                "fsis",
                "nhtsa",
                name="source",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("source_recall_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hazard", sa.Text(), nullable=True),
        sa.Column("remedy", sa.Text(), nullable=True),
        sa.Column(
            "remedy_type",
            sa.Enum(
                "refund",
                "repair",
                "replace",
                "dispose",
                "other",
                name="remedy_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("recall_date", sa.Date(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "ongoing",
                "completed",
                "terminated",
                "unknown",
                name="status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "remedy_type IN ('refund', 'repair', 'replace', 'dispose', 'other')",
            name=op.f("ck_recall_remedy_type"),
        ),
        sa.CheckConstraint(
            "source IN ('cpsc', 'fda_food', 'fda_drug', 'fda_device', 'fsis', 'nhtsa')",
            name=op.f("ck_recall_source"),
        ),
        sa.CheckConstraint(
            "status IN ('ongoing', 'completed', 'terminated', 'unknown')",
            name=op.f("ck_recall_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recall")),
        sa.UniqueConstraint(
            "source", "source_recall_id", name=op.f("uq_recall_source_source_recall_id")
        ),
    )
    op.create_index(op.f("ix_recall_recall_date"), "recall", ["recall_date"], unique=False)
    op.create_table(
        "sync_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "cpsc",
                "fda_food",
                "fda_drug",
                "fda_device",
                "fsis",
                "nhtsa",
                name="source",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.Enum(
                "backfill",
                "incremental",
                name="mode",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "succeeded",
                "failed",
                name="status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            server_default="running",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inserted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint("mode IN ('backfill', 'incremental')", name=op.f("ck_sync_run_mode")),
        sa.CheckConstraint(
            "source IN ('cpsc', 'fda_food', 'fda_drug', 'fda_device', 'fsis', 'nhtsa')",
            name=op.f("ck_sync_run_source"),
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')", name=op.f("ck_sync_run_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_run")),
    )
    op.create_index(
        op.f("ix_sync_run_source_started_at"), "sync_run", ["source", "started_at"], unique=False
    )
    op.create_table(
        "recall_chunk",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("recall_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "section",
            sa.Enum(
                "summary",
                "hazard",
                "remedy",
                "products",
                "how_to_identify",
                "other",
                name="section",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "search_text",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=False,
        ),
        sa.Column("embedding", pgvector.sqlalchemy.halfvec.HALFVEC(dim=384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "section IN ('summary', 'hazard', 'remedy', 'products', 'how_to_identify', 'other')",
            name=op.f("ck_recall_chunk_section"),
        ),
        sa.ForeignKeyConstraint(
            ["recall_id"],
            ["recall.id"],
            name=op.f("fk_recall_chunk_recall_id_recall"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recall_chunk")),
        sa.UniqueConstraint(
            "recall_id",
            "section",
            "ordinal",
            name=op.f("uq_recall_chunk_recall_id_section_ordinal"),
        ),
    )
    op.create_index(op.f("ix_recall_chunk_recall_id"), "recall_chunk", ["recall_id"], unique=False)
    op.create_index(
        op.f("ix_recall_chunk_search_text"),
        "recall_chunk",
        ["search_text"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "recall_product",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("recall_id", sa.BigInteger(), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("manufacturer", sa.Text(), nullable=True),
        sa.Column(
            "model_numbers",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "upcs",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "lot_codes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("sold_start_date", sa.Date(), nullable=True),
        sa.Column("sold_end_date", sa.Date(), nullable=True),
        sa.Column(
            "retailers",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column(
            "search_text",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(brand, '')), 'A') || setweight(to_tsvector('english', product_name), 'A') || setweight(to_tsvector('english', coalesce(manufacturer, '')), 'B') || setweight(to_tsvector('english', coalesce(category, '')), 'C')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("embedding", pgvector.sqlalchemy.halfvec.HALFVEC(dim=384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["recall_id"],
            ["recall.id"],
            name=op.f("fk_recall_product_recall_id_recall"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recall_product")),
    )
    op.create_index(
        "ix_recall_product_brand_trgm",
        "recall_product",
        ["brand"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"brand": "gin_trgm_ops"},
    )
    op.create_index(
        op.f("ix_recall_product_model_numbers"),
        "recall_product",
        ["model_numbers"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_recall_product_product_name_trgm",
        "recall_product",
        ["product_name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"product_name": "gin_trgm_ops"},
    )
    op.create_index(
        op.f("ix_recall_product_recall_id"), "recall_product", ["recall_id"], unique=False
    )
    op.create_index(
        op.f("ix_recall_product_search_text"),
        "recall_product",
        ["search_text"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_recall_product_upcs"),
        "recall_product",
        ["upcs"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_recall_product_upcs"), table_name="recall_product", postgresql_using="gin"
    )
    op.drop_index(
        op.f("ix_recall_product_search_text"), table_name="recall_product", postgresql_using="gin"
    )
    op.drop_index(op.f("ix_recall_product_recall_id"), table_name="recall_product")
    op.drop_index(
        "ix_recall_product_product_name_trgm",
        table_name="recall_product",
        postgresql_using="gin",
        postgresql_ops={"product_name": "gin_trgm_ops"},
    )
    op.drop_index(
        op.f("ix_recall_product_model_numbers"), table_name="recall_product", postgresql_using="gin"
    )
    op.drop_index(
        "ix_recall_product_brand_trgm",
        table_name="recall_product",
        postgresql_using="gin",
        postgresql_ops={"brand": "gin_trgm_ops"},
    )
    op.drop_table("recall_product")
    op.drop_index(
        op.f("ix_recall_chunk_search_text"), table_name="recall_chunk", postgresql_using="gin"
    )
    op.drop_index(op.f("ix_recall_chunk_recall_id"), table_name="recall_chunk")
    op.drop_table("recall_chunk")
    op.drop_index(op.f("ix_sync_run_source_started_at"), table_name="sync_run")
    op.drop_table("sync_run")
    op.drop_index(op.f("ix_recall_recall_date"), table_name="recall")
    op.drop_table("recall")
    op.drop_index(op.f("ix_event_name_occurred_at"), table_name="event")
    op.drop_table("event")
