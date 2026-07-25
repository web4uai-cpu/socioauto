"""Pydantic request/response models for the v1 API. Validates every API boundary input."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.orchestrator.state import DEFAULT_TIMEZONE

POST_KIND_PATTERN = "^(text|image|video|audio|faceless_video)$"
# Same set, but empty is allowed and means "no preference — decide per platform".
OPTIONAL_POST_KIND_PATTERN = "^(text|image|video|audio|faceless_video)?$"


class CampaignCreateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    platforms: list[str] = ["instagram", "twitter", "linkedin"]
    tone: str = "professional"
    cta: str | None = None
    target_audience: str | None = None
    schedule: datetime | None = None
    # Blank means "decide per platform" (see resolve_kind in orchestrator/state.py).
    post_kind: str = Field(default="", pattern=OPTIONAL_POST_KIND_PATTERN)
    # Trusted campaigns skip the *human* review queue and publish once moderation approves.
    # Moderation itself is never skipped.
    auto_publish: bool = False
    # IANA name (e.g. "America/New_York"). Optimal posting windows are local to this.
    timezone: str = Field(default=DEFAULT_TIMEZONE, max_length=64)


class MediaRef(BaseModel):
    id: str
    url: str
    content_type: str
    kind: str


class ContentItemResponse(BaseModel):
    platform: str
    topic: str
    body: str
    status: str
    kind: str = "image"
    goal: str = ""
    # Follow-up parts for threaded platforms; empty for a single post.
    thread: list[str] = []
    hashtags: list[str] = []
    media: list[MediaRef] = []
    # Visual/Video/Audio/SEO agent output. Empty dict when the agent skipped this item.
    visual: dict = {}
    video: dict = {}
    audio: dict = {}
    seo: dict = {}
    moderation_reasons: list[str] = []
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    external_post_id: str | None = None
    external_post_url: str | None = None


class ManualPostCreateRequest(BaseModel):
    platforms: list[str] = Field(min_length=1)
    body: str = Field(min_length=1, max_length=4000)
    hashtags: list[str] = []
    cta: str | None = None
    media: list[MediaRef] = []
    schedule: datetime | None = None
    post_kind: str = Field(default="", pattern=OPTIONAL_POST_KIND_PATTERN)


class ItemEditRequest(BaseModel):
    """A reviewer's edit to one calendar item. Every field is optional; omitted ones are kept.

    Any edit re-opens the moderation gate — see `edit_campaign_item`.
    """

    body: str | None = Field(default=None, max_length=6000)
    thread: list[str] | None = None
    hashtags: list[str] | None = None
    cta: str | None = None


class RegenerateRequest(BaseModel):
    """Reviewer rejection: send content back to the agents to be re-drafted."""

    # Passed to the Content Agent so the retry addresses what was wrong.
    feedback: str | None = Field(default=None, max_length=2000)
    # Regenerate a single item; omit to redo the whole calendar.
    item_index: int | None = Field(default=None, ge=0)


class PipelineStage(BaseModel):
    name: str
    label: str


class CampaignProgressResponse(BaseModel):
    campaign_id: str
    # running | complete | error
    status: str
    current_agent: str | None = None
    current_label: str | None = None
    completed: list[str] = []
    stages: list[PipelineStage] = []
    total: int = 0
    percent: int = 0
    error: str | None = None


class CampaignResponse(BaseModel):
    id: str
    prompt: str
    platforms: list[str]
    tone: str
    cta: str | None
    target_audience: str | None
    status: str
    calendar: list[ContentItemResponse]
    # Research Agent report: keywords, hashtags, pain points. Empty for manual posts.
    research: dict = {}


class ApproveResponse(BaseModel):
    id: str
    status: str
    calendar: list[ContentItemResponse]


class Recommendation(BaseModel):
    type: str
    message: str
    evidence: dict = {}


class AnalyticsDashboardResponse(BaseModel):
    total_campaigns: int
    total_posts: int
    published_posts: int
    pending_moderation: int
    rejected_posts: int
    # Engagement rollup across measured posts. Counts stay 0 and rates None until posts are
    # live on a connected account — simulated posts return no metrics.
    posts_measured: int = 0
    impressions: int = 0
    likes: int = 0
    shares: int = 0
    comments: int = 0
    engagement_rate: float | None = None
    # None (not 0) when no platform reported click counts.
    clicks: int | None = None
    click_through_rate: float | None = None
    recommendations: list[Recommendation] = []


class AccountConnectRequest(BaseModel):
    platform: str = Field(pattern="^(x|instagram|linkedin|tiktok|facebook)$")
    external_account_id: str = Field(min_length=1, max_length=255)
    display_name: str | None = None
    api_key: str = Field(min_length=1, description="Raw platform API key/token; never stored as-is")


class AccountConnectResponse(BaseModel):
    id: str
    platform: str
    external_account_id: str
    display_name: str | None
    connected: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
