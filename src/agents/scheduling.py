"""Scheduling Agent: picks optimal send times for approved content and queues them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.agents.base import BaseAgent
from src.orchestrator.state import CampaignState, ContentStatus
from src.scheduling.optimal_times import next_optimal_slot

# Minimum spacing between two posts on the same platform, to avoid burst-posting.
_MIN_GAP = timedelta(hours=2)


class SchedulingAgent(BaseAgent):
    name = "scheduling"

    def run(self, state: CampaignState) -> CampaignState:
        """Assign each APPROVED item the next optimal slot for its platform, spaced per platform.

        Times are computed from ``src.scheduling.optimal_times`` so posts land in high-engagement
        windows rather than a fixed offset. Items move to SCHEDULED but are not published here —
        the due-post runner (or an immediate publish step) handles delivery.
        """
        now = datetime.now(UTC)
        # Track the earliest next allowed time per platform so items don't stack up.
        cursor: dict[str, datetime] = {}
        for item in state.calendar:
            if item.status != ContentStatus.APPROVED:
                continue
            after = cursor.get(item.platform, now)
            slot = next_optimal_slot(item.platform, after)
            item.scheduled_at = slot
            item.status = ContentStatus.SCHEDULED
            cursor[item.platform] = slot + _MIN_GAP
        state.note(f"[{self.name}] scheduled approved items into optimal windows")
        return state
