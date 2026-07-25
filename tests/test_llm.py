"""LLM provider selection and agent integration.

No test hits a real API: providers are either the NullProvider (no credentials configured)
or a stub injected via monkeypatch.
"""

from __future__ import annotations

import re

import pytest

from src.agents.content_creation import ContentCreationAgent
from src.agents.content_strategy import ContentStrategyAgent
from src.agents.trend_research import TrendResearchAgent
from src.llm.provider import NullProvider, get_provider, reset_provider
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    reset_provider()
    yield
    reset_provider()


class StubProvider:
    """Records prompts and returns canned responses."""

    name = "stub"

    def __init__(self, text=None, payload=None):
        self._text = text
        self._payload = payload
        self.prompts: list[str] = []

    def complete(self, prompt, *, system="", max_tokens=4096):
        self.prompts.append(prompt)
        return self._text

    def complete_json(self, prompt, schema, *, system="", max_tokens=4096):
        self.prompts.append(prompt)
        return self._payload


def test_no_credentials_yields_null_provider(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    provider = get_provider()
    assert isinstance(provider, NullProvider)
    assert provider.complete("hello") is None
    assert provider.complete_json("hello", {}) is None


def test_unsupported_provider_falls_back_to_null(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    monkeypatch.setenv("LLM_API_KEY", "key")
    assert isinstance(get_provider(), NullProvider)


def test_content_creation_uses_llm_draft(monkeypatch):
    stub = StubProvider(
        payload={
            "body": "Fresh take on AI in healthcare.",
            "hashtags": ["#AI", "HealthTech"],
            "media_brief": "Clinician reviewing a tablet.",
            "cta": "Read the guide",
        }
    )
    monkeypatch.setattr("src.agents.content_creation.get_provider", lambda: stub)

    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.calendar.append(ContentItem(platform="x", topic="AI in healthcare"))
    ContentCreationAgent().run(state)

    item = state.calendar[0]
    assert item.body == "Fresh take on AI in healthcare."
    assert item.hashtags == ["AI", "HealthTech"]  # '#' prefix stripped
    assert item.cta == "Read the guide"
    assert item.status == ContentStatus.PENDING_MODERATION


def test_content_creation_threads_long_posts_on_x(monkeypatch):
    """X supports threads, so overlong copy is split rather than truncated — nothing is lost."""
    stub = StubProvider(payload={"body": "x" * 400, "hashtags": [], "media_brief": "", "cta": ""})
    monkeypatch.setattr("src.agents.content_creation.get_provider", lambda: stub)

    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.calendar.append(ContentItem(platform="x", topic="long post"))
    ContentCreationAgent().run(state)

    item = state.calendar[0]
    assert item.thread, "expected a thread continuation"
    assert len(item.body) <= 280
    assert all(len(part) <= 280 for part in item.thread)
    # Every character of the original survives across the parts.
    recovered = "".join(re.sub(r"\s*\d+/\d+$", "", p) for p in [item.body, *item.thread])
    assert recovered.count("x") == 400


def test_content_creation_truncates_when_platform_has_no_threads(monkeypatch):
    """Instagram has no thread concept, so the limit is enforced by truncation."""
    stub = StubProvider(payload={"body": "x" * 3000, "hashtags": [], "media_brief": "", "cta": ""})
    monkeypatch.setattr("src.agents.content_creation.get_provider", lambda: stub)

    state = CampaignState(brand_name="Acme", platforms=["instagram"])
    state.calendar.append(ContentItem(platform="instagram", topic="long post"))
    ContentCreationAgent().run(state)

    assert len(state.calendar[0].body) == 2200
    assert state.calendar[0].thread == []


def test_content_creation_falls_back_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr("src.agents.content_creation.get_provider", lambda: NullProvider())

    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.calendar.append(ContentItem(platform="x", topic="fallback topic"))
    ContentCreationAgent().run(state)

    assert state.calendar[0].body == "fallback topic"
    assert state.calendar[0].status == ContentStatus.PENDING_MODERATION


def test_trend_research_populates_trends(monkeypatch):
    stub = StubProvider(
        payload={
            "trends": [
                {"topic": "AI triage", "score": 0.9, "source": "industry", "rationale": "hot"}
            ]
        }
    )
    monkeypatch.setattr("src.agents.trend_research.get_provider", lambda: stub)

    state = CampaignState(brand_name="Acme", platforms=["x"])
    TrendResearchAgent().run(state)

    assert [t["topic"] for t in state.trends] == ["AI triage"]


def test_trend_research_keeps_caller_supplied_trends(monkeypatch):
    """Supplied trends are never overwritten, but the rest of the report is still researched.

    The agent now also produces keywords/hashtags/pain points, so it consults the LLM even
    when trends are given — passing the supplied topics in rather than inventing new ones.
    """
    stub = StubProvider(
        payload={"trends": [{"topic": "generated"}], "keywords": [], "hashtags": []}
    )
    monkeypatch.setattr("src.agents.trend_research.get_provider", lambda: stub)

    state = CampaignState(brand_name="Acme", platforms=["x"], trends=[{"topic": "supplied"}])
    TrendResearchAgent().run(state)

    assert [t["topic"] for t in state.trends] == ["supplied"]
    # The supplied topic is what the research prompt was anchored to.
    assert "supplied" in stub.prompts[0]


def test_content_strategy_drops_unknown_platforms(monkeypatch):
    stub = StubProvider(
        payload={
            "items": [
                {"platform": "x", "topic": "AI triage", "goal": "awareness"},
                {"platform": "myspace", "topic": "AI triage", "goal": "awareness"},
            ]
        }
    )
    monkeypatch.setattr("src.agents.content_strategy.get_provider", lambda: stub)

    state = CampaignState(brand_name="Acme", platforms=["x"], trends=[{"topic": "AI triage"}])
    ContentStrategyAgent().run(state)

    assert [i.platform for i in state.calendar] == ["x"]


def test_content_strategy_falls_back_to_cross_product(monkeypatch):
    monkeypatch.setattr("src.agents.content_strategy.get_provider", lambda: NullProvider())

    state = CampaignState(
        brand_name="Acme",
        platforms=["x", "linkedin"],
        trends=[{"topic": "AI triage"}],
    )
    ContentStrategyAgent().run(state)

    assert len(state.calendar) == 2
