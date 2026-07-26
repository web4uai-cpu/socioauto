"""Input Parser Agent: turns a raw natural-language request into a structured brief.

Runs first in the pipeline. Downstream agents read `state.brief` instead of re-reading the
raw prompt, so intent/audience/goal are resolved exactly once.
"""

from __future__ import annotations

import re

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import CampaignState

INTENTS = ("announce", "educate", "promote", "engage", "recruit", "celebrate")

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "topic": {"type": "string"},
        "goal": {"type": "string"},
        "target_audience": {"type": "string"},
        "tone": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["intent", "topic", "goal", "target_audience", "tone", "key_points", "constraints"],
    "additionalProperties": False,
}

SYSTEM = (
    "You extract structured campaign parameters from a marketer's request. Only record what "
    "the request actually states or clearly implies — never invent products, metrics, dates, "
    "or audiences that were not mentioned. Leave a field generic rather than fabricating it."
)

# Deterministic intent cues, used when no LLM is configured.
_INTENT_CUES: dict[str, tuple[str, ...]] = {
    "announce": ("announce", "launch", "introduc", "unveil", "release", "ship"),
    "promote": ("promote", "sale", "discount", "offer", "deal", "buy", "pricing"),
    "educate": ("explain", "how to", "guide", "teach", "tutorial", "tips", "learn"),
    "recruit": ("hiring", "recruit", "join our team", "career", "job"),
    "celebrate": ("celebrat", "anniversar", "milestone", "thank", "congrat"),
    "engage": ("ask", "poll", "question", "discuss", "community"),
}


class InputParserAgent(BaseAgent):
    """Extract intent and parameters from `state.raw_input` into `state.brief`."""

    name = "input-parser"

    def run(self, state: CampaignState) -> CampaignState:
        """Populate `state.brief`, and seed `state.trends` when the caller gave none.

        Args:
            state: Campaign state carrying `raw_input`.

        Returns:
            The same state with `brief` filled in.
        """
        raw = (state.raw_input or "").strip()
        if not raw:
            # Nothing to parse (e.g. a manual post) — leave the brief empty and move on.
            state.note(f"[{self.name}] no raw input to parse")
            return state

        brief = self._parse_with_llm(state, raw) or self._parse_heuristically(state, raw)
        state.brief = brief

        # Seed the research agent with the parsed topic rather than the raw prompt.
        if not state.trends:
            state.trends = [{"topic": brief["topic"], "score": 1.0, "source": "input-parser"}]

        # Voice guidelines the caller did not set explicitly are taken from the brief.
        state.voice_guidelines.setdefault("tone", brief["tone"])
        state.voice_guidelines.setdefault("audience", brief["target_audience"])

        state.note(f"[{self.name}] intent={brief['intent']} topic={brief['topic'][:40]!r}")
        return state

    def _parse_with_llm(self, state: CampaignState, raw: str) -> dict | None:
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Target platforms: {', '.join(state.platforms) or 'general social'}\n"
            f"Request: {raw}\n\n"
            "Extract the campaign brief. Use the most specific intent that fits."
        )
        result = get_provider("writing").complete_json(prompt, BRIEF_SCHEMA, system=SYSTEM)
        if not result or not result.get("topic"):
            return None
        result.setdefault("intent", "announce")
        return result

    def _parse_heuristically(self, state: CampaignState, raw: str) -> dict:
        """Rule-based fallback so the pipeline stays runnable without an LLM."""
        lowered = raw.lower()
        intent = next(
            (name for name, cues in _INTENT_CUES.items() if any(c in lowered for c in cues)),
            "announce",
        )
        # First sentence is the topic; the rest become key points.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw) if s.strip()]
        topic = sentences[0] if sentences else raw
        return {
            "intent": intent,
            "topic": topic[:200],
            "goal": f"{intent} to the brand's audience",
            "target_audience": state.voice_guidelines.get("audience") or "the brand's audience",
            "tone": state.voice_guidelines.get("tone") or "professional",
            "key_points": sentences[1:4],
            "constraints": [],
        }
