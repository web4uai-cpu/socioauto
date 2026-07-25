"""Analytics rollups computed with real relational queries over the Post projection."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.analytics.insights import build_recommendations, summarize
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

    rollup = {
        "total_campaigns": int(total_campaigns),
        "total_posts": _count(),
        "published_posts": _count(Post.status == "published"),
        "pending_moderation": _count(Post.status == "pending_moderation"),
        "rejected_posts": _count(Post.status == "rejected"),
    }
    rollup.update(performance_for_user(db, user_id))
    return rollup


def performance_for_user(db: Session, user_id: uuid.UUID) -> dict:
    """Aggregate measured engagement and recommendations across a user's campaigns.

    Reads from each campaign's persisted `state_json` rather than the `analytics` table:
    `_project_posts` deletes and re-creates Post rows on every save, and `Analytics.post_id`
    cascades, so rows written there would be destroyed by the next campaign write despite the
    table being documented append-only. Fixing that needs stable post identity first.
    """
    rows = db.execute(select(Campaign.state_json).where(Campaign.user_id == user_id)).scalars()

    posts: list[dict] = []
    recommendations: list[dict] = []
    for state_json in rows:
        if not state_json:
            continue
        for item in state_json.get("calendar", []):
            if item.get("status") == "published":
                posts.append(
                    {
                        "platform": item.get("platform"),
                        "kind": item.get("kind"),
                        "metrics": item.get("metrics") or {},
                    }
                )
        recommendations.extend(state_json.get("recommendations", []))

    summary = summarize(posts)
    # Dedupe by type so one message per insight, not one per campaign.
    seen: set[str] = set()
    unique: list[dict] = []
    for rec in recommendations:
        if rec.get("type") and rec["type"] not in seen:
            seen.add(rec["type"])
            unique.append(rec)

    summary["recommendations"] = unique or build_recommendations(posts)
    return summary
