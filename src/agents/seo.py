"""SEO Agent: optimizes each item for search/discovery and lead generation.

Runs last in the generation chain so it can see the final copy, visual, and video. It fills
`item.seo` and may tighten `item.hashtags` — but never rewrites `item.body`, so moderation
still reviews the copy the content agent actually produced.
"""

from __future__ import annotations

import re

from src.agents.base import BaseAgent
from src.agents.content_creation import spec_for
from src.llm.provider import get_provider
from src.orchestrator.state import CampaignState, ContentItem
from src.seo.readability import flesch_reading_ease, readability_label, seo_score

# Hashtag counts that perform on each platform; over-tagging suppresses reach on some.
# Instagram rewards a dense tag set (AGENT_WORKFLOW.md Phase 3 targets 15-20); the others
# do not, and stuffing them there costs reach.
PLATFORM_HASHTAG_LIMIT: dict[str, int] = {
    "instagram": 20,
    "tiktok": 6,
    "x": 3,
    "linkedin": 5,
    "facebook": 3,
    # YouTube indexes description tags for search; Shorts surfaces on the feed, not search.
    "youtube": 15,
    "youtube_shorts": 5,
}
DEFAULT_HASHTAG_LIMIT = 5
META_DESCRIPTION_LIMIT = 155

# Lead-capture formats suggested by the deterministic path. These are generic *formats*, not
# claims about anything the brand actually offers.
_LEAD_MAGNETS_BY_GOAL: dict[str, str] = {
    "conversion": "free trial or demo booking",
    "engagement": "poll or AMA sign-up",
    "awareness": "newsletter subscription",
}
_DEFAULT_LEAD_MAGNET = "downloadable checklist or template"

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
            seo = self._optimize_with_llm(provider, state, item) or self._fallback(state, item)
            seo["slug"] = _slugify(seo.get("primary_keyword") or item.topic)
            seo["meta_description"] = seo.get("meta_description", "")[:META_DESCRIPTION_LIMIT]
            item.seo = seo

            # Merge the content agent's hashtags, the SEO agent's, and the campaign-level
            # research set — in that order of specificity — then cap per platform.
            limit = PLATFORM_HASHTAG_LIMIT.get(item.platform, DEFAULT_HASHTAG_LIMIT)
            merged = list(
                dict.fromkeys(
                    item.hashtags
                    + [t.lstrip("#") for t in seo.get("hashtags", [])]
                    + self._research_hashtags(state)
                )
            )
            item.hashtags = [t for t in merged if t][:limit]

            # Score the finished post. Done after hashtags are settled so the count is real.
            self._score(item, limit)
            optimized += 1

        state.note(f"[{self.name}] optimized {optimized} items")
        return state

    def _score(self, item: ContentItem, hashtag_target: int) -> None:
        """Attach readability and a transparent on-page SEO score to `item.seo`."""
        # Score the whole post, including any thread continuation.
        full_text = " ".join([item.body, *item.thread])
        readability = flesch_reading_ease(full_text)
        result = seo_score(
            body=full_text,
            primary_keyword=item.seo.get("primary_keyword", ""),
            hashtags=item.hashtags,
            hashtag_target=hashtag_target,
            has_cta=bool(item.cta or item.seo.get("lead_cta")),
            readability=readability,
            word_range=spec_for(item.platform).word_range,
        )
        item.seo["readability"] = readability
        item.seo["readability_label"] = readability_label(readability)
        item.seo["score"] = result["score"]
        item.seo["passed_checks"] = result["passed"]
        item.seo["suggestions"] = result["suggestions"]

    def _research_keywords(self, state: CampaignState) -> list[str]:
        """Keyword terms the Research Agent found for this campaign."""
        return [
            entry["term"]
            for entry in state.research.get("keywords", [])
            if isinstance(entry, dict) and entry.get("term")
        ]

    def _research_hashtags(self, state: CampaignState) -> list[str]:
        return [tag for tag in state.research.get("hashtags", []) if tag]

    def _optimize_with_llm(self, provider, state: CampaignState, item: ContentItem) -> dict | None:
        goal = state.brief.get("goal", "grow reach")
        audience = state.brief.get("target_audience") or state.voice_guidelines.get(
            "audience", "the brand's audience"
        )
        tag_limit = PLATFORM_HASHTAG_LIMIT.get(item.platform, DEFAULT_HASHTAG_LIMIT)
        researched = self._research_keywords(state)
        pain_points = state.research.get("pain_points", [])
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Platform: {item.platform}\n"
            f"Campaign goal: {goal}\n"
            f"Target audience: {audience}\n"
            f"Post body: {item.body}\n"
            f"Current hashtags: {', '.join(item.hashtags) or 'none'}\n"
            f"Researched keywords: {', '.join(researched) or 'none'}\n"
            f"Audience pain points: {'; '.join(pain_points) or 'none'}\n\n"
            "Prefer the researched keywords where they fit this post naturally. "
            f"Return SEO metadata. Meta description must be under {META_DESCRIPTION_LIMIT} "
            f"characters. Suggest at most {tag_limit} hashtags."
        )
        result = provider.complete_json(prompt, SEO_SCHEMA, system=SYSTEM)
        if not result or not result.get("primary_keyword"):
            return None
        result["source"] = provider.name
        return result

    def _fallback(self, state: CampaignState, item: ContentItem) -> dict:
        """Used when no LLM is configured.

        Prefers the Research Agent's keywords that actually appear in this post, so the
        campaign-level research still drives per-item SEO; falls back to extracting from the
        topic when research produced nothing relevant.
        """
        haystack = f"{item.topic} {item.body}".lower()
        keywords = [term for term in self._research_keywords(state) if term in haystack][:6]
        if not keywords:
            words = [
                w for w in re.findall(r"[a-z][a-z0-9']+", item.topic.lower()) if w not in _STOPWORDS
            ]
            keywords = list(dict.fromkeys(words))[:6]
        primary = keywords[0] if keywords else item.topic.lower()[:40]
        body = item.body or item.topic
        goal = item.goal or state.brief.get("goal", "")
        return {
            "primary_keyword": primary,
            "keywords": keywords,
            "hashtags": [k.replace(" ", "") for k in keywords[:3]],
            "meta_description": body[:META_DESCRIPTION_LIMIT],
            # A generic capture format matched to the campaign goal — never a claim that the
            # brand actually offers this, which is why it reads as a suggestion.
            "lead_magnet": _LEAD_MAGNETS_BY_GOAL.get(goal, _DEFAULT_LEAD_MAGNET),
            "lead_form_fields": ["email"] if goal == "awareness" else ["name", "email"],
            "lead_cta": item.cta or "Learn more on our site.",
            "source": "fallback",
        }
