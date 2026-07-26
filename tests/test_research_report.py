"""Phase 2 research report: keywords, hashtags, pain points, and its handoff to SEO."""

from src.agents.seo import SEOAgent
from src.agents.trend_research import (
    MAX_HASHTAGS,
    TARGET_KEYWORDS,
    TrendResearchAgent,
)
from src.orchestrator.state import CampaignState, ContentItem


class _Stub:
    """Stands in for a configured LLM."""

    name = "stub"

    def __init__(self, payload):
        self.payload = payload
        self.prompts: list[str] = []

    def complete_json(self, prompt, schema, *, system="", max_tokens=4096):
        self.prompts.append(prompt)
        return self.payload

    def complete(self, prompt, *, system="", max_tokens=4096):
        return None


def _state(**kwargs) -> CampaignState:
    kwargs.setdefault("platforms", ["x"])
    return CampaignState(brand_name="Acme Health", **kwargs)


# --- Report shape ---------------------------------------------------------------------


def test_report_is_produced_without_an_llm():
    """The deterministic path must still yield a usable report."""
    state = _state(brief={"topic": "AI in healthcare for doctors", "key_points": []})
    state = TrendResearchAgent().run(state)

    research = state.research
    assert research["source"] == "fallback"
    assert research["keywords"], "keywords should be derived from the topic"
    assert research["hashtags"]
    # Nothing external was consulted, so these must stay empty rather than be invented.
    assert research["competitors"] == []
    assert research["search_volumes"] == []


def test_pain_points_are_never_invented_without_an_llm():
    state = TrendResearchAgent().run(_state(brief={"topic": "AI in healthcare"}))
    assert state.research["pain_points"] == []


def test_llm_report_populates_every_section(monkeypatch):
    stub = _Stub(
        {
            "trends": [
                {"topic": "AI triage", "score": 0.9, "source": "industry", "rationale": "r"}
            ],
            "keywords": [
                {"term": "ai triage", "intent": "informational", "rationale": "r"},
                {"term": "clinical ai", "intent": "commercial", "rationale": "r"},
            ],
            "hashtags": ["#AITriage", "clinicalai", "AITriage"],
            "pain_points": ["Too much admin time", "Diagnostic uncertainty"],
        }
    )
    monkeypatch.setattr("src.agents.trend_research.get_provider", lambda *_: stub)

    state = TrendResearchAgent().run(_state())
    research = state.research

    assert research["source"] == "llm"
    assert [k["term"] for k in research["keywords"]] == ["ai triage", "clinical ai"]
    assert research["pain_points"] == ["Too much admin time", "Diagnostic uncertainty"]
    # '#' stripped, lowercased, and the duplicate dropped.
    assert research["hashtags"] == ["aitriage", "clinicalai"]


def test_hashtags_are_capped_and_keywords_bounded(monkeypatch):
    stub = _Stub(
        {
            "trends": [],
            "keywords": [
                {"term": f"kw{i}", "intent": "informational", "rationale": "r"} for i in range(40)
            ],
            "hashtags": [f"tag{i}" for i in range(40)],
            "pain_points": [],
        }
    )
    monkeypatch.setattr("src.agents.trend_research.get_provider", lambda *_: stub)

    research = TrendResearchAgent().run(_state()).research
    assert len(research["hashtags"]) == MAX_HASHTAGS
    assert len(research["keywords"]) == TARGET_KEYWORDS


def test_report_survives_serialization_roundtrip():
    state = TrendResearchAgent().run(_state(brief={"topic": "AI in healthcare"}))
    restored = CampaignState.from_dict(state.to_dict())
    assert restored.research == state.research


# --- Handoff into the SEO Agent ---------------------------------------------------------


def test_seo_prefers_researched_keywords_present_in_the_post():
    state = _state()
    state.research = {
        "keywords": [{"term": "triage", "intent": "informational", "rationale": "r"}],
        "hashtags": ["clinicalai"],
        "pain_points": [],
    }
    state.calendar = [ContentItem(platform="x", topic="Faster triage", body="Faster triage today")]
    state = SEOAgent().run(state)

    assert state.calendar[0].seo["primary_keyword"] == "triage"


def test_seo_falls_back_when_no_researched_keyword_fits():
    """A research keyword that does not appear in the post must not be forced onto it."""
    state = _state()
    state.research = {
        "keywords": [{"term": "unrelated", "intent": "informational", "rationale": "r"}],
        "hashtags": [],
        "pain_points": [],
    }
    state.calendar = [ContentItem(platform="x", topic="Scheduling tools", body="Ship faster.")]
    state = SEOAgent().run(state)

    assert state.calendar[0].seo["primary_keyword"] == "scheduling"


def test_research_hashtags_reach_the_post():
    state = _state()
    state.research = {"keywords": [], "hashtags": ["clinicalai"], "pain_points": []}
    state.calendar = [ContentItem(platform="x", topic="Triage", body="body")]
    state = SEOAgent().run(state)

    assert "clinicalai" in state.calendar[0].hashtags


def test_seo_works_with_an_empty_research_report():
    """Manual posts never run research, so SEO must not depend on it."""
    state = _state()
    state.calendar = [ContentItem(platform="x", topic="Scheduling tools", body="Ship faster.")]
    state = SEOAgent().run(state)

    assert state.calendar[0].seo["primary_keyword"]


def test_full_pipeline_carries_research_into_hashtags():
    from src.orchestrator.graph import run_campaign

    state = CampaignState(
        brand_name="Acme Health",
        platforms=["x"],
        raw_input="Announce our AI triage assistant for doctors",
    )
    state = run_campaign(state)

    assert state.research["keywords"]
    assert state.calendar[0].hashtags
