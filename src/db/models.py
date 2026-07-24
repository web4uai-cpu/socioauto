"""SQLAlchemy ORM models for the core PostgreSQL schema.

Tables: users, social_accounts, campaigns, posts, analytics, subscriptions, invoices.
Mirrors config/db/migrations/001_init.sql — keep both in sync when the schema changes.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces the deprecated ``datetime.utcnow``)."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


JsonDocument = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # Nullable: invited/self-provisioned accounts may exist before a password is set.
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint("role IN ('owner','admin','editor','viewer')", name="ck_users_role"),
    )

    social_accounts: Mapped[list["SocialAccount"]] = relationship(back_populates="user")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="user")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")


class SocialAccount(Base):
    """A connected platform account (X, Instagram, LinkedIn, TikTok, Facebook)."""

    __tablename__ = "social_accounts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    # Never store raw secrets here — only a pointer into the secrets manager.
    credentials_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "platform IN ('x','instagram','linkedin','tiktok','facebook')",
            name="ck_social_accounts_platform",
        ),
    )

    user: Mapped["User"] = relationship(back_populates="social_accounts")
    posts: Mapped[list["Post"]] = relationship(back_populates="social_account")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(50), default="professional")
    cta: Mapped[str | None] = mapped_column(String(255))
    target_audience: Mapped[str | None] = mapped_column(String(255))
    platforms: Mapped[list] = mapped_column(JsonDocument, default=list)
    voice_guidelines: Mapped[dict] = mapped_column(JsonDocument, default=dict)
    # Full serialized CampaignState — source of truth for the agent pipeline. Post rows below
    # are a relational projection of this for analytics/reporting queries.
    state_json: Mapped[dict] = mapped_column(JsonDocument, default=dict)
    auto_publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','active','paused','completed',"
            "'pending_review','needs_revision','scheduled','published')",
            name="ck_campaigns_status",
        ),
    )

    user: Mapped["User"] = relationship(back_populates="campaigns")
    posts: Mapped[list["Post"]] = relationship(back_populates="campaign")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    # Nullable: campaign drafts are generated before a platform account is attached.
    social_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    media_refs: Mapped[dict] = mapped_column(JsonDocument, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    moderation_reasons: Mapped[dict] = mapped_column(JsonDocument, default=dict)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_post_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('draft','pending_moderation','approved','rejected',"
            "'scheduled','published','failed')",
            name="ck_posts_status",
        ),
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="posts")
    social_account: Mapped["SocialAccount"] = relationship(back_populates="posts")
    analytics: Mapped[list["Analytics"]] = relationship(back_populates="post")


class Analytics(Base):
    """Append-only performance snapshots per post — never update/delete rows."""

    __tablename__ = "analytics"

    id: Mapped[uuid.UUID] = _uuid_pk()
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    likes: Mapped[int] = mapped_column(BigInteger, default=0)
    shares: Mapped[int] = mapped_column(BigInteger, default=0)
    comments: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    post: Mapped["Post"] = relationship(back_populates="analytics")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tier: Mapped[str] = mapped_column(String(30), nullable=False, default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "tier IN ('free','starter','pro','agency','enterprise')",
            name="ck_subscriptions_tier",
        ),
        CheckConstraint(
            "status IN ('active','past_due','canceled','trialing')",
            name="ck_subscriptions_status",
        ),
    )

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="subscription")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = _uuid_pk()
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE")
    )
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(255))
    amount_due: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','open','paid','void','uncollectible')",
            name="ck_invoices_status",
        ),
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="invoices")


class AuditLog(Base):
    """Append-only audit trail of every state transition (who/what/when) for compliance.

    See docs/SYSTEM_DESIGN.md §5. Never update or delete rows.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    actor: Mapped[str] = mapped_column(String(320), nullable=False)  # email / system principal
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. campaign.approved
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JsonDocument, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
