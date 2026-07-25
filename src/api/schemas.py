"""Pydantic request/response models for the v1 API. Validates every API boundary input."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CampaignCreateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    platforms: list[str] = ["instagram", "twitter", "linkedin"]
    tone: str = "professional"
    cta: str | None = None
    target_audience: str | None = None
    schedule: datetime | None = None


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
    hashtags: list[str] = []
    media: list[MediaRef] = []
    # Visual/Video/SEO agent output. Empty dict when the agent skipped this item.
    visual: dict = {}
    video: dict = {}
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
