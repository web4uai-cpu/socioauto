"""SEO Agent: optimizes each item for search/discovery and lead generation.

Runs last in the generation chain so it can see the final copy, visual, and video. It fills
`item.seo` and may tighten `item.hashtags` — but never rewrites `item.body`, so moderation
still reviews the copy the content agent actually produced.
"""

from __future__ import annotations

import re

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import CampaignState, ContentItem

# Hashtag counts that perform on each platform; over-tagging suppresses reach on some.
PLATFORM_HASHTAG_LIMIT: dict[str, int] = {
    "instagram": 12,
    "tiktok": 6,
    "x": 3,
    "linkedin": 5,
    "facebook": 3,
}
DEFAULT_HASHTAG_LIMIT = 5
META_DESCRIPTION_LIMIT = 155

SEO_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_keyword": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "meta_description": {"type": "string"},
        "lead_magnet": {"type": "string"},
        "lead_cta": {"type": "string"},
    },
    "required": [
        "primary_keyword",
        "keywords",
        "hashtags",
        "meta_description",
        "lead_magnet",
        "lead_cta",
    ],
    "additionalProperties": False,
}

SYSTEM = (
    "You optimize social posts for search and lead generation. Choose keywords a real person "
    "would search for. Never keyword-stuff, never promise outcomes the brand did not state, "
    "and never invent a lead magnet that was not mentioned — suggest a generic one instead. "
    "Hashtags must not include the '#' prefix."
)

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "for",
    "with",
    "our",
    "your",
    "we",
    "you",
    "to",
    "of",
    "in",
    "on",
    "is",
    "are",
    "it",
    "this",
    "that",
    "new",
    "now",
    "just",
    "get",
    # Campaign action verbs describe what we're doing, not what the post is *about* —
    # excluding them keeps the extracted keyword on the subject matter.
    "announce",
    "announcing",
    "introduce",
    "introducing",
    "launch",
    "launching",
    "unveil",
    "unveiling",
    "release",
    "releasing",
    "presenting",
    "sharing",
}


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60]


class SEOAgent(BaseAgent):
    """Attach keywords, meta description, slug, and a lead-gen CTA to every item."""

    name = "seo"

    def run(self, state: CampaignState) -> CampaignState:
        """Populate `item.seo` and normalize `item.hashtags` to the platform's limit.

        Args:
            state: Campaign state with drafted content.

        Returns:
            The same state with SEO metadata attached.
        """
        provider = get_provider()
        optimized = 0
        for item in state.calendar:
            if item.seo:
                continue
            seo = self._optimize_with_llm(provider, state, item) or self._fallback(item)
            seo["slug"] = _slugify(seo.get("primary_keyword") or item.topic)
            seo["meta_description"] = seo.get("meta_description", "")[:META_DESCRIPTION_LIMIT]
            item.seo = seo

            # Merge SEO hashtags with the content agent's, dedupe, and cap per platform.
            limit = PLATFORM_HASHTAG_LIMIT.get(item.platform, DEFAULT_HASHTAG_LIMIT)
            merged = list(
                dict.fromkeys(item.hashtags + [t.lstrip("#") for t in seo.get("hashtags", [])])
            )
            item.hashtags = [t for t in merged if t][:limit]
            optimized += 1

        state.note(f"[{self.name}] optimized {optimized} items")
        return state

    def _optimize_with_llm(self, provider, state: CampaignState, item: ContentItem) -> dict | None:
        goal = state.brief.get("goal", "grow reach")
        audience = state.brief.get("target_audience") or state.voice_guidelines.get(
            "audience", "the brand's audience"
        )
        tag_limit = PLATFORM_HASHTAG_LIMIT.get(item.platform, DEFAULT_HASHTAG_LIMIT)
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Platform: {item.platform}\n"
            f"Campaign goal: {goal}\n"
            f"Target audience: {audience}\n"
            f"Post body: {item.body}\n"
            f"Current hashtags: {', '.join(item.hashtags) or 'none'}\n\n"
            f"Return SEO metadata. Meta description must be under {META_DESCRIPTION_LIMIT} "
            f"characters. Suggest at most {tag_limit} hashtags."
        )
        result = provider.complete_json(prompt, SEO_SCHEMA, system=SYSTEM)
        if not result or not result.get("primary_keyword"):
            return None
        result["source"] = provider.name
        return result

    def _fallback(self, item: ContentItem) -> dict:
        """Frequency-based keyword extraction, used when no LLM is configured."""
        words = [
            w for w in re.findall(r"[a-z][a-z0-9']+", item.topic.lower()) if w not in _STOPWORDS
        ]
        keywords = list(dict.fromkeys(words))[:6]
        primary = keywords[0] if keywords else item.topic.lower()[:40]
        body = item.body or item.topic
        return {
            "primary_keyword": primary,
            "keywords": keywords,
            "hashtags": [k.replace(" ", "") for k in keywords[:3]],
            "meta_description": body[:META_DESCRIPTION_LIMIT],
            "lead_magnet": "",
            "lead_cta": item.cta or "Learn more on our site.",
            "source": "fallback",
        }
