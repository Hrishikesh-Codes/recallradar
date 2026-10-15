"""Web Push subscriptions, and "push" as an alert channel.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_subscription",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_push_subscription_user_id_auth_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_subscription")),
        sa.UniqueConstraint("endpoint", name=op.f("uq_push_subscription_endpoint")),
    )
    op.create_index(
        op.f("ix_push_subscription_user_id"), "push_subscription", ["user_id"], unique=False
    )

    op.drop_constraint(op.f("ck_alert_channel"), "alert", type_="check")
    op.create_check_constraint(op.f("ck_alert_channel"), "alert", "channel IN ('email', 'push')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_alert_channel"), "alert", type_="check")
    op.create_check_constraint(op.f("ck_alert_channel"), "alert", "channel IN ('email')")
    op.drop_index(op.f("ix_push_subscription_user_id"), table_name="push_subscription")
    op.drop_table("push_subscription")
