"""Analytics rollups computed with real relational queries over the Post projection."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import Campaign, Post


def dashboard_for_user(db: Session, user_id: uuid.UUID) -> dict[str, int]:
    total_campaigns = db.execute(
        select(func.count(Campaign.id)).where(Campaign.user_id == user_id)
    ).scalar_one()

    def _count(*conditions) -> int:
        stmt = (
            select(func.count(Post.id))
            .join(Campaign, Post.campaign_id == Campaign.id)
            .where(Campaign.user_id == user_id, *conditions)
        )
        return db.execute(stmt).scalar_one()

    return {
        "total_campaigns": int(total_campaigns),
        "total_posts": _count(),
        "published_posts": _count(Post.status == "published"),
        "pending_moderation": _count(Post.status == "pending_moderation"),
        "rejected_posts": _count(Post.status == "rejected"),
    }
