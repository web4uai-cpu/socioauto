"""Campaign persistence.

The full ``CampaignState`` is stored as JSON on the campaign row (source of truth for the
agent pipeline). Each calendar item is also projected into a ``Post`` row so analytics and
reporting can run real relational queries. The projection is rebuilt on every save, so the
two representations never diverge.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.db.models import Campaign, Post
from src.orchestrator.state import CampaignState


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass
class CampaignRecord:
    id: str
    user_id: str
    prompt: str
    platforms: list[str]
    tone: str
    cta: str | None
    target_audience: str | None
    status: str
    state: CampaignState


def _to_record(row: Campaign) -> CampaignRecord:
    return CampaignRecord(
        id=str(row.id),
        user_id=str(row.user_id),
        prompt=row.prompt or "",
        platforms=list(row.platforms or []),
        tone=row.tone,
        cta=row.cta,
        target_audience=row.target_audience,
        status=row.status,
        state=CampaignState.from_dict(row.state_json or {"brand_name": str(row.user_id)}),
    )


def _project_posts(db: Session, row: Campaign) -> None:
    """Rebuild the Post projection for a campaign from its CampaignState calendar."""
    db.execute(delete(Post).where(Post.campaign_id == row.id))
    for item in row.state_json.get("calendar", []):
        db.add(
            Post(
                campaign_id=row.id,
                social_account_id=None,
                platform=item["platform"],
                body=item.get("body", ""),
                media_refs={"media_brief": item.get("media_brief", "")},
                status=item.get("status", "draft"),
                moderation_reasons={"reasons": item.get("moderation_reasons", [])},
                scheduled_at=_parse_dt(item.get("scheduled_at")),
                published_at=_parse_dt(item.get("published_at")),
                external_post_id=item.get("external_post_id"),
            )
        )


def save(db: Session, record: CampaignRecord) -> None:
    row = db.get(Campaign, uuid.UUID(record.id))
    if row is None:
        row = Campaign(id=uuid.UUID(record.id), user_id=uuid.UUID(record.user_id))
        db.add(row)
    row.name = (record.prompt or "campaign")[:255]
    row.prompt = record.prompt
    row.tone = record.tone
    row.cta = record.cta
    row.target_audience = record.target_audience
    row.platforms = record.platforms
    row.voice_guidelines = record.state.voice_guidelines
    row.auto_publish = record.state.auto_publish
    row.status = record.status
    row.state_json = record.state.to_dict()
    db.flush()
    _project_posts(db, row)
    db.commit()


def get(db: Session, campaign_id: str) -> CampaignRecord | None:
    try:
        pk = uuid.UUID(campaign_id)
    except ValueError:
        return None
    row = db.get(Campaign, pk)
    return _to_record(row) if row else None


def for_user(db: Session, user_id: uuid.UUID) -> list[CampaignRecord]:
    rows = db.execute(select(Campaign).where(Campaign.user_id == user_id)).scalars().all()
    return [_to_record(r) for r in rows]


def with_due_posts(db: Session, now: datetime) -> list[CampaignRecord]:
    """Return campaigns that have at least one scheduled post due at or before ``now``."""
    stmt = (
        select(Campaign)
        .join(Post, Post.campaign_id == Campaign.id)
        .where(Post.status == "scheduled", Post.scheduled_at <= now)
        .distinct()
    )
    return [_to_record(r) for r in db.execute(stmt).scalars().all()]


def new_id() -> str:
    return str(uuid.uuid4())
