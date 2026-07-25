"""Celery application and campaign-execution task.

Slow LLM/agent work runs off the request thread so the API stays responsive (SYSTEM_DESIGN §6).
Without a broker configured (local/dev/tests) tasks run eagerly in-process, so callers get the
same behavior without needing Redis.
"""

from __future__ import annotations

import os
import uuid

from celery import Celery

from src.logging_config import get_logger
from src.orchestrator.graph import run_to_moderation
from src.orchestrator.state import ContentStatus

logger = get_logger(__name__)

_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() in ("1", "true", "yes")

celery_app = Celery("socialmedia", broker=_BROKER_URL, backend=_BROKER_URL)
celery_app.conf.update(
    task_always_eager=_EAGER,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_default_queue="orchestrator",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Run the due-post publisher once a minute (requires `celery beat`).
    beat_schedule={
        "publish-due-posts": {
            "task": "scheduling.publish_due_posts",
            "schedule": 60.0,
        }
    },
)


@celery_app.task(name="orchestrator.run_campaign")
def run_campaign_task(campaign_id: str, actor_email: str) -> dict:
    """Run the pre-approval agent pipeline for a persisted campaign and save the result.

    Loads the draft campaign, runs research → strategy → creation → moderation, updates the
    campaign status, and persists it (plus an audit-log entry). Returns a small status dict.
    """
    # Imported lazily so the worker process owns its own DB session lifecycle.
    from src.db.repositories import audit
    from src.db.repositories import campaigns as campaigns_repo
    from src.db.session import SessionLocal

    db = SessionLocal()
    try:
        record = campaigns_repo.get(db, campaign_id)
        if record is None:
            logger.error("campaign task: record not found", extra={"campaign_id": campaign_id})
            return {"campaign_id": campaign_id, "status": "not_found"}

        logger.info("campaign task started", extra={"campaign_id": campaign_id})
        record.state = run_to_moderation(record.state)
        any_approved = any(item.status == ContentStatus.APPROVED for item in record.state.calendar)
        record.status = "pending_review" if any_approved else "needs_revision"
        campaigns_repo.save(db, record)
        audit.record(
            db,
            actor=actor_email,
            action="campaign.pipeline_completed",
            entity_type="campaign",
            entity_id=campaign_id,
            details={"status": record.status},
        )
        logger.info(
            "campaign task finished",
            extra={"campaign_id": campaign_id, "status": record.status},
        )
        return {"campaign_id": campaign_id, "status": record.status}
    finally:
        db.close()


@celery_app.task(name="engagement.process_inbound")
def process_inbound_engagement(engagement_id: str) -> dict:
    """Draft a reply for one inbound engagement, or flag it for a human.

    Enqueued by the platform webhook handlers after the row is persisted, so a worker
    outage delays drafting but never loses the message.
    """
    from src.agents.engagement import EngagementAgent
    from src.db.repositories import engagements as engagements_repo
    from src.db.session import SessionLocal

    db = SessionLocal()
    try:
        engagement = engagements_repo.get(db, uuid.UUID(engagement_id))
        if engagement is None:
            logger.error("engagement not found", extra={"engagement_id": engagement_id})
            return {"engagement_id": engagement_id, "status": "not_found"}

        draft, escalated = EngagementAgent().draft_reply(engagement.message)
        engagements_repo.save_draft(db, engagement, draft=draft, escalated=escalated)
        logger.info(
            "engagement processed",
            extra={"engagement_id": engagement_id, "escalated": escalated},
        )
        return {"engagement_id": engagement_id, "status": engagement.status}
    finally:
        db.close()


@celery_app.task(name="scheduling.publish_due_posts")
def publish_due_posts() -> dict:
    """Publish all scheduled posts whose time has arrived, across every campaign.

    Runs on the Celery beat schedule. For each campaign with due posts it resolves the owner's
    decrypted platform tokens, publishes the due items, and persists the updated campaign.
    """
    from datetime import UTC, datetime

    from src.db.repositories import accounts as accounts_repo
    from src.db.repositories import audit
    from src.db.repositories import campaigns as campaigns_repo
    from src.db.session import SessionLocal
    from src.orchestrator.state import ContentStatus
    from src.scheduling.runner import publish_due_items

    db = SessionLocal()
    total = 0
    campaigns_touched = 0
    try:
        now = datetime.now(UTC)
        for record in campaigns_repo.with_due_posts(db, now):
            tokens = accounts_repo.access_tokens_for_user(db, uuid.UUID(record.user_id))
            count = publish_due_items(record.state, tokens, now)
            if count == 0:
                continue
            if all(i.status == ContentStatus.PUBLISHED for i in record.state.calendar):
                record.status = "published"
            campaigns_repo.save(db, record)
            audit.record(
                db,
                actor="system:scheduler",
                action="campaign.due_published",
                entity_type="campaign",
                entity_id=record.id,
                details={"published": count},
            )
            total += count
            campaigns_touched += 1
        logger.info(
            "due-post run complete",
            extra={"published": total, "campaigns": campaigns_touched},
        )
        return {"published": total, "campaigns": campaigns_touched}
    finally:
        db.close()
