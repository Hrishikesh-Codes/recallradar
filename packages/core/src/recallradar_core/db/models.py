"""Database schema. Mirrors SPEC §4.3; expect it to change once ingesters see real data (M1)."""

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    BigInteger,
    Computed,
    ForeignKey,
    Identity,
    Index,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from recallradar_core.db.base import Base, TimestampMixin, str_enum
from recallradar_core.enums import (
    ChunkSection,
    RecallSource,
    RecallStatus,
    RemedyType,
    SyncMode,
    SyncStatus,
)

# BAAI/bge-small-en-v1.5 output size. Stored as halfvec (2 bytes/dim) to fit Neon's 0.5 GB tier.
EMBEDDING_DIM = 384

_EMPTY_TEXT_ARRAY = text("'{}'::text[]")
_EMPTY_JSONB = text("'{}'::jsonb")


class Recall(TimestampMixin, Base):
    __tablename__ = "recall"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[RecallSource] = mapped_column(str_enum(RecallSource, "source"))
    source_recall_id: Mapped[str]
    title: Mapped[str]
    description: Mapped[str | None]
    hazard: Mapped[str | None]
    remedy: Mapped[str | None]
    remedy_type: Mapped[RemedyType | None] = mapped_column(str_enum(RemedyType, "remedy_type"))
    recall_date: Mapped[date | None]
    # Last-modified time as reported by the source, not by us.
    last_updated: Mapped[datetime | None]
    status: Mapped[RecallStatus] = mapped_column(
        str_enum(RecallStatus, "status"), server_default=RecallStatus.UNKNOWN.value
    )
    official_url: Mapped[str | None]
    raw: Mapped[dict[str, Any]]
    # sha256 of the canonicalised raw record: an upsert with the same hash is a no-op.
    content_hash: Mapped[str]
    # When our sync first saw this recall; recall_date -> first_seen_at is the freshness metric.
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())

    products: Mapped[list["RecallProduct"]] = relationship(
        back_populates="recall", cascade="all, delete-orphan", passive_deletes=True
    )
    chunks: Mapped[list["RecallChunk"]] = relationship(
        back_populates="recall", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("source", "source_recall_id"),
        Index(None, "recall_date"),
    )


class RecallProduct(TimestampMixin, Base):
    __tablename__ = "recall_product"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    recall_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("recall.id", ondelete="CASCADE"), index=True
    )
    product_name: Mapped[str]
    brand: Mapped[str | None]
    manufacturer: Mapped[str | None]
    model_numbers: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    upcs: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    lot_codes: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    sold_start_date: Mapped[date | None]
    sold_end_date: Mapped[date | None]
    retailers: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    category: Mapped[str | None]
    search_text: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(brand, '')), 'A')"
            " || setweight(to_tsvector('english', product_name), 'A')"
            " || setweight(to_tsvector('english', coalesce(manufacturer, '')), 'B')"
            " || setweight(to_tsvector('english', coalesce(category, '')), 'C')",
            persisted=True,
        ),
    )
    embedding: Mapped[list[float] | None] = mapped_column(HALFVEC(EMBEDDING_DIM))

    recall: Mapped[Recall] = relationship(back_populates="products")

    __table_args__ = (
        Index(None, "search_text", postgresql_using="gin"),
        Index(None, "model_numbers", postgresql_using="gin"),
        Index(None, "upcs", postgresql_using="gin"),
        Index(
            "ix_recall_product_product_name_trgm",
            "product_name",
            postgresql_using="gin",
            postgresql_ops={"product_name": "gin_trgm_ops"},
        ),
        Index(
            "ix_recall_product_brand_trgm",
            "brand",
            postgresql_using="gin",
            postgresql_ops={"brand": "gin_trgm_ops"},
        ),
    )


class RecallChunk(TimestampMixin, Base):
    """A passage of official recall text, the unit of retrieval for Ask (SPEC §7)."""

    __tablename__ = "recall_chunk"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    recall_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("recall.id", ondelete="CASCADE"), index=True
    )
    section: Mapped[ChunkSection] = mapped_column(str_enum(ChunkSection, "section"))
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str]
    search_text: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', text)", persisted=True)
    )
    embedding: Mapped[list[float] | None] = mapped_column(HALFVEC(EMBEDDING_DIM))

    recall: Mapped[Recall] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("recall_id", "section", "ordinal"),
        Index(None, "search_text", postgresql_using="gin"),
    )


class SyncRun(Base):
    """One ingester run; the admin health page and freshness metrics read from here."""

    __tablename__ = "sync_run"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[RecallSource] = mapped_column(str_enum(RecallSource, "source"))
    mode: Mapped[SyncMode] = mapped_column(str_enum(SyncMode, "mode"))
    status: Mapped[SyncStatus] = mapped_column(
        str_enum(SyncStatus, "status"), server_default=SyncStatus.RUNNING.value
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    fetched: Mapped[int] = mapped_column(server_default="0")
    inserted: Mapped[int] = mapped_column(server_default="0")
    updated: Mapped[int] = mapped_column(server_default="0")
    unchanged: Mapped[int] = mapped_column(server_default="0")
    error: Mapped[str | None]
    details: Mapped[dict[str, Any]] = mapped_column(server_default=_EMPTY_JSONB)

    __table_args__ = (Index(None, "source", "started_at"),)


class Event(Base):
    """Append-only product/usage events, the raw material for the README's metrics (SPEC §14)."""

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
    name: Mapped[str]
    anonymous_id: Mapped[str | None]
    properties: Mapped[dict[str, Any]] = mapped_column(server_default=_EMPTY_JSONB)

    __table_args__ = (Index(None, "name", "occurred_at"),)
