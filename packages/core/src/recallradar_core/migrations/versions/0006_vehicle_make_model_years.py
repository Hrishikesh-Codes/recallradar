"""Vehicle columns for NHTSA recalls (normalised make and model, recalled model years), and VINs
as a watched-item input type.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recall_product", sa.Column("vehicle_make", sa.Text(), nullable=True))
    op.add_column("recall_product", sa.Column("vehicle_model", sa.Text(), nullable=True))
    op.add_column(
        "recall_product",
        sa.Column(
            "model_years",
            postgresql.ARRAY(sa.SmallInteger()),
            server_default=sa.text("'{}'::smallint[]"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_recall_product_vehicle_make_vehicle_model"),
        "recall_product",
        ["vehicle_make", "vehicle_model"],
        unique=False,
    )
    op.drop_constraint(op.f("ck_watch_item_input_type"), "watch_item", type_="check")
    op.create_check_constraint(
        op.f("ck_watch_item_input_type"),
        "watch_item",
        "input_type IN ('text', 'link', 'barcode', 'vin')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_watch_item_input_type"), "watch_item", type_="check")
    op.create_check_constraint(
        op.f("ck_watch_item_input_type"), "watch_item", "input_type IN ('text', 'link', 'barcode')"
    )
    op.drop_index(op.f("ix_recall_product_vehicle_make_vehicle_model"), table_name="recall_product")
    op.drop_column("recall_product", "model_years")
    op.drop_column("recall_product", "vehicle_model")
    op.drop_column("recall_product", "vehicle_make")
