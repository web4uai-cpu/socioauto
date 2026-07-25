"""Publishing Agent: calls platform APIs for scheduled+approved content only."""

from __future__ import annotations

from datetime import UTC, datetime

from src.agents.base import BaseAgent
from src.logging_config import get_logger
from src.orchestrator.state import CampaignState, ContentStatus
from src.platforms.http_client import PlatformHttpError, publish_post

logger = get_logger(__name__)


class PublishingAgent(BaseAgent):
    """Publishes scheduled+approved content items; hard-gates unapproved/unscheduled ones."""

    name = "publishing"

    def run(self, state: CampaignState) -> CampaignState:
        """Publish every SCHEDULED item in `state.calendar`.

        Items that are not SCHEDULED are left untouched. Publishing failures are caught and
        recorded on the item/state log rather than raised, so one failure doesn't abort the
        rest of the batch.

        Args:
            state: Current campaign state.

        Returns:
            The same CampaignState with calendar items updated in place.
        """
        for item in state.calendar:
            if item.status != ContentStatus.SCHEDULED:
                continue  # hard gate: never publish unapproved/unscheduled content
            try:
                access_token = state.access_tokens.get(item.platform)
                external_id = publish_post(item.platform, item.body, access_token=access_token)
                item.external_post_id = external_id
                item.published_at = datetime.now(UTC)
                item.status = ContentStatus.PUBLISHED
                logger.info(
                    "post published",
                    extra={"platform": item.platform, "external_post_id": external_id},
                )
            except PlatformHttpError as exc:
                item.status = ContentStatus.FAILED
                state.note(f"[{self.name}] publish failed for {item.platform}: {exc}")
                logger.error("publish failed", extra={"platform": item.platform, "error": str(exc)})
        return state
