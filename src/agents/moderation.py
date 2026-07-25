"""Moderation Agent: mandatory brand-safety/compliance gate before publish."""

from __future__ import annotations

import re

from src.agents.base import BaseAgent
from src.logging_config import get_logger
from src.orchestrator.state import CampaignState, ContentStatus

logger = get_logger(__name__)

BANNED_PATTERNS = [
    r"\bguaranteed returns\b",
    r"\bmiracle cure\b",
]


class ModerationAgent(BaseAgent):
    """Mandatory gate: rejects content matching banned patterns before it can be scheduled."""

    name = "moderation"

    def run(self, state: CampaignState) -> CampaignState:
        """Review every PENDING_MODERATION item in `state.calendar` and set a verdict.

        Args:
            state: Current campaign state.

        Returns:
            The same CampaignState with each pending item marked APPROVED or REJECTED.
        """
        for item in state.calendar:
            if item.status != ContentStatus.PENDING_MODERATION:
                continue
            try:
                reasons = [p for p in BANNED_PATTERNS if re.search(p, item.body, re.IGNORECASE)]
            except re.error as exc:
                # A malformed pattern must never silently let content through.
                logger.error("moderation regex error", extra={"error": str(exc)})
                item.status = ContentStatus.REJECTED
                item.moderation_reasons = ["internal moderation error"]
                continue
            if reasons:
                item.status = ContentStatus.REJECTED
                item.moderation_reasons = reasons
                logger.info(
                    "content rejected", extra={"platform": item.platform, "reasons": reasons}
                )
            else:
                item.status = ContentStatus.APPROVED
        state.note(f"[{self.name}] reviewed {len(state.calendar)} items")
        return state
