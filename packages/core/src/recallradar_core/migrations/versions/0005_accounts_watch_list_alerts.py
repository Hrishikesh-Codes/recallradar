"""Accounts (Better Auth tables, snake_case), user settings, watched items, matches, alerts.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_user",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("is_anonymous", sa.Boolean(), server_default=sa.text("false"), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_user")),
        sa.UniqueConstraint("email", name=op.f("uq_auth_user_email")),
    )
    op.create_table(
        "auth_verification",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_verification")),
    )
    op.create_index(
        op.f("ix_auth_verification_identifier"), "auth_verification", ["identifier"], unique=False
    )
    op.create_table(
        "auth_account",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("id_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_auth_account_user_id_auth_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_account")),
    )
    op.create_index(op.f("ix_auth_account_user_id"), "auth_account", ["user_id"], unique=False)
    op.create_table(
        "auth_session",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_auth_session_user_id_auth_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_session")),
        sa.UniqueConstraint("token", name=op.f("uq_auth_session_token")),
    )
    op.create_index(op.f("ix_auth_session_user_id"), "auth_session", ["user_id"], unique=False)
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("email_alerts", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "alert_tiers",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{recalled,check_unit}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_user_settings_user_id_auth_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_settings")),
    )
    op.create_table(
        "watch_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("input_type", sa.Text(), nullable=False),
        sa.Column("input_value", sa.Text(), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column(
            "last_checked_at",
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
            "input_type IN ('text', 'link', 'barcode')", name=op.f("ck_watch_item_input_type")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_watch_item_user_id_auth_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watch_item")),
    )
    op.create_index(
        op.f("ix_watch_item_user_id_created_at"),
        "watch_item",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "alert",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("recall_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.Text(), server_default="email", nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint("channel IN ('email')", name=op.f("ck_alert_channel")),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')", name=op.f("ck_alert_status")
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["watch_item.id"],
            name=op.f("fk_alert_item_id_watch_item"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recall_id"], ["recall.id"], name=op.f("fk_alert_recall_id_recall"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_alert_user_id_auth_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert")),
        sa.UniqueConstraint(
            "item_id", "recall_id", "channel", name=op.f("uq_alert_item_id_recall_id_channel")
        ),
    )
    op.create_index(op.f("ix_alert_user_id"), "alert", ["user_id"], unique=False)
    op.create_table(
        "watch_match",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("recall_id", sa.BigInteger(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "first_matched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["watch_item.id"],
            name=op.f("fk_watch_match_item_id_watch_item"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recall_id"],
            ["recall.id"],
            name=op.f("fk_watch_match_recall_id_recall"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watch_match")),
        sa.UniqueConstraint("item_id", "recall_id", name=op.f("uq_watch_match_item_id_recall_id")),
    )
    op.create_index(op.f("ix_watch_match_recall_id"), "watch_match", ["recall_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_watch_match_recall_id"), table_name="watch_match")
    op.drop_table("watch_match")
    op.drop_index(op.f("ix_alert_user_id"), table_name="alert")
    op.drop_table("alert")
    op.drop_index(op.f("ix_watch_item_user_id_created_at"), table_name="watch_item")
    op.drop_table("watch_item")
    op.drop_table("user_settings")
    op.drop_index(op.f("ix_auth_session_user_id"), table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_index(op.f("ix_auth_account_user_id"), table_name="auth_account")
    op.drop_table("auth_account")
    op.drop_index(op.f("ix_auth_verification_identifier"), table_name="auth_verification")
    op.drop_table("auth_verification")
    op.drop_table("auth_user")
