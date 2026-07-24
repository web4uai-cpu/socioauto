"""Content Strategy Agent: builds a content calendar from trends + brand voice."""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.orchestrator.state import CampaignState, ContentItem


class ContentStrategyAgent(BaseAgent):
    name = "content-strategy"

    def run(self, state: CampaignState) -> CampaignState:
        for trend in state.trends:
            for platform in state.platforms:
                state.calendar.append(ContentItem(platform=platform, topic=trend["topic"]))
        state.note(f"[{self.name}] built calendar with {len(state.calendar)} items")
        return state
