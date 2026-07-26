"""Content Strategy Agent: builds a content calendar from trends + brand voice."""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import CampaignState, ContentItem, PostKind, resolve_kind

CALENDAR_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "topic": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": [k.value for k in PostKind],
                    },
                    "goal": {
                        "type": "string",
                        "enum": ["awareness", "engagement", "conversion"],
                    },
                },
                "required": ["platform", "topic", "kind", "goal"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are a social media strategist. Pair each trend with the platforms where it will "
    "actually land rather than posting everything everywhere, and balance awareness, "
    "engagement, and conversion goals across the calendar."
)


class ContentStrategyAgent(BaseAgent):
    name = "content-strategy"

    def run(self, state: CampaignState) -> CampaignState:
        planned = self._plan_with_llm(state)
        if planned:
            state.calendar.extend(planned)
        else:
            # Deterministic fallback: every trend on every requested platform.
            for trend in state.trends:
                for platform in state.platforms:
                    state.calendar.append(
                        ContentItem(
                            platform=platform,
                            topic=trend["topic"],
                            kind=resolve_kind(state.post_kind, platform),
                        )
                    )
        state.note(f"[{self.name}] built calendar with {len(state.calendar)} items")
        return state

    def _plan_with_llm(self, state: CampaignState) -> list[ContentItem]:
        if not state.trends or not state.platforms:
            return []
        topics = [trend["topic"] for trend in state.trends]
        kind_rule = (
            f"Every item must use kind '{state.post_kind}'."
            if state.post_kind
            else "Choose the kind that suits each platform and topic."
        )
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Brand voice guidelines: {state.voice_guidelines or 'professional and friendly'}\n"
            f"Available platforms: {', '.join(state.platforms)}\n"
            f"Trends to work from: {topics}\n\n"
            "Build a content calendar. Use only the listed platforms and only these trend "
            f"topics. Skip pairings that would not perform on that platform. {kind_rule}"
        )
        plan = get_provider("analysis").complete_json(prompt, CALENDAR_SCHEMA, system=SYSTEM)
        if not plan:
            return []
        allowed = set(state.platforms)
        return [
            ContentItem(
                platform=entry["platform"],
                topic=entry["topic"],
                # A caller-specified kind overrides whatever the model chose.
                kind=resolve_kind(state.post_kind or entry.get("kind", ""), entry["platform"]),
                goal=entry.get("goal", ""),
            )
            for entry in plan.get("items", [])
            if entry.get("platform") in allowed and entry.get("topic")
        ]
