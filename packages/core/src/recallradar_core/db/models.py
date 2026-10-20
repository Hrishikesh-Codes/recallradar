"""Database schema. Mirrors SPEC §4.3; expect it to change once ingesters see real data (M1)."""

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from recallradar_core.db.base import Base, TimestampMixin, str_enum
from recallradar_core.enums import (
    ChunkSection,
    NoticeType,
    RecallSource,
    RecallStatus,
    RemedyType,
    SyncMode,
    SyncStatus,
)

# BAAI/bge-small-en-v1.5 output size. Stored as halfvec (2 bytes/dim): half the space of vector.
EMBEDDING_DIM = 384
NAME_PREFIX_CHARS = 200

_EMPTY_TEXT_ARRAY = text("'{}'::text[]")
_EMPTY_JSONB = text("'{}'::jsonb")
_EMPTY_JSONB_ARRAY = text("'[]'::jsonb")


class Recall(TimestampMixin, Base):
    __tablename__ = "recall"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[RecallSource] = mapped_column(str_enum(RecallSource, "source"))
    source_recall_id: Mapped[str]
    # Human-facing number: CPSC recall number ("26227") or FDA event ID ("99887").
    reference: Mapped[str | None]
    notice_type: Mapped[NoticeType] = mapped_column(
        str_enum(NoticeType, "notice_type"), server_default=NoticeType.RECALL.value
    )
    title: Mapped[str]
    description: Mapped[str | None]
    hazard: Mapped[str | None]
    remedy: Mapped[str | None]
    remedy_type: Mapped[RemedyType | None] = mapped_column(str_enum(RemedyType, "remedy_type"))
    recall_date: Mapped[date | None]
    # When the notice became public: CPSC recall date, FDA enforcement report date.
    published_date: Mapped[date | None]
    # Last-modified time as reported by the source, not by us.
    last_updated: Mapped[datetime | None]
    status: Mapped[RecallStatus] = mapped_column(
        str_enum(RecallStatus, "status"), server_default=RecallStatus.UNKNOWN.value
    )
    official_url: Mapped[str | None]
    firm: Mapped[str | None]
    # FDA hazard class: "Class I" (most serious) to "Class III".
    classification: Mapped[str | None]
    distribution: Mapped[str | None]
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
        Index(None, "published_date"),
    )


class RecallProduct(TimestampMixin, Base):
    __tablename__ = "recall_product"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    recall_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("recall.id", ondelete="CASCADE"), index=True
    )
    # FDA recall number ("H-1404-2026"); CPSC recall ID (one product per recall).
    source_product_id: Mapped[str]
    product_name: Mapped[str]
    brand: Mapped[str | None]
    manufacturer: Mapped[str | None]
    # Identifiers as printed, for display ...
    model_numbers: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    lot_codes: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    # ... and normalised for exact matching ("WD-123.a" -> "WD123A"). GTIN-14 for barcodes.
    upcs: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    model_keys: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    lot_keys: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    # Codes from flattened tables, column unknown: candidates only, never a confirmed match.
    weak_model_keys: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    sold_start_date: Mapped[date | None]
    sold_end_date: Mapped[date | None]
    retailers: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    category: Mapped[str | None]
    categories: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    safety_critical: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # True when only some lots/dates/serials are recalled: an identifier match is then
    # "check your unit", never "recalled" (SPEC §6.4).
    unit_restricted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    restrictions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=_EMPTY_JSONB_ARRAY
    )
    where_to_look: Mapped[list[str]] = mapped_column(server_default=_EMPTY_TEXT_ARRAY)
    quantity: Mapped[str | None]
    # Vehicles (NHTSA): normalised make and model ("HONDA", "CRV") and the recalled model years.
    # Vehicles are matched on these, not by name similarity, and aren't embedded.
    vehicle_make: Mapped[str | None]
    vehicle_model: Mapped[str | None]
    model_years: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), server_default=text("'{}'::smallint[]")
    )
    raw: Mapped[dict[str, Any] | None]
    content_hash: Mapped[str]
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
    # The embedding lives in ProductVector (possibly another database); this says whether it's
    # missing or stale (the embedded text changed). Vehicles are never embedded.
    needs_embedding: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    recall: Mapped[Recall] = relationship(back_populates="products")

    __table_args__ = (
        UniqueConstraint("recall_id", "source_product_id"),
        Index(None, "search_text", postgresql_using="gin"),
        Index(None, "upcs", postgresql_using="gin"),
        Index(None, "model_keys", postgresql_using="gin"),
        Index(None, "weak_model_keys", postgresql_using="gin"),
        Index(None, "lot_keys", postgresql_using="gin"),
        # Fuzzy name matching looks at the first 200 characters only (FDA descriptions run to
        # 2,000), which keeps this index small. Queries must use the same expression.
        Index(
            "ix_recall_product_name_prefix_trgm",
            text(f"left(product_name, {NAME_PREFIX_CHARS}) gin_trgm_ops"),
            postgresql_using="gin",
        ),
        Index(None, "vehicle_make", "vehicle_model"),
        Index(
            "ix_recall_product_brand_trgm",
            "brand",
            postgresql_using="gin",
            postgresql_ops={"brand": "gin_trgm_ops"},
        ),
    )


class ProductVector(Base):
    """A recall product's embedding, for nearest-neighbour search.

    Kept apart from `recall_product` so it can live in its own database (VECTOR_DATABASE_URL):
    Neon's free plan caps a database at 512 MiB, and vectors with their HNSW index are about
    160 MB of the total. Without that setting it is a table in the main database. No foreign
    key, since the product may be in another database; products are never deleted.
    """

    __tablename__ = "product_vector"

    product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    embedding: Mapped[list[float]] = mapped_column(HALFVEC(EMBEDDING_DIM))

    __table_args__ = (
        Index(
            "ix_product_vector_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
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


class BarcodeLookup(Base):
    """Cached product lookups by barcode (Open Food Facts), so a barcode is fetched once.

    `found` is false for barcodes the lookup service doesn't know; those are cached too, for
    less time (see recallradar_api.checking).
    """

    __tablename__ = "barcode_lookup"

    gtin14: Mapped[str] = mapped_column(primary_key=True)
    source: Mapped[str]
    found: Mapped[bool] = mapped_column(Boolean)
    product_name: Mapped[str | None]
    brand: Mapped[str | None]
    is_food: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Feedback(Base):
    """A user's answer about one match: "This is mine", "Not my product", "Already handled".

    Stored as a matching label (SPEC §6.7) with what was checked, never with who checked it.
    """

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    check_id: Mapped[str]
    recall_id: Mapped[int | None] = mapped_column(
        ForeignKey("recall.id", ondelete="SET NULL"), index=True
    )
    label: Mapped[str]
    tier_shown: Mapped[str | None]
    query: Mapped[dict[str, Any]] = mapped_column(server_default=_EMPTY_JSONB)

    __table_args__ = (
        CheckConstraint("label IN ('mine', 'not_mine', 'handled')", name="label"),
        UniqueConstraint("check_id", "recall_id"),
    )
