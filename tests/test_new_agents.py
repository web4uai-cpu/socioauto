"""Input Parser, Visual, Video, and SEO agents, plus their place in the pipeline.

These run with no LLM configured, so they exercise each agent's deterministic fallback —
the path that must keep the pipeline runnable without credentials.
"""

import pytest

from src.agents.input_parser import InputParserAgent
from src.agents.seo import PLATFORM_HASHTAG_LIMIT, SEOAgent
from src.agents.video import VIDEO_PLATFORMS, VideoAgent
from src.agents.visual import PLATFORM_VISUAL_SPEC, VisualAgent
from src.orchestrator.graph import PIPELINE, PRE_APPROVAL_PIPELINE
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus, PostKind


def _state(**kwargs) -> CampaignState:
    kwargs.setdefault("platforms", ["x"])
    return CampaignState(brand_name="Acme AI", **kwargs)


# --- Input Parser ------------------------------------------------------------------


def test_input_parser_extracts_intent_and_seeds_trends():
    state = _state(raw_input="Announce our new scheduling feature to enterprise buyers.")
    state = InputParserAgent().run(state)

    assert state.brief["intent"] == "announce"
    assert "scheduling feature" in state.brief["topic"]
    # Research agent is seeded from the parsed topic, not the raw prompt.
    assert state.trends[0]["source"] == "input-parser"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("How to automate your social posting", "educate"),
        ("We're hiring a senior engineer", "recruit"),
        ("50% discount this week only", "promote"),
        ("Celebrating our 10th anniversary", "celebrate"),
    ],
)
def test_input_parser_classifies_intents(text, expected):
    state = InputParserAgent().run(_state(raw_input=text))
    assert state.brief["intent"] == expected


def test_input_parser_no_ops_without_raw_input():
    """Manual posts carry no raw prompt — the parser must leave the state alone."""
    state = InputParserAgent().run(_state())
    assert state.brief == {}
    assert state.trends == []


def test_input_parser_does_not_override_caller_supplied_trends():
    state = _state(raw_input="Announce a thing", trends=[{"topic": "given", "score": 0.5}])
    state = InputParserAgent().run(state)
    assert state.trends[0]["topic"] == "given"


# --- Visual ------------------------------------------------------------------------


def test_visual_agent_uses_platform_native_aspect_ratio():
    state = _state(platforms=["instagram", "x"])
    state.calendar = [
        ContentItem(platform="instagram", topic="Launch"),
        ContentItem(platform="x", topic="Launch"),
    ]
    state = VisualAgent().run(state)

    assert state.calendar[0].visual["aspect_ratio"] == PLATFORM_VISUAL_SPEC["instagram"][0]
    assert state.calendar[1].visual["aspect_ratio"] == PLATFORM_VISUAL_SPEC["x"][0]


def test_youtube_surfaces_have_opposite_orientations():
    # Long-form renders a landscape thumbnail; Shorts is a vertical frame.
    assert PLATFORM_VISUAL_SPEC["youtube"][0] == "16:9"
    assert PLATFORM_VISUAL_SPEC["youtube_shorts"][0] == "9:16"


def test_visual_agent_always_produces_prompt_and_alt_text():
    state = _state()
    state.calendar = [ContentItem(platform="x", topic="Launch day", media_brief="a rocket")]
    state = VisualAgent().run(state)

    visual = state.calendar[0].visual
    assert visual["prompt"]
    assert visual["alt_text"]
    assert visual["status"] == "spec"  # no image provider wired up yet


def test_visual_agent_respects_existing_spec():
    state = _state()
    state.calendar = [ContentItem(platform="x", topic="t", visual={"prompt": "mine"})]
    state = VisualAgent().run(state)
    assert state.calendar[0].visual == {"prompt": "mine"}


# --- Video -------------------------------------------------------------------------


def test_video_agent_skips_items_that_are_not_video_kinds():
    """Kind gates the video agent — see test_post_kinds_and_audio.py for the full matrix."""
    state = _state(platforms=["linkedin"])
    state.calendar = [ContentItem(platform="linkedin", topic="Launch", kind=PostKind.IMAGE)]
    state = VideoAgent().run(state)
    assert state.calendar[0].video == {}


def test_video_agent_scripts_video_kinds():
    state = _state(platforms=["tiktok"])
    state.calendar = [
        ContentItem(
            platform="tiktok", topic="Launch", body="We shipped it.", kind=PostKind.VIDEO
        )
    ]
    state = VideoAgent().run(state)

    video = state.calendar[0].video
    assert video["hook"]
    assert len(video["scenes"]) >= 3
    assert video["thumbnail_prompt"]
    assert video["target_seconds"] == VIDEO_PLATFORMS["tiktok"]


def test_video_scene_durations_sum_to_target():
    state = _state(platforms=["tiktok"])
    state.calendar = [ContentItem(platform="tiktok", topic="Launch", kind=PostKind.VIDEO)]
    state = VideoAgent().run(state)

    video = state.calendar[0].video
    assert sum(s["seconds"] for s in video["scenes"]) == video["target_seconds"]


# --- SEO ---------------------------------------------------------------------------


def test_seo_agent_extracts_keywords_and_slug():
    state = _state()
    state.calendar = [
        ContentItem(platform="x", topic="Automated social media scheduling", body="Ship faster.")
    ]
    state = SEOAgent().run(state)

    seo = state.calendar[0].seo
    assert "automated" in seo["keywords"]
    assert seo["primary_keyword"]
    assert seo["slug"] == "automated"
    assert seo["meta_description"]


def test_seo_agent_caps_hashtags_per_platform():
    state = _state(platforms=["x"])
    state.calendar = [
        ContentItem(
            platform="x",
            topic="Automated social media scheduling tools",
            hashtags=["a", "b", "c", "d", "e", "f", "g"],
        )
    ]
    state = SEOAgent().run(state)
    assert len(state.calendar[0].hashtags) <= PLATFORM_HASHTAG_LIMIT["x"]


def test_seo_agent_never_rewrites_the_body():
    """Moderation must review the copy content-creation produced, not an SEO rewrite."""
    state = _state()
    original = "We shipped scheduling."
    state.calendar = [ContentItem(platform="x", topic="Scheduling", body=original)]
    state = SEOAgent().run(state)
    assert state.calendar[0].body == original


def test_seo_meta_description_is_truncated():
    state = _state()
    state.calendar = [ContentItem(platform="x", topic="Long", body="x" * 500)]
    state = SEOAgent().run(state)
    assert len(state.calendar[0].seo["meta_description"]) <= 155


# --- Pipeline wiring ---------------------------------------------------------------


def test_pipeline_runs_all_workflow_stages_in_order():
    names = [a.name for a in PIPELINE]
    assert names == [
        "input-parser",
        "trend-research",
        "content-strategy",
        "content-creation",
        "visual",
        "video",
        "audio",
        "seo",
        "moderation",
        "scheduling",
        "publishing",
        "engagement",
        "analytics",
    ]


def test_generation_agents_all_run_before_the_moderation_gate():
    """Everything visual/video/audio/SEO generate must be reviewed before publishing."""
    names = [a.name for a in PRE_APPROVAL_PIPELINE]
    assert names[-1] == "moderation"
    for generated in ("visual", "video", "audio", "seo"):
        assert names.index(generated) < names.index("moderation")


def test_full_pipeline_produces_visual_video_audio_and_seo():
    from src.orchestrator.graph import run_campaign

    state = CampaignState(
        brand_name="Acme AI",
        platforms=["tiktok"],  # video-first platform, so defaults to the video kind
        raw_input="Announce our new AI scheduling assistant",
    )
    state = run_campaign(state)

    item = state.calendar[0]
    assert item.status == ContentStatus.PUBLISHED
    assert item.kind is PostKind.VIDEO
    assert item.visual["prompt"]
    assert item.video["scenes"]
    assert item.audio["script"]
    assert item.seo["primary_keyword"]


def test_state_roundtrips_new_agent_fields():
    """New fields must survive the DB serialization used by campaigns_repo."""
    state = CampaignState(brand_name="Acme", raw_input="hi", brief={"intent": "announce"})
    state.calendar = [
        ContentItem(
            platform="tiktok",
            topic="t",
            visual={"prompt": "p"},
            video={"hook": "h"},
            seo={"primary_keyword": "k"},
        )
    ]
    restored = CampaignState.from_dict(state.to_dict())

    assert restored.raw_input == "hi"
    assert restored.brief == {"intent": "announce"}
    assert restored.calendar[0].visual == {"prompt": "p"}
    assert restored.calendar[0].video == {"hook": "h"}
    assert restored.calendar[0].seo == {"primary_keyword": "k"}
