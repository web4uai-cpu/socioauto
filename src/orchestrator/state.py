"""Campaign state shared across all agents in the orchestration graph."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


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
    hashtags: list[str] = field(default_factory=list)
    media_brief: str = ""
    cta: str = ""
    status: ContentStatus = ContentStatus.DRAFT
    moderation_reasons: list[str] = field(default_factory=list)
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    external_post_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "topic": self.topic,
            "body": self.body,
            "hashtags": list(self.hashtags),
            "media_brief": self.media_brief,
            "cta": self.cta,
            "status": self.status.value,
            "moderation_reasons": list(self.moderation_reasons),
            "scheduled_at": _iso(self.scheduled_at),
            "published_at": _iso(self.published_at),
            "external_post_id": self.external_post_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContentItem":
        return cls(
            platform=data["platform"],
            topic=data.get("topic", ""),
            body=data.get("body", ""),
            hashtags=list(data.get("hashtags", [])),
            media_brief=data.get("media_brief", ""),
            cta=data.get("cta", ""),
            status=ContentStatus(data.get("status", "draft")),
            moderation_reasons=list(data.get("moderation_reasons", [])),
            scheduled_at=_parse_dt(data.get("scheduled_at")),
            published_at=_parse_dt(data.get("published_at")),
            external_post_id=data.get("external_post_id"),
        )


@dataclass
class CampaignState:
    brand_name: str
    voice_guidelines: dict[str, Any] = field(default_factory=dict)
    auto_publish: bool = False
    platforms: list[str] = field(default_factory=list)
    trends: list[dict[str, Any]] = field(default_factory=list)
    calendar: list[ContentItem] = field(default_factory=list)
    analytics: list[dict[str, Any]] = field(default_factory=list)
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
            "trends": self.trends,
            "calendar": [item.to_dict() for item in self.calendar],
            "analytics": self.analytics,
            "log": list(self.log),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignState":
        return cls(
            brand_name=data["brand_name"],
            voice_guidelines=data.get("voice_guidelines", {}),
            auto_publish=data.get("auto_publish", False),
            platforms=list(data.get("platforms", [])),
            trends=data.get("trends", []),
            calendar=[ContentItem.from_dict(item) for item in data.get("calendar", [])],
            analytics=data.get("analytics", []),
            log=list(data.get("log", [])),
        )
