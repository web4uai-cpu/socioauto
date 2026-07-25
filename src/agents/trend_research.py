"""Trend Research Agent: discovers trending topics relevant to the brand niche."""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import CampaignState

MAX_TRENDS = 10

TRENDS_SCHEMA = {
    "type": "object",
    "properties": {
        "trends": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "score": {"type": "number"},
                    "source": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["topic", "score", "source", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["trends"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are a social media trend researcher. Only propose topics you are confident are "
    "genuinely relevant to the brand's niche. Score relevance from 0 to 1. State the source "
    "type you are reasoning from; never fabricate a specific article, URL, or metric."
)


class TrendResearchAgent(BaseAgent):
    name = "trend-research"

    def run(self, state: CampaignState) -> CampaignState:
        # Trends supplied by the caller (or a real trends API) always win.
        if not state.trends:
            state.trends = self._discover(state)
        state.note(f"[{self.name}] discovered {len(state.trends)} trends")
        return state

    def _discover(self, state: CampaignState) -> list[dict]:
        niche = state.voice_guidelines.get("niche") or state.brand_name
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Niche: {niche}\n"
            f"Target platforms: {', '.join(state.platforms) or 'general social'}\n\n"
            f"Return up to {MAX_TRENDS} current trends worth posting about, each with a "
            "relevance score between 0 and 1 and a one-line rationale."
        )
        result = get_provider().complete_json(prompt, TRENDS_SCHEMA, system=SYSTEM)
        if not result:
            return []
        return result.get("trends", [])[:MAX_TRENDS]
