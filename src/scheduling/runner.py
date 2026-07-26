"""Due-post publishing: publish scheduled items whose time has arrived."""

from __future__ import annotations

from datetime import UTC, datetime

from src.logging_config import get_logger
from src.orchestrator.state import CampaignState, ContentStatus
from src.platforms.delivery import deliver, is_due

logger = get_logger(__name__)


def publish_due_items(
    state: CampaignState, access_tokens: dict[str, str], now: datetime | None = None
) -> int:
    """Publish every SCHEDULED item that is due, including ones awaiting a retry.

    Delivery, retry scheduling, and escalation all live in `platforms.delivery`, shared with
    the Publishing Agent — this runner only decides *which* items are due.

    Uses the connected account's token per platform (falls back to simulate mode when absent).
    Mutates ``state`` in place and returns the number of items published.
    """
    now = now or datetime.now(UTC)
    published = 0
    for item in state.calendar:
        if item.status != ContentStatus.SCHEDULED or not is_due(item, now):
            continue
        if deliver(item, access_tokens.get(item.platform), now):
            published += 1
    return published


def items_needing_attention(state: CampaignState) -> list[dict]:
    """Items whose automated recovery is exhausted and that a human must now look at."""
    return [
        {
            "platform": item.platform,
            "topic": item.topic,
            "status": item.status.value,
            "attempts": item.retry_count,
            "last_error": item.last_error,
        }
        for item in state.calendar
        if item.needs_human
    ]
