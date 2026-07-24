"""Trend Research Agent: discovers trending topics relevant to the brand niche."""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.orchestrator.state import CampaignState


class TrendResearchAgent(BaseAgent):
    name = "trend-research"

    def run(self, state: CampaignState) -> CampaignState:
        # Placeholder: wire up a real trend source (platform trends API, RSS, search tool).
        state.trends = state.trends or []
        state.note(f"[{self.name}] discovered {len(state.trends)} trends")
        return state
