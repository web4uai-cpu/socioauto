"""Campaign endpoints: create from natural language, fetch, and human-in-the-loop approval."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.agents.moderation import ModerationAgent
from src.agents.publishing import PublishingAgent
from src.agents.scheduling import SchedulingAgent
from src.api.deps import enforce_rate_limit, get_current_user
from src.api.schemas import (
    CampaignCreateRequest,
    CampaignProgressResponse,
    CampaignResponse,
    ContentItemResponse,
    ManualPostCreateRequest,
    PipelineStage,
)
from src.db.models import User
from src.db.repositories import accounts as accounts_repo
from src.db.repositories import audit
from src.db.repositories import campaigns as campaigns_repo
from src.db.repositories.campaigns import CampaignRecord
from src.db.session import get_db
from src.logging_config import get_logger
from src.orchestrator import progress
from src.orchestrator.graph import AGENT_LABELS, PRE_APPROVAL_PIPELINE, run_to_moderation
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus, resolve_kind

logger = get_logger(__name__)

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
        research=record.state.research,
        calendar=[
            ContentItemResponse(
                platform=item.platform,
                topic=item.topic,
                body=item.body,
                status=item.status.value,
                kind=item.kind.value,
                goal=item.goal,
                hashtags=item.hashtags,
                media=item.media,
                visual=item.visual,
                video=item.video,
                audio=item.audio,
                seo=item.seo,
                moderation_reasons=item.moderation_reasons,
                scheduled_at=item.scheduled_at,
                published_at=item.published_at,
                external_post_id=item.external_post_id,
            )
            for item in record.state.calendar
        ],
    )


@router.post("/manual", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_manual_post(
    req: ManualPostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    """Create a user-authored post (own text, optional uploaded audio/video/image) instead of
    letting the AI pipeline generate it. Still runs through the mandatory Moderation Agent gate
    before it can be scheduled or published — see `/approve` and `/schedule`.
    """
    state = CampaignState(
        brand_name=current_user.email, platforms=req.platforms, post_kind=req.post_kind
    )
    state.calendar = [
        ContentItem(
            platform=platform,
            topic=req.body[:80],
            body=req.body,
            kind=resolve_kind(req.post_kind, platform),
            hashtags=list(req.hashtags),
            media=[m.model_dump() for m in req.media],
            cta=req.cta or "",
            status=ContentStatus.PENDING_MODERATION,
            scheduled_at=req.schedule,
        )
        for platform in req.platforms
    ]
    state = ModerationAgent().run(state)

    any_approved = any(item.status == ContentStatus.APPROVED for item in state.calendar)
    record = CampaignRecord(
        id=campaigns_repo.new_id(),
        user_id=str(current_user.id),
        prompt=req.body,
        platforms=req.platforms,
        tone="manual",
        cta=req.cta,
        target_audience=None,
        status="pending_review" if any_approved else "needs_revision",
        state=state,
    )
    campaigns_repo.save(db, record)
    audit.record(
        db,
        actor=current_user.email,
        action="campaign.manual_created",
        entity_type="campaign",
        entity_id=record.id,
        details={"status": record.status, "platforms": req.platforms},
    )
    return _to_response(record)


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
        # The Input Parser turns this into a structured brief and seeds the research agent.
        raw_input=req.prompt,
        post_kind=req.post_kind,
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


def _stages() -> list[PipelineStage]:
    """The ordered pre-approval pipeline, with display labels for the progress UI."""
    return [
        PipelineStage(name=agent.name, label=AGENT_LABELS.get(agent.name, agent.name))
        for agent in PRE_APPROVAL_PIPELINE
    ]


def _run_pipeline_in_background(campaign_id: str, actor: str) -> None:
    """Run the generation pipeline for an already-persisted draft, reporting progress.

    Runs in a FastAPI background task, so it needs its own DB session — the request-scoped
    one is closed by the time this executes.
    """
    from src.db.session import SessionLocal

    stages = _stages()
    total = len(stages)
    completed: list[str] = []

    def report(agent_name: str, index: int, _total: int) -> None:
        completed.append(agent_name)
        progress.set_progress(
            campaign_id,
            {
                "campaign_id": campaign_id,
                "status": "running",
                "current_agent": agent_name,
                "current_label": AGENT_LABELS.get(agent_name, agent_name),
                "completed": list(completed),
                "total": total,
                "percent": round(index / total * 100),
            },
        )

    db = SessionLocal()
    try:
        record = campaigns_repo.get(db, campaign_id)
        if record is None:
            return
        record.state = run_to_moderation(record.state, on_agent=report)
        any_approved = any(item.status == ContentStatus.APPROVED for item in record.state.calendar)
        record.status = "pending_review" if any_approved else "needs_revision"
        campaigns_repo.save(db, record)
        audit.record(
            db,
            actor=actor,
            action="campaign.created",
            entity_type="campaign",
            entity_id=campaign_id,
            details={"status": record.status},
        )
        progress.set_progress(
            campaign_id,
            {
                "campaign_id": campaign_id,
                "status": "complete",
                "current_agent": None,
                "current_label": None,
                "completed": [s.name for s in stages],
                "total": total,
                "percent": 100,
            },
        )
    except Exception as exc:  # noqa: BLE001 - surface the failure to the poller
        logger.exception("background campaign failed", extra={"campaign_id": campaign_id})
        progress.set_progress(
            campaign_id,
            {
                "campaign_id": campaign_id,
                "status": "error",
                "completed": list(completed),
                "total": total,
                "percent": round(len(completed) / total * 100) if total else 0,
                "error": str(exc),
            },
        )
    finally:
        db.close()


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
def start_campaign(
    req: CampaignCreateRequest,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Create a draft campaign and run the pipeline in the background.

    Returns immediately with the campaign id so the client can poll
    ``GET /api/v1/campaigns/{id}/progress`` and show per-agent progress. Use ``POST
    /api/v1/campaigns`` instead when a synchronous result is wanted.
    """
    state = CampaignState(
        brand_name=current_user.email,
        platforms=req.platforms,
        voice_guidelines={"tone": req.tone, "cta": req.cta, "audience": req.target_audience},
        raw_input=req.prompt,
        post_kind=req.post_kind,
    )
    record = CampaignRecord(
        id=campaigns_repo.new_id(),
        user_id=str(current_user.id),
        prompt=req.prompt,
        platforms=req.platforms,
        tone=req.tone,
        cta=req.cta,
        target_audience=req.target_audience,
        # "draft" is the persisted not-yet-generated state (matches /async); the response
        # reports "generating" because that is what is actually happening.
        status="draft",
        state=state,
    )
    campaigns_repo.save(db, record)

    stages = _stages()
    progress.set_progress(
        record.id,
        {
            "campaign_id": record.id,
            "status": "running",
            "current_agent": None,
            "current_label": "Starting",
            "completed": [],
            "total": len(stages),
            "percent": 0,
        },
    )
    background.add_task(_run_pipeline_in_background, record.id, current_user.email)
    return {"campaign_id": record.id, "status": "generating"}


@router.get("/{campaign_id}/progress", response_model=CampaignProgressResponse)
def campaign_progress(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignProgressResponse:
    """Report how far the generation pipeline has got for one campaign."""
    record = campaigns_repo.get(db, campaign_id)
    if record is None or record.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    stages = _stages()
    snapshot = progress.get_progress(campaign_id)
    if snapshot is None:
        # Nothing recorded: either it predates progress tracking or it ran synchronously.
        # Infer from the persisted status rather than reporting a bogus 0%.
        done = record.status not in ("generating", "draft")
        return CampaignProgressResponse(
            campaign_id=campaign_id,
            status="complete" if done else "running",
            completed=[s.name for s in stages] if done else [],
            stages=stages,
            total=len(stages),
            percent=100 if done else 0,
        )
    return CampaignProgressResponse(stages=stages, **snapshot)


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
        # The Input Parser turns this into a structured brief and seeds the research agent.
        raw_input=req.prompt,
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
