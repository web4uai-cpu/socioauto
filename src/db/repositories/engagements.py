"""Persistence for inbound engagements (mentions, comments, DMs)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Engagement


def record_inbound(
    db: Session,
    *,
    platform: str,
    external_id: str,
    kind: str,
    author: str | None,
    message: str,
) -> Engagement | None:
    """Store a newly received engagement.

    Returns None when `external_id` was already recorded — platforms redeliver webhooks, and
    a duplicate must not create a second reply-drafting job.
    """
    existing = db.execute(
        select(Engagement).where(Engagement.external_id == external_id)
    ).scalar_one_or_none()
    if existing is not None:
        return None

    engagement = Engagement(
        platform=platform,
        external_id=external_id,
        kind=kind,
        author=author,
        message=message,
    )
    db.add(engagement)
    db.commit()
    db.refresh(engagement)
    return engagement


def get(db: Session, engagement_id: uuid.UUID) -> Engagement | None:
    return db.get(Engagement, engagement_id)


def pending(db: Session, limit: int = 100) -> list[Engagement]:
    return list(
        db.execute(
            select(Engagement)
            .where(Engagement.status == "pending")
            .order_by(Engagement.received_at)
            .limit(limit)
        )
        .scalars()
        .all()
    )


def save_draft(
    db: Session, engagement: Engagement, *, draft: str | None, escalated: bool
) -> Engagement:
    """Attach a drafted reply. Escalated items are held for a human rather than auto-sent."""
    engagement.draft_response = draft
    engagement.escalated = escalated
    engagement.status = "escalated" if escalated else "drafted"
    engagement.processed_at = datetime.now(UTC)
    db.commit()
    db.refresh(engagement)
    return engagement
