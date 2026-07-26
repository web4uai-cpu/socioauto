"""Engagement Agent: drafts responses to inbound comments/DMs, flags escalations."""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import CampaignState

# Anything touching these goes to a human instead of getting an auto-drafted reply.
ESCALATION_KEYWORDS = ["lawsuit", "lawyer", "scam", "refund", "complaint"]

MAX_REPLY_CHARS = 500

SYSTEM = (
    "You reply to inbound social media messages on behalf of a brand. Be brief, warm, and "
    "specific. Never promise refunds, discounts, delivery dates, or legal outcomes, and "
    "never invent order details. If you cannot help concretely, acknowledge the message and "
    "say a team member will follow up."
)


def needs_escalation(message: str) -> bool:
    """True when a message must be handled by a human rather than auto-answered."""
    lowered = message.lower()
    return any(keyword in lowered for keyword in ESCALATION_KEYWORDS)


class EngagementAgent(BaseAgent):
    name = "engagement"

    def draft_reply(
        self, message: str, *, brand_name: str = "", voice_guidelines: dict | None = None
    ) -> tuple[str | None, bool]:
        """Draft a reply to one inbound message.

        Returns `(draft, escalated)`. An escalated message gets no draft — putting words in
        a human's mouth on a legal or refund complaint is worse than an empty queue item.
        """
        if needs_escalation(message):
            return None, True

        prompt = (
            f"Brand: {brand_name or 'the brand'}\n"
            f"Brand voice guidelines: {voice_guidelines or 'professional and friendly'}\n"
            f"Inbound message: {message}\n\n"
            f"Write a single reply of at most {MAX_REPLY_CHARS} characters."
        )
        draft = get_provider("writing").complete(prompt, system=SYSTEM, max_tokens=2048)
        return (draft[:MAX_REPLY_CHARS] if draft else None), False

    def run(self, state: CampaignState) -> CampaignState:
        # Inbound engagements arrive via platform webhooks and are processed out-of-band by
        # `engagement.process_inbound` (src/orchestrator/tasks.py), not in the campaign graph.
        state.note(f"[{self.name}] processed inbound engagements")
        return state
