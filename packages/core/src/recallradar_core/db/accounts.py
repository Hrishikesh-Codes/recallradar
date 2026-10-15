"""Accounts, watched items, and alerts.

The auth_* tables belong to Better Auth, which runs in the web app (apps/web/src/lib/auth.ts maps
its camelCase fields to these snake_case columns). They live here so Alembic is the one place
the schema is defined. Deleting an auth_user row deletes everything of theirs (SPEC §2.9).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from recallradar_core.db.base import Base, TimestampMixin

_EMPTY_JSONB = text("'{}'::jsonb")
_EMPTY_JSONB_ARRAY = text("'[]'::jsonb")


def _user_fk() -> ForeignKey:
    """A ForeignKey object belongs to one column, so each column gets its own."""
    return ForeignKey("auth_user.id", ondelete="CASCADE")


class AuthUser(Base):
    __tablename__ = "auth_user"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    image: Mapped[str | None]
    # "Try the demo" visitors get a private anonymous account; it never receives email.
    is_anonymous: Mapped[bool | None] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_session"

    id: Mapped[str] = mapped_column(primary_key=True)
    expires_at: Mapped[datetime]
    token: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime]
    ip_address: Mapped[str | None]
    user_agent: Mapped[str | None]
    user_id: Mapped[str] = mapped_column(_user_fk(), index=True)


class AuthAccount(Base):
    __tablename__ = "auth_account"

    id: Mapped[str] = mapped_column(primary_key=True)
    account_id: Mapped[str]
    provider_id: Mapped[str]
    user_id: Mapped[str] = mapped_column(_user_fk(), index=True)
    access_token: Mapped[str | None]
    refresh_token: Mapped[str | None]
    id_token: Mapped[str | None]
    access_token_expires_at: Mapped[datetime | None]
    refresh_token_expires_at: Mapped[datetime | None]
    scope: Mapped[str | None]
    password: Mapped[str | None]  # unused: sign-in is magic link only
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime]


class AuthVerification(Base):
    """Pending magic links."""

    __tablename__ = "auth_verification"

    id: Mapped[str] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(index=True)
    value: Mapped[str]
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(_user_fk(), primary_key=True)
    email_alerts: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # Which verdicts trigger an alert (SPEC §8: configurable per tier).
    alert_tiers: Mapped[list[str]] = mapped_column(
        server_default=text("'{recalled,check_unit}'::text[]")
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class WatchItem(TimestampMixin, Base):
    """Something a user owns and wants watched. Re-checked whenever new recalls arrive."""

    __tablename__ = "watch_item"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(_user_fk())
    label: Mapped[str]
    input_type: Mapped[str]
    # What the user typed, pasted, or scanned: re-parsed on every re-check, so better parsing
    # helps old items too.
    input_value: Mapped[str]
    purchase_date: Mapped[date | None]
    verdict: Mapped[str]
    last_checked_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint("input_type IN ('text', 'link', 'barcode', 'vin')", name="input_type"),
        Index(None, "user_id", "created_at"),
    )


class WatchMatch(Base):
    """A recall currently matching a watched item. `dismissed_at` is set by "Not my product"."""

    __tablename__ = "watch_match"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("watch_item.id", ondelete="CASCADE"))
    recall_id: Mapped[int] = mapped_column(ForeignKey("recall.id", ondelete="CASCADE"), index=True)
    tier: Mapped[str]
    reasons: Mapped[list[Any]] = mapped_column(JSONB, server_default=_EMPTY_JSONB_ARRAY)
    first_matched_at: Mapped[datetime] = mapped_column(server_default=func.now())
    dismissed_at: Mapped[datetime | None]

    __table_args__ = (UniqueConstraint("item_id", "recall_id"),)


class Alert(Base):
    """One alert per item per recall per channel (SPEC §8), enforced by a unique constraint."""

    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(_user_fk(), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("watch_item.id", ondelete="CASCADE"))
    recall_id: Mapped[int] = mapped_column(ForeignKey("recall.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(server_default="email")
    tier: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sent_at: Mapped[datetime | None]
    provider_message_id: Mapped[str | None]
    error: Mapped[str | None]
    details: Mapped[dict[str, Any]] = mapped_column(server_default=_EMPTY_JSONB)

    __table_args__ = (
        UniqueConstraint("item_id", "recall_id", "channel"),
        CheckConstraint("channel IN ('email')", name="channel"),
        CheckConstraint("status IN ('pending', 'sent', 'failed', 'skipped')", name="status"),
    )
