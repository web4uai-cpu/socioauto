"""Due-post publishing: publish scheduled items whose time has arrived."""
from __future__ import annotations

from datetime import UTC, datetime

from src.logging_config import get_logger
from src.orchestrator.state import CampaignState, ContentStatus
from src.platforms.http_client import PlatformHttpError, publish_post

logger = get_logger(__name__)


def publish_due_items(
    state: CampaignState, access_tokens: dict[str, str], now: datetime | None = None
) -> int:
    """Publish every SCHEDULED item whose ``scheduled_at`` is at or before ``now``.

    Uses the connected account's token per platform (falls back to simulate mode when absent).
    Mutates ``state`` in place and returns the number of items published.
    """
    now = now or datetime.now(UTC)
    published = 0
    for item in state.calendar:
        if item.status != ContentStatus.SCHEDULED:
            continue
        if item.scheduled_at is not None and item.scheduled_at > now:
            continue  # not due yet
        try:
            token = access_tokens.get(item.platform)
            item.external_post_id = publish_post(item.platform, item.body, access_token=token)
            item.published_at = datetime.now(UTC)
            item.status = ContentStatus.PUBLISHED
            published += 1
            logger.info(
                "due post published",
                extra={"platform": item.platform, "external_post_id": item.external_post_id},
            )
        except PlatformHttpError as exc:
            item.status = ContentStatus.FAILED
            state.note(f"[scheduler] publish failed for {item.platform}: {exc}")
            logger.error(
                "due publish failed", extra={"platform": item.platform, "error": str(exc)}
            )
    return published
