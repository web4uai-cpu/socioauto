"""Content Creation Agent: drafts copy/media brief per calendar item."""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus

PLATFORM_LIMITS = {"x": 280, "instagram": 2200, "linkedin": 3000, "tiktok": 2200, "facebook": 5000}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "body": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "media_brief": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["body", "hashtags", "media_brief", "cta"],
    "additionalProperties": False,
}

SYSTEM = (
    "You write social media copy for a brand. Respect the brand voice, the platform's "
    "conventions, and the character limit exactly. Never invent statistics, prices, or "
    "claims about people. Hashtags must not include the '#' prefix."
)


class ContentCreationAgent(BaseAgent):
    name = "content-creation"

    def run(self, state: CampaignState) -> CampaignState:
        provider = get_provider()
        generated = 0
        for item in state.calendar:
            if item.body:
                continue
            limit = PLATFORM_LIMITS.get(item.platform, 280)
            if self._draft_with_llm(provider, state, item, limit):
                generated += 1
            else:
                # Deterministic fallback keeps the pipeline runnable without an LLM.
                item.body = f"{item.topic}"[:limit]
            item.status = ContentStatus.PENDING_MODERATION
        state.note(
            f"[{self.name}] drafted content for {len(state.calendar)} items "
            f"({generated} via {provider.name})"
        )
        return state

    def _draft_with_llm(
        self, provider, state: CampaignState, item: ContentItem, limit: int
    ) -> bool:
        """Populate `item` from the LLM. Returns False when generation is unavailable."""
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Brand voice guidelines: {state.voice_guidelines or 'professional and friendly'}\n"
            f"Platform: {item.platform}\n"
            f"Character limit for the body: {limit}\n"
            f"Topic: {item.topic}\n\n"
            "Write one post. Return the body, 3-8 hashtags, a one-sentence media brief "
            "describing the visual, and a short call to action."
        )
        draft = provider.complete_json(prompt, DRAFT_SCHEMA, system=SYSTEM)
        if not draft or not draft.get("body"):
            return False
        item.body = draft["body"][:limit]
        item.hashtags = [tag.lstrip("#") for tag in draft.get("hashtags", [])]
        item.media_brief = draft.get("media_brief", "")
        item.cta = draft.get("cta", "")
        return True
