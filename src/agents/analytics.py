"""Analytics Agent: collects performance metrics and feeds back into strategy."""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.orchestrator.state import CampaignState, ContentStatus


class AnalyticsAgent(BaseAgent):
    name = "analytics"

    def run(self, state: CampaignState) -> CampaignState:
        published = [i for i in state.calendar if i.status == ContentStatus.PUBLISHED]
        state.analytics.append({"published_count": len(published)})
        state.note(f"[{self.name}] recorded snapshot for {len(published)} published items")
        return state
