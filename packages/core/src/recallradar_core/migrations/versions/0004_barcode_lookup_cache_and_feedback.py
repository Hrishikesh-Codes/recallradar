"""Barcode lookup cache (Open Food Facts results) and match feedback labels.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "barcode_lookup",
        sa.Column("gtin14", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("found", sa.Boolean(), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("is_food", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("gtin14", name=op.f("pk_barcode_lookup")),
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("check_id", sa.Text(), nullable=False),
        sa.Column("recall_id", sa.BigInteger(), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("tier_shown", sa.Text(), nullable=True),
        sa.Column(
            "query",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "label IN ('mine', 'not_mine', 'handled')", name=op.f("ck_feedback_label")
        ),
        sa.ForeignKeyConstraint(
            ["recall_id"],
            ["recall.id"],
            name=op.f("fk_feedback_recall_id_recall"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback")),
        sa.UniqueConstraint("check_id", "recall_id", name=op.f("uq_feedback_check_id_recall_id")),
    )
    op.create_index(op.f("ix_feedback_recall_id"), "feedback", ["recall_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_feedback_recall_id"), table_name="feedback")
    op.drop_table("feedback")
    op.drop_table("barcode_lookup")
