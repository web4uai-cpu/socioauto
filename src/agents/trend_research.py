"""Research Agent: trends, keywords, hashtags, and audience pain points for a campaign.

Produces the ResearchReport that Phase 2 of docs/AGENT_WORKFLOW.md describes. Everything here
is *derived*, not measured: there is no live trends API, no web scraping, and no competitor
data source wired up. Fields that would require real external data (`competitors`, search
volumes, engagement counts) stay empty rather than being invented — see `_EXTERNAL_SOURCES`.
"""

from __future__ import annotations

import re
from typing import Any

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.logging_config import get_logger
from src.orchestrator.state import CampaignState

logger = get_logger(__name__)

MAX_TRENDS = 10
TARGET_KEYWORDS = 20
MIN_HASHTAGS = 15
MAX_HASHTAGS = 20

# Report fields that need a real data source. Documented here so a future provider knows
# exactly what to fill, and so nothing downstream mistakes "empty" for "researched and none".
_EXTERNAL_SOURCES = ("competitors", "search_volumes")

RESEARCH_SCHEMA = {
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
        },
        "keywords": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "intent": {
                        "type": "string",
                        "enum": ["informational", "commercial", "navigational"],
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["term", "intent", "rationale"],
                "additionalProperties": False,
            },
        },
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "pain_points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["trends", "keywords", "hashtags", "pain_points"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are a social media researcher. Only propose topics, keywords, and audience pain "
    "points you are confident are genuinely relevant to the brand's niche. Score relevance "
    "from 0 to 1 and state the source type you are reasoning from. Never fabricate a specific "
    "article, URL, search volume, follower count, or competitor metric — you have no live "
    "data. Hashtags must not include the '#' prefix."
)

_STOPWORDS = {
    # Instruction verbs from the user's request describe the *task*, not the subject, so
    # they must not become campaign keywords ("create a campaign about X" -> X).
    "create",
    "campaign",
    "post",
    "write",
    "make",
    "generate",
    "announce",
    "need",
    "want",
    "please",
    "the",
    "a",
    "an",
    "and",
    "or",
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
    "about",
    "from",
    "how",
}


def _clean_tag(tag: str) -> str:
    """Normalise a hashtag: strip '#', drop non-alphanumerics, lowercase."""
    return re.sub(r"[^a-z0-9]", "", tag.lstrip("#").lower())


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9']+", text.lower()) if w not in _STOPWORDS]


class TrendResearchAgent(BaseAgent):
    """Build the campaign's research report before any content is planned."""

    name = "trend-research"

    def run(self, state: CampaignState) -> CampaignState:
        """Populate `state.trends` and `state.research`.

        Caller-supplied trends always win, so an integration that already has real trend data
        can inject it and still get keywords/hashtags derived from it.
        """
        report = self._research_with_llm(state) or {}

        # Trends supplied by the caller (or a real trends API) always win.
        if not state.trends:
            state.trends = report.get("trends") or self._fallback_trends(state)

        keywords = report.get("keywords") or self._fallback_keywords(state)
        hashtags = report.get("hashtags") or [k["term"] for k in keywords]

        state.research = {
            "keywords": keywords[:TARGET_KEYWORDS],
            "hashtags": self._normalise_hashtags(hashtags),
            # Pain points are never guessed: with no LLM there is nothing honest to put here.
            "pain_points": report.get("pain_points", [])[:10],
            "source": "llm" if report else "fallback",
            # Left empty until a real data source is configured; see _EXTERNAL_SOURCES.
            **{field: [] for field in _EXTERNAL_SOURCES},
        }

        state.note(
            f"[{self.name}] {len(state.trends)} trends, "
            f"{len(state.research['keywords'])} keywords, "
            f"{len(state.research['hashtags'])} hashtags"
        )
        return state

    def _research_with_llm(self, state: CampaignState) -> dict[str, Any] | None:
        """Research the brief, retrying once with broader terms before giving up.

        A narrow niche is the usual reason a research call comes back empty, so the retry
        drops the niche qualifier and widens the ask rather than repeating the same query.
        """
        result = self._attempt(state, broaden=False)
        if result:
            return result
        logger.info("research returned nothing; retrying with broader terms")
        return self._attempt(state, broaden=True)

    def _attempt(self, state: CampaignState, *, broaden: bool) -> dict[str, Any] | None:
        niche = state.voice_guidelines.get("niche") or state.brand_name
        if broaden:
            # Widen to the parent category and drop platform/audience constraints.
            niche = f"the broader category around {niche}"
        audience = state.brief.get("target_audience") or state.voice_guidelines.get(
            "audience", "the brand's audience"
        )
        known = [t["topic"] for t in state.trends] if state.trends else []
        trend_rule = (
            f"Use these topics rather than inventing new ones: {known}"
            if known
            else f"Return up to {MAX_TRENDS} current trends worth posting about."
        )
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Niche: {niche}\n"
            f"Target audience: {audience}\n"
            f"Target platforms: {', '.join(state.platforms) or 'general social'}\n\n"
            f"{trend_rule}\n"
            f"Also return {TARGET_KEYWORDS} high-value keywords this audience would actually "
            f"search for, {MIN_HASHTAGS}-{MAX_HASHTAGS} hashtags, and the audience's main pain "
            "points that this brand can credibly speak to."
        )
        result = get_provider().complete_json(prompt, RESEARCH_SCHEMA, system=SYSTEM)
        if not result:
            return None
        result["trends"] = result.get("trends", [])[:MAX_TRENDS]
        return result

    def _fallback_trends(self, state: CampaignState) -> list[dict[str, Any]]:
        """With no LLM and no supplied trends, the parsed topic is the only honest signal."""
        topic = state.brief.get("topic")
        if not topic:
            return []
        return [{"topic": topic, "score": 1.0, "source": "input-parser", "rationale": ""}]

    def _fallback_keywords(self, state: CampaignState) -> list[dict[str, str]]:
        """Frequency-based extraction from the topics and brief, used with no LLM."""
        text = " ".join(
            [
                *(t.get("topic", "") for t in state.trends),
                state.brief.get("topic", ""),
                *state.brief.get("key_points", []),
            ]
        )
        terms = list(dict.fromkeys(_words(text)))[:TARGET_KEYWORDS]
        return [
            {"term": term, "intent": "informational", "rationale": "derived from campaign topic"}
            for term in terms
        ]

    def _normalise_hashtags(self, raw: list[Any]) -> list[str]:
        """Dedupe, strip '#', drop empties, and cap to the target range."""
        tags: list[str] = []
        for entry in raw:
            tag = _clean_tag(entry if isinstance(entry, str) else str(entry.get("term", "")))
            if tag and tag not in tags:
                tags.append(tag)
        return tags[:MAX_HASHTAGS]
