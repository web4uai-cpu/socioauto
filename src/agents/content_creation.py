"""Content Creation Agent: drafts platform-native copy for each calendar item.

Each platform gets its own length target and editorial style (see `PLATFORM_SPECS`), because
the same copy does not work on LinkedIn and TikTok. Where a platform supports threads, copy
that overruns the character limit is **split into a thread rather than truncated** — losing
the end of a post is worse than posting it in two parts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus

# Room left for the " 1/n" counter appended to each thread part.
_THREAD_COUNTER_ROOM = 8
MAX_THREAD_PARTS = 10


@dataclass(frozen=True)
class PlatformSpec:
    """How copy should be shaped for one platform."""

    char_limit: int
    style: str
    # Target length in words, when the platform rewards a particular range.
    word_range: tuple[int, int] | None = None
    supports_thread: bool = False


PLATFORM_SPECS: dict[str, PlatformSpec] = {
    "instagram": PlatformSpec(
        2200,
        "Visual-first and personable. Lead with a hook line, then short paragraphs.",
        word_range=(125, 150),
    ),
    "x": PlatformSpec(
        280,
        "Punchy and conversational. One idea per post.",
        supports_thread=True,
    ),
    "linkedin": PlatformSpec(
        3000,
        "Professional and insight-led. Concrete specifics, no hype, no emoji spam.",
        word_range=(150, 300),
    ),
    "facebook": PlatformSpec(
        5000,
        "Engaging and community-focused. Invite replies and discussion.",
        word_range=(80, 160),
    ),
    "tiktok": PlatformSpec(
        2200,
        "Casual and fast. Front-load the hook; the caption supports the video.",
        word_range=(20, 60),
    ),
}
DEFAULT_SPEC = PlatformSpec(280, "Clear and concise.")

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


def spec_for(platform: str) -> PlatformSpec:
    return PLATFORM_SPECS.get(platform, DEFAULT_SPEC)


def split_into_thread(body: str, limit: int) -> list[str]:
    """Split `body` into numbered thread parts that each fit within `limit`.

    Splits on sentence boundaries where possible so parts read naturally; a single sentence
    longer than the limit is hard-wrapped on whitespace as a last resort.
    """
    room = limit - _THREAD_COUNTER_ROOM
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body.strip()) if s.strip()]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > room:
            # Sentence too long on its own — break it on the last space that fits.
            cut = sentence.rfind(" ", 0, room)
            cut = cut if cut > 0 else room
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= room:
            current = candidate
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)

    chunks = [c for c in chunks if c][:MAX_THREAD_PARTS]
    if len(chunks) <= 1:
        return chunks
    total = len(chunks)
    return [f"{chunk} {i}/{total}" for i, chunk in enumerate(chunks, start=1)]


class ContentCreationAgent(BaseAgent):
    name = "content-creation"

    def run(self, state: CampaignState) -> CampaignState:
        """Draft copy for every item that does not already have a body."""
        provider = get_provider()
        generated = 0
        threaded = 0
        for item in state.calendar:
            if item.body:
                continue
            spec = spec_for(item.platform)
            if self._draft_with_llm(provider, state, item, spec):
                generated += 1
            else:
                # Deterministic fallback keeps the pipeline runnable without an LLM.
                item.body = item.topic
            if self._fit_to_limit(item, spec):
                threaded += 1
            item.status = ContentStatus.PENDING_MODERATION

        note = (
            f"[{self.name}] drafted content for {len(state.calendar)} items "
            f"({generated} via {provider.name})"
        )
        state.note(f"{note}, {threaded} threaded" if threaded else note)
        return state

    def _fit_to_limit(self, item: ContentItem, spec: PlatformSpec) -> bool:
        """Bring `item.body` within the platform limit. Returns True if it became a thread."""
        if len(item.body) <= spec.char_limit:
            return False
        if spec.supports_thread:
            parts = split_into_thread(item.body, spec.char_limit)
            if len(parts) > 1:
                item.body = parts[0]
                item.thread = parts[1:]
                return True
        item.body = item.body[: spec.char_limit]
        return False

    def _draft_with_llm(
        self, provider, state: CampaignState, item: ContentItem, spec: PlatformSpec
    ) -> bool:
        """Populate `item` from the LLM. Returns False when generation is unavailable."""
        if spec.word_range:
            length = f"Target {spec.word_range[0]}-{spec.word_range[1]} words."
        elif spec.supports_thread:
            length = (
                f"Keep it under {spec.char_limit} characters if you can; if the idea genuinely "
                "needs more room, write it in full and it will be split into a thread."
            )
        else:
            length = f"Stay under {spec.char_limit} characters."

        pain_points = state.research.get("pain_points", [])
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Brand voice guidelines: {state.voice_guidelines or 'professional and friendly'}\n"
            f"Platform: {item.platform}\n"
            f"Platform style: {spec.style}\n"
            f"Character limit: {spec.char_limit}. {length}\n"
            f"Topic: {item.topic}\n"
            f"Campaign goal: {item.goal or state.brief.get('goal', 'grow reach')}\n"
            f"Audience pain points to speak to: {'; '.join(pain_points) or 'unknown'}\n\n"
            "Write one post. Return the body, 3-8 hashtags, a one-sentence media brief "
            "describing the visual, and a short call to action."
        )
        draft = provider.complete_json(prompt, DRAFT_SCHEMA, system=SYSTEM)
        if not draft or not draft.get("body"):
            return False
        item.body = draft["body"]
        item.hashtags = [tag.lstrip("#") for tag in draft.get("hashtags", [])]
        item.media_brief = draft.get("media_brief", "")
        item.cta = draft.get("cta", "")
        return True
