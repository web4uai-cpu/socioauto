"""Campaign endpoints: create from natural language, fetch, and human-in-the-loop approval."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.agents.publishing import PublishingAgent
from src.agents.scheduling import SchedulingAgent
from src.api.deps import enforce_rate_limit, get_current_user
from src.api.schemas import CampaignCreateRequest, CampaignResponse, ContentItemResponse
from src.db.models import User
from src.db.repositories import accounts as accounts_repo
from src.db.repositories import audit
from src.db.repositories import campaigns as campaigns_repo
from src.db.repositories.campaigns import CampaignRecord
from src.db.session import get_db
from src.orchestrator.graph import run_to_moderation
from src.orchestrator.state import CampaignState, ContentStatus

router = APIRouter(
    prefix="/api/v1/campaigns", tags=["campaigns"], dependencies=[Depends(enforce_rate_limit)]
)


def _to_response(record: CampaignRecord) -> CampaignResponse:
    return CampaignResponse(
        id=record.id,
        prompt=record.prompt,
        platforms=record.platforms,
        tone=record.tone,
        cta=record.cta,
        target_audience=record.target_audience,
        status=record.status,
        calendar=[
            ContentItemResponse(
                platform=item.platform,
                topic=item.topic,
                body=item.body,
                status=item.status.value,
                scheduled_at=item.scheduled_at,
                published_at=item.published_at,
                external_post_id=item.external_post_id,
            )
            for item in record.state.calendar
        ],
    )


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    req: CampaignCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    """Create a campaign from a natural-language prompt and run research/strategy/creation
    up through moderation. Publishing only happens after an explicit human approval call.
    """
    state = CampaignState(
        brand_name=current_user.email,
        platforms=req.platforms,
        voice_guidelines={"tone": req.tone, "cta": req.cta, "audience": req.target_audience},
        trends=[{"topic": req.prompt, "score": 1.0, "source": "nl-prompt"}],
    )
    state = run_to_moderation(state)

    any_approved = any(item.status == ContentStatus.APPROVED for item in state.calendar)
    record = CampaignRecord(
        id=campaigns_repo.new_id(),
        user_id=str(current_user.id),
        prompt=req.prompt,
        platforms=req.platforms,
        tone=req.tone,
        cta=req.cta,
        target_audience=req.target_audience,
        status="pending_review" if any_approved else "needs_revision",
        state=state,
    )
    campaigns_repo.save(db, record)
    audit.record(
        db,
        actor=current_user.email,
        action="campaign.created",
        entity_type="campaign",
        entity_id=record.id,
        details={"status": record.status, "platforms": req.platforms},
    )
    return _to_response(record)


@router.post("/async", status_code=status.HTTP_202_ACCEPTED)
def enqueue_campaign(
    req: CampaignCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Persist a draft campaign and enqueue its agent pipeline on the Celery worker.

    Offloads the slow agent pipeline from the request thread (SYSTEM_DESIGN §6). With no broker
    configured (dev/tests) the task runs eagerly in-process and completes before returning. Poll
    ``GET /api/v1/campaigns/{id}`` for the result.
    """
    from src.orchestrator.tasks import run_campaign_task

    state = CampaignState(
        brand_name=current_user.email,
        platforms=req.platforms,
        voice_guidelines={"tone": req.tone, "cta": req.cta, "audience": req.target_audience},
        trends=[{"topic": req.prompt, "score": 1.0, "source": "nl-prompt"}],
    )
    record = CampaignRecord(
        id=campaigns_repo.new_id(),
        user_id=str(current_user.id),
        prompt=req.prompt,
        platforms=req.platforms,
        tone=req.tone,
        cta=req.cta,
        target_audience=req.target_audience,
        status="draft",
        state=state,
    )
    campaigns_repo.save(db, record)
    task = run_campaign_task.delay(record.id, current_user.email)
    return {"task_id": str(task.id), "campaign_id": record.id, "status": "queued"}


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CampaignResponse]:
    """List only campaigns created by the authenticated user."""
    return [_to_response(record) for record in campaigns_repo.for_user(db, current_user.id)]


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign_details(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    record = campaigns_repo.get(db, campaign_id)
    if record is None or record.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return _to_response(record)


@router.post("/{campaign_id}/schedule", response_model=CampaignResponse)
def schedule_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    """Queue approved content into optimal future time slots without publishing now.

    The due-post runner (Celery beat task ``scheduling.publish_due_posts``) publishes each item
    once its scheduled time arrives. Use ``/approve`` instead to publish immediately.
    """
    record = campaigns_repo.get(db, campaign_id)
    if record is None or record.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    record.state = SchedulingAgent().run(record.state)
    if any(item.status == ContentStatus.SCHEDULED for item in record.state.calendar):
        record.status = "scheduled"
    campaigns_repo.save(db, record)
    audit.record(
        db,
        actor=current_user.email,
        action="campaign.scheduled",
        entity_type="campaign",
        entity_id=record.id,
        details={"status": record.status},
    )
    return _to_response(record)


@router.post("/{campaign_id}/approve", response_model=CampaignResponse)
def approve_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    """Human-in-the-loop approval gate: only content already APPROVED by Moderation is
    scheduled and published here. Rejected items are left untouched for revision.
    """
    record = campaigns_repo.get(db, campaign_id)
    if record is None or record.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    # Attach the user's decrypted platform tokens transiently so publishing hits the real APIs
    # (falls back to simulate mode for any platform without a connected account).
    record.state.access_tokens = accounts_repo.access_tokens_for_user(db, current_user.id)
    state = SchedulingAgent().run(record.state)
    state = PublishingAgent().run(state)
    record.state = state
    record.status = (
        "published"
        if any(item.status == ContentStatus.PUBLISHED for item in state.calendar)
        else record.status
    )
    campaigns_repo.save(db, record)
    audit.record(
        db,
        actor=current_user.email,
        action="campaign.approved",
        entity_type="campaign",
        entity_id=record.id,
        details={"status": record.status},
    )
    return _to_response(record)
