"""Content Creation Agent: drafts copy/media brief per calendar item."""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.orchestrator.state import CampaignState

PLATFORM_LIMITS = {"x": 280, "instagram": 2200, "linkedin": 3000, "tiktok": 2200, "facebook": 5000}


class ContentCreationAgent(BaseAgent):
    name = "content-creation"

    def run(self, state: CampaignState) -> CampaignState:
        for item in state.calendar:
            if item.body:
                continue
            limit = PLATFORM_LIMITS.get(item.platform, 280)
            draft = f"{item.topic}"[:limit]
            item.body = draft
            item.status = item.status.__class__.PENDING_MODERATION
        state.note(f"[{self.name}] drafted content for {len(state.calendar)} items")
        return state
