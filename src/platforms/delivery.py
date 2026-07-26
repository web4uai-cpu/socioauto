"""Single delivery path for publishing one content item, with retry and escalation.

Both the Publishing Agent and the due-post runner call `deliver()`. They previously each had
their own copy of this logic and had already drifted — the runner never recorded
`external_post_url` — so keeping one implementation is the point of this module.

Recovery policy (docs/AGENT_WORKFLOW.md § Error Handling):

- **Transport-level** retries (429/5xx/network) happen inside `request_json` via tenacity,
  within a single attempt.
- **Attempt-level** retries happen here: a failed publish stays SCHEDULED with an exponentially
  backed-off `next_retry_at`, so the due-post runner picks it up later instead of the post
  dying on one bad minute.
- After `MAX_PUBLISH_ATTEMPTS` the item is marked FAILED **and** flagged `needs_human`, which
  is what surfaces it on the escalation queue. Silent permanent failure is the outcome this
  policy exists to prevent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.logging_config import get_logger
from src.orchestrator.state import ContentItem, ContentStatus
from src.platforms.clients import build_post_url
from src.platforms.http_client import PlatformHttpError, publish_post

logger = get_logger(__name__)

MAX_PUBLISH_ATTEMPTS = 5
# Backoff per attempt number. Deliberately spans minutes-to-hours: platform outages and
# rate-limit windows rarely clear in seconds, and hammering them makes it worse.
_BACKOFF = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=45),
    timedelta(hours=2),
    timedelta(hours=6),
)


def backoff_for(attempt: int) -> timedelta:
    """Delay before retry number `attempt` (1-based), capped at the longest step."""
    index = max(0, min(attempt - 1, len(_BACKOFF) - 1))
    return _BACKOFF[index]


def is_due(item: ContentItem, now: datetime) -> bool:
    """True when the item's scheduled time has arrived and any retry backoff has elapsed."""
    if item.scheduled_at is not None and item.scheduled_at > now:
        return False
    return item.next_retry_at is None or item.next_retry_at <= now


def deliver(item: ContentItem, access_token: str | None, now: datetime | None = None) -> bool:
    """Publish one item, recording success or scheduling a retry. Returns True if published.

    Mutates `item`. Never raises: delivery failures are a normal operating condition and must
    not abort a batch of other posts.
    """
    now = now or datetime.now(UTC)
    try:
        external_id = publish_post(item.platform, item.body, access_token=access_token)
    except PlatformHttpError as exc:
        _record_failure(item, str(exc), now)
        return False

    item.external_post_id = external_id
    item.external_post_url = build_post_url(item.platform, external_id)
    item.published_at = now
    item.status = ContentStatus.PUBLISHED
    # Clear retry bookkeeping so a post that eventually succeeded looks clean.
    item.next_retry_at = None
    item.last_error = None
    item.needs_human = False
    logger.info(
        "post published",
        extra={
            "platform": item.platform,
            "external_post_id": external_id,
            "attempts": item.retry_count + 1,
        },
    )
    return True


def _record_failure(item: ContentItem, error: str, now: datetime) -> None:
    item.retry_count += 1
    item.last_error = error[:500]

    if item.retry_count >= MAX_PUBLISH_ATTEMPTS:
        item.status = ContentStatus.FAILED
        item.next_retry_at = None
        item.needs_human = True
        logger.error(
            "publish escalated to human after exhausting retries",
            extra={
                "platform": item.platform,
                "attempts": item.retry_count,
                "error": error,
            },
        )
        return

    item.status = ContentStatus.SCHEDULED  # stays queued for the next attempt
    item.next_retry_at = now + backoff_for(item.retry_count)
    logger.warning(
        "publish failed; retry scheduled",
        extra={
            "platform": item.platform,
            "attempt": item.retry_count,
            "next_retry_at": item.next_retry_at.isoformat(),
            "error": error,
        },
    )
