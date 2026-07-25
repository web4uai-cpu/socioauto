"""Pydantic request/response models for the v1 API. Validates every API boundary input."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

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


class ManualPostCreateRequest(BaseModel):
    platforms: list[str] = Field(min_length=1)
    body: str = Field(min_length=1, max_length=4000)
    hashtags: list[str] = []
    cta: str | None = None
    media: list[MediaRef] = []
    schedule: datetime | None = None
    post_kind: str = Field(default="", pattern=OPTIONAL_POST_KIND_PATTERN)


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


class ApproveResponse(BaseModel):
    id: str
    status: str
    calendar: list[ContentItemResponse]


class AnalyticsDashboardResponse(BaseModel):
    total_campaigns: int
    total_posts: int
    published_posts: int
    pending_moderation: int
    rejected_posts: int


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
