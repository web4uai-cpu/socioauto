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
}


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

        return get_breaker(self.platform).call(_do)


def get_client(platform: str) -> RestPlatformClient:
    return RestPlatformClient(platform)
