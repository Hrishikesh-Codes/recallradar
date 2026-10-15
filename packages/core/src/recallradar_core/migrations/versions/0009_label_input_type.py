"""Label photos (their OCR text) as a watched-item input type.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_watch_item_input_type"), "watch_item", type_="check")
    op.create_check_constraint(
        op.f("ck_watch_item_input_type"),
        "watch_item",
        "input_type IN ('text', 'link', 'barcode', 'vin', 'label')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_watch_item_input_type"), "watch_item", type_="check")
    op.create_check_constraint(
        op.f("ck_watch_item_input_type"),
        "watch_item",
        "input_type IN ('text', 'link', 'barcode', 'vin')",
    )
