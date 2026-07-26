"""Concrete per-platform API clients.

Each client knows how to turn a rendered post into the correct API request for its platform
and how to read back basic metrics. All network I/O goes through ``http_client.request_json``
(TLS + retry/backoff) wrapped in a per-platform circuit breaker.

When no ``access_token`` is supplied (local/demo runs without connected credentials), clients
operate in **simulate** mode and return a synthetic external id, so the orchestrator pipeline
remains runnable end-to-end without live platform apps.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from src.logging_config import get_logger
from src.platforms.circuit_breaker import get_breaker
from src.platforms.http_client import PlatformHttpError, request_json

logger = get_logger(__name__)


class PlatformClient(Protocol):
    platform: str

    def publish(self, body: str, *, access_token: str | None = None) -> str: ...

    def fetch_metrics(self, external_id: str, *, access_token: str | None = None) -> dict: ...


@dataclass
class _Endpoint:
    publish_url: str
    metrics_url_template: str


# Public REST endpoints per platform (payload shapes handled in RestPlatformClient).
_ENDPOINTS: dict[str, _Endpoint] = {
    "x": _Endpoint(
        "https://api.twitter.com/2/tweets",
        "https://api.twitter.com/2/tweets/{id}?tweet.fields=public_metrics",
    ),
    "linkedin": _Endpoint(
        "https://api.linkedin.com/v2/ugcPosts",
        "https://api.linkedin.com/v2/socialActions/{id}",
    ),
    "facebook": _Endpoint(
        "https://graph.facebook.com/v19.0/me/feed",
        "https://graph.facebook.com/v19.0/{id}/insights",
    ),
    "instagram": _Endpoint(
        "https://graph.facebook.com/v19.0/me/media",
        "https://graph.facebook.com/v19.0/{id}/insights",
    ),
    "tiktok": _Endpoint(
        "https://open.tiktokapis.com/v2/post/publish/content/init/",
        "https://open.tiktokapis.com/v2/video/query/",
    ),
    # YouTube long-form and Shorts share the Data API v3 videos resource; they differ only in
    # the shape of the media (16:9 vs 9:16) and the runtime, which the generation agents handle.
    "youtube": _Endpoint(
        "https://www.googleapis.com/youtube/v3/videos?part=snippet,status",
        "https://www.googleapis.com/youtube/v3/videos?part=statistics&id={id}",
    ),
    "youtube_shorts": _Endpoint(
        "https://www.googleapis.com/youtube/v3/videos?part=snippet,status",
        "https://www.googleapis.com/youtube/v3/videos?part=statistics&id={id}",
    ),
}

# Platforms served by the YouTube Data API, which needs a nested snippet payload and returns
# metrics wrapped in an `items` envelope.
_YOUTUBE_PLATFORMS = frozenset({"youtube", "youtube_shorts"})
# YouTube rejects a snippet.title longer than this.
_YOUTUBE_TITLE_LIMIT = 100
# "People & Blogs" — the safest default when the caller expresses no category.
_YOUTUBE_CATEGORY_ID = "22"


def _derive_title(body: str) -> str:
    """Derive a YouTube video title from the post body.

    ContentItem carries a single ``body``; YouTube needs a separate title. Take the first
    non-empty line and truncate on a word boundary so the title never ends mid-word.
    """
    first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
    title = " ".join(first_line.split())
    if len(title) <= _YOUTUBE_TITLE_LIMIT:
        return title
    clipped = title[:_YOUTUBE_TITLE_LIMIT]
    head, sep, _ = clipped.rpartition(" ")
    return (head if sep else clipped).rstrip()


# Permalink templates for platforms whose post id maps directly onto a public URL.
#
# Instagram is deliberately absent: its Graph API media id is *not* the /p/<shortcode> used in
# permalinks, so building a URL from the id would produce a dead link. Instagram returns a
# `permalink` field on the media object — capture that rather than guessing.
_PERMALINKS: dict[str, str] = {
    "x": "https://x.com/i/web/status/{id}",
    "linkedin": "https://www.linkedin.com/feed/update/{id}",
    "facebook": "https://www.facebook.com/{id}",
    "tiktok": "https://www.tiktok.com/video/{id}",
    # Both YouTube surfaces return a real video id, so a permalink can be built directly.
    "youtube": "https://www.youtube.com/watch?v={id}",
    "youtube_shorts": "https://www.youtube.com/shorts/{id}",
}
# Marker used by simulate-mode ids; those posts do not exist, so they get no URL.
_SIMULATED = "-sim-"


def build_post_url(platform: str, external_id: str | None) -> str | None:
    """Return the public URL for a published post, or None when one cannot be known.

    Returns None for simulated posts and for platforms whose id does not map to a URL —
    handing back a plausible-looking dead link would be worse than returning nothing.
    """
    if not external_id or _SIMULATED in external_id:
        return None
    template = _PERMALINKS.get(platform)
    return template.format(id=external_id) if template else None


class RestPlatformClient:
    """Config-driven REST client covering all supported platforms."""

    def __init__(self, platform: str) -> None:
        if platform not in _ENDPOINTS:
            raise PlatformHttpError(f"no API client configured for platform '{platform}'")
        self.platform = platform
        self._endpoint = _ENDPOINTS[platform]

    def _build_payload(self, body: str) -> dict:
        if self.platform == "x":
            return {"text": body}
        if self.platform in ("facebook", "instagram"):
            return {"message": body}
        if self.platform in _YOUTUBE_PLATFORMS:
            return {
                "snippet": {
                    "title": _derive_title(body),
                    "description": body,
                    "categoryId": _YOUTUBE_CATEGORY_ID,
                },
                "status": {"privacyStatus": "public"},
            }
        # LinkedIn/TikTok accept a message-like field; kept generic for the scaffold.
        return {"text": body}

    def publish(self, body: str, *, access_token: str | None = None) -> str:
        if not body.strip():
            raise PlatformHttpError("empty post body")
        if access_token is None:
            external_id = f"{self.platform}-sim-{uuid.uuid4().hex[:10]}"
            logger.info("platform post simulated", extra={"platform": self.platform})
            return external_id

        def _do() -> dict:
            return request_json(
                "POST",
                self._endpoint.publish_url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=self._build_payload(body),
            )

        payload = get_breaker(self.platform).call(_do)
        external_id = (
            payload.get("data", {}).get("id")
            or payload.get("id")
            or f"{self.platform}-{uuid.uuid4().hex[:10]}"
        )
        logger.info(
            "platform post accepted",
            extra={"platform": self.platform, "external_post_id": external_id},
        )
        return external_id

    def fetch_metrics(self, external_id: str, *, access_token: str | None = None) -> dict:
        if access_token is None:
            return {"impressions": 0, "likes": 0, "shares": 0, "comments": 0}

        def _do() -> dict:
            return request_json(
                "GET",
                self._endpoint.metrics_url_template.format(id=external_id),
                headers={"Authorization": f"Bearer {access_token}"},
            )

        payload = get_breaker(self.platform).call(_do)
        if self.platform in _YOUTUBE_PLATFORMS:
            # v3 wraps results in an `items` envelope; flatten so callers see a plain dict
            # like every other platform returns.
            items = payload.get("items") or []
            return items[0].get("statistics", {}) if items else {}
        return payload


def get_client(platform: str) -> RestPlatformClient:
    return RestPlatformClient(platform)
