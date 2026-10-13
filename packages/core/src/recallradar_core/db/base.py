from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Date, DateTime, Enum, MetaData, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint/index names, so Alembic migrations are deterministic across environments.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy reads this as a class attribute
        str: Text(),
        date: Date(),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB(),
        list[str]: ARRAY(Text()),
    }


def str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Store a StrEnum as text guarded by a CHECK constraint (no native Postgres ENUM type)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
