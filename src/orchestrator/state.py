"""Campaign state shared across all agents in the orchestration graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# Default audience timezone for scheduling. India has no DST, so local posting windows are
# stable year-round. Override per campaign with `CampaignState.timezone`.
DEFAULT_TIMEZONE = "Asia/Kolkata"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class PostKind(str, Enum):
    """What medium a post is, which decides how it is produced.

    Gates the generation agents: `TEXT` runs none of them, `AUDIO` produces a voiceover with
    no video, and `FACELESS_VIDEO` is a video with narration but no on-camera presenter.
    """

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FACELESS_VIDEO = "faceless_video"


# Kinds each generation agent applies to.
VISUAL_KINDS = frozenset({PostKind.IMAGE, PostKind.VIDEO, PostKind.AUDIO, PostKind.FACELESS_VIDEO})
VIDEO_KINDS = frozenset({PostKind.VIDEO, PostKind.FACELESS_VIDEO})
AUDIO_KINDS = frozenset({PostKind.AUDIO, PostKind.VIDEO, PostKind.FACELESS_VIDEO})

# What a platform gets when the caller expressed no preference. Keeps prior behaviour:
# TikTok is a video-first surface, everything else defaults to an image post.
DEFAULT_KIND_BY_PLATFORM: dict[str, PostKind] = {"tiktok": PostKind.VIDEO}
FALLBACK_KIND = PostKind.IMAGE


def resolve_kind(requested: str | PostKind | None, platform: str) -> PostKind:
    """Resolve the post kind for one item.

    Precedence: an explicit caller/model choice wins; otherwise fall back to the platform's
    default. An unrecognised value is treated as "no preference" rather than raising, so a
    bad LLM response degrades instead of failing the campaign.
    """
    if isinstance(requested, PostKind):
        return requested
    if requested:
        try:
            return PostKind(str(requested).strip().lower())
        except ValueError:
            pass
    return DEFAULT_KIND_BY_PLATFORM.get(platform, FALLBACK_KIND)


class ContentStatus(str, Enum):
    DRAFT = "draft"
    PENDING_MODERATION = "pending_moderation"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class ContentItem:
    platform: str
    topic: str
    body: str = ""
    # Medium of this post; decides which generation agents run for it.
    kind: PostKind = PostKind.IMAGE
    # Strategy goal for this item: awareness | engagement | conversion.
    goal: str = ""
    # Follow-up parts for platforms that support threads (X). Empty means a single post;
    # when populated, `body` is the first part.
    thread: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    media_brief: str = ""
    media: list[dict[str, str]] = field(default_factory=list)
    cta: str = ""
    # Visual Agent: image/thumbnail generation spec (prompt, alt_text, aspect_ratio).
    visual: dict[str, Any] = field(default_factory=dict)
    # Video Agent: script, scene beats, and thumbnail prompt for video-capable platforms.
    video: dict[str, Any] = field(default_factory=dict)
    # Audio Agent: voiceover script, voice spec, transcript, and duration estimate.
    audio: dict[str, Any] = field(default_factory=dict)
    # SEO Agent: keywords, meta description, slug, and lead-generation CTA.
    seo: dict[str, Any] = field(default_factory=dict)
    status: ContentStatus = ContentStatus.DRAFT
    moderation_reasons: list[str] = field(default_factory=list)
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    external_post_id: str | None = None
    # Public permalink, when the platform's id maps to one and the post is real.
    external_post_url: str | None = None
    # Latest performance snapshot pulled from the platform: impressions/likes/shares/comments,
    # plus clicks where the platform reports them. Empty until a post is live and measured.
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "topic": self.topic,
            "body": self.body,
            "kind": self.kind.value,
            "goal": self.goal,
            "thread": list(self.thread),
            "hashtags": list(self.hashtags),
            "media_brief": self.media_brief,
            "media": list(self.media),
            "cta": self.cta,
            "visual": dict(self.visual),
            "video": dict(self.video),
            "audio": dict(self.audio),
            "seo": dict(self.seo),
            "status": self.status.value,
            "moderation_reasons": list(self.moderation_reasons),
            "scheduled_at": _iso(self.scheduled_at),
            "published_at": _iso(self.published_at),
            "external_post_id": self.external_post_id,
            "external_post_url": self.external_post_url,
            "metrics": dict(self.metrics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContentItem":
        return cls(
            platform=data["platform"],
            topic=data.get("topic", ""),
            body=data.get("body", ""),
            kind=PostKind(data.get("kind", PostKind.IMAGE.value)),
            goal=data.get("goal", ""),
            thread=list(data.get("thread", [])),
            hashtags=list(data.get("hashtags", [])),
            media_brief=data.get("media_brief", ""),
            media=list(data.get("media", [])),
            cta=data.get("cta", ""),
            visual=dict(data.get("visual", {})),
            video=dict(data.get("video", {})),
            audio=dict(data.get("audio", {})),
            seo=dict(data.get("seo", {})),
            status=ContentStatus(data.get("status", "draft")),
            moderation_reasons=list(data.get("moderation_reasons", [])),
            scheduled_at=_parse_dt(data.get("scheduled_at")),
            published_at=_parse_dt(data.get("published_at")),
            external_post_id=data.get("external_post_id"),
            external_post_url=data.get("external_post_url"),
            metrics=dict(data.get("metrics", {})),
        )


@dataclass
class CampaignState:
    brand_name: str
    voice_guidelines: dict[str, Any] = field(default_factory=dict)
    auto_publish: bool = False
    platforms: list[str] = field(default_factory=list)
    # Raw natural-language request from the user; parsed into `brief` by the Input Parser.
    raw_input: str = ""
    # Input Parser output: intent, goal, audience, tone, topic, constraints.
    brief: dict[str, Any] = field(default_factory=dict)
    # Caller-requested post kind applied to every item; blank means decide per platform.
    post_kind: str = ""
    # Research Agent output: keywords, hashtags, pain points, competitors, sources.
    research: dict[str, Any] = field(default_factory=dict)
    # IANA timezone the audience lives in; optimal posting windows are local to it.
    timezone: str = DEFAULT_TIMEZONE
    trends: list[dict[str, Any]] = field(default_factory=list)
    calendar: list[ContentItem] = field(default_factory=list)
    analytics: list[dict[str, Any]] = field(default_factory=list)
    # Analytics Agent output: improvement suggestions derived from measured performance.
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    # LLM tokens spent generating this campaign, and their cost when rates are configured.
    # This is the measurable half of ROI; the revenue half needs attribution we do not have.
    usage: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    # Transient per-platform OAuth access tokens for publishing. Never serialized to the DB
    # (excluded from to_dict/from_dict) so decrypted secrets never touch persistent storage.
    access_tokens: dict[str, str] = field(default_factory=dict)

    def note(self, message: str) -> None:
        self.log.append(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brand_name": self.brand_name,
            "voice_guidelines": self.voice_guidelines,
            "auto_publish": self.auto_publish,
            "platforms": list(self.platforms),
            "raw_input": self.raw_input,
            "brief": dict(self.brief),
            "post_kind": self.post_kind,
            "research": dict(self.research),
            "timezone": self.timezone,
            "trends": self.trends,
            "calendar": [item.to_dict() for item in self.calendar],
            "analytics": self.analytics,
            "recommendations": list(self.recommendations),
            "usage": dict(self.usage),
            "log": list(self.log),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignState":
        return cls(
            brand_name=data["brand_name"],
            voice_guidelines=data.get("voice_guidelines", {}),
            auto_publish=data.get("auto_publish", False),
            platforms=list(data.get("platforms", [])),
            raw_input=data.get("raw_input", ""),
            brief=dict(data.get("brief", {})),
            post_kind=data.get("post_kind", ""),
            research=dict(data.get("research", {})),
            timezone=data.get("timezone", "UTC"),
            trends=data.get("trends", []),
            calendar=[ContentItem.from_dict(item) for item in data.get("calendar", [])],
            analytics=data.get("analytics", []),
            recommendations=list(data.get("recommendations", [])),
            usage=dict(data.get("usage", {})),
            log=list(data.get("log", [])),
        )
