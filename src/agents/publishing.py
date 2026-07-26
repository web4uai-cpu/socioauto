"""Publishing Agent: calls platform APIs for scheduled+approved content only."""

from __future__ import annotations

from datetime import UTC, datetime

from src.agents.base import BaseAgent
from src.logging_config import get_logger
from src.orchestrator.state import CampaignState, ContentStatus
from src.platforms.delivery import deliver

logger = get_logger(__name__)


class PublishingAgent(BaseAgent):
    """Publishes scheduled+approved content items; hard-gates unapproved/unscheduled ones."""

    name = "publishing"

    def run(self, state: CampaignState) -> CampaignState:
        """Publish every SCHEDULED item in `state.calendar` that is due.

        Items that are not SCHEDULED are left untouched — the hard gate that stops unapproved
        content reaching a platform. Delivery is handled by `platforms.delivery.deliver`, which
        also owns retry scheduling and escalation, so this agent and the due-post runner cannot
        drift apart.

        Args:
            state: Current campaign state.

        Returns:
            The same CampaignState with calendar items updated in place.
        """
        now = datetime.now(UTC)
        published = 0
        escalated = 0
        for item in state.calendar:
            if item.status != ContentStatus.SCHEDULED:
                continue  # hard gate: never publish unapproved/unscheduled content
            # Respect an in-flight retry backoff rather than hammering a failing platform.
            if item.next_retry_at is not None and item.next_retry_at > now:
                continue
            if deliver(item, state.access_tokens.get(item.platform), now):
                published += 1
            elif item.needs_human:
                escalated += 1

        if escalated:
            state.note(f"[{self.name}] {escalated} item(s) escalated for human review")
        return state
