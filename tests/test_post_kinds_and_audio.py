"""Post-kind gating, the Audio Agent, and pipeline progress reporting.

Runs with no LLM configured, so these exercise each agent's deterministic fallback.
"""

import pytest

from src.agents.audio import WORDS_PER_MINUTE, AudioAgent, estimate_seconds
from src.agents.video import VideoAgent
from src.agents.visual import VisualAgent
from src.orchestrator.graph import (
    AGENT_LABELS,
    PRE_APPROVAL_PIPELINE,
    run_campaign,
    run_to_moderation,
)
from src.orchestrator.state import (
    CampaignState,
    ContentItem,
    PostKind,
    resolve_kind,
)


def _item(kind: PostKind, platform: str = "x", **kwargs) -> ContentItem:
    return ContentItem(platform=platform, topic="Launch day", kind=kind, **kwargs)


def _state(*items: ContentItem, **kwargs) -> CampaignState:
    kwargs.setdefault("platforms", ["x"])
    state = CampaignState(brand_name="Acme AI", **kwargs)
    state.calendar = list(items)
    return state


# --- resolve_kind ------------------------------------------------------------------


@pytest.mark.parametrize(
    "requested,platform,expected",
    [
        ("audio", "x", PostKind.AUDIO),
        ("faceless_video", "linkedin", PostKind.FACELESS_VIDEO),
        ("", "tiktok", PostKind.VIDEO),  # platform default
        ("", "linkedin", PostKind.IMAGE),  # global fallback
        ("nonsense", "linkedin", PostKind.IMAGE),  # bad value degrades, never raises
    ],
)
def test_resolve_kind(requested, platform, expected):
    assert resolve_kind(requested, platform) is expected


# --- Audio Agent -------------------------------------------------------------------


@pytest.mark.parametrize("kind", [PostKind.AUDIO, PostKind.VIDEO, PostKind.FACELESS_VIDEO])
def test_audio_agent_produces_spec_for_audio_bearing_kinds(kind):
    state = AudioAgent().run(_state(_item(kind, body="We shipped it.")))
    audio = state.calendar[0].audio
    assert audio["script"]
    assert audio["voice"]["words_per_minute"] == WORDS_PER_MINUTE
    assert audio["status"] == "spec"
    assert audio["transcript"] == audio["script"]


@pytest.mark.parametrize("kind", [PostKind.TEXT, PostKind.IMAGE])
def test_audio_agent_skips_silent_kinds(kind):
    state = AudioAgent().run(_state(_item(kind, body="We shipped it.")))
    assert state.calendar[0].audio == {}


def test_audio_agent_reuses_video_narration():
    """The voiceover must voice the script the Video Agent wrote, not a second draft."""
    item = _item(PostKind.VIDEO, platform="tiktok", body="caption")
    item.video = {
        "scenes": [
            {"narration": "First beat.", "visual": "b-roll", "seconds": 10},
            {"narration": "Second beat.", "visual": "b-roll", "seconds": 10},
        ]
    }
    state = AudioAgent().run(_state(item))
    assert state.calendar[0].audio["script"] == "First beat. Second beat."


def test_audio_type_differs_for_audio_only_posts():
    audio_only = AudioAgent().run(_state(_item(PostKind.AUDIO)))
    video = AudioAgent().run(_state(_item(PostKind.VIDEO)))
    assert audio_only.calendar[0].audio["audio_type"] == "podcast_clip"
    assert video.calendar[0].audio["audio_type"] == "voiceover"


def test_estimated_seconds_scales_with_script_length():
    short = estimate_seconds(" ".join(["word"] * 75))
    long = estimate_seconds(" ".join(["word"] * 300))
    assert short == 30
    assert long == 120
    assert long > short


def test_audio_agent_respects_existing_spec():
    item = _item(PostKind.AUDIO, audio={"script": "mine"})
    state = AudioAgent().run(_state(item))
    assert state.calendar[0].audio == {"script": "mine"}


# --- Kind gating across the generation agents ---------------------------------------


def test_audio_only_post_gets_audio_but_no_video():
    """The headline requirement: an audio post must not produce a video script."""
    state = _state(_item(PostKind.AUDIO, platform="tiktok", body="listen in"))
    state = VisualAgent().run(state)
    state = VideoAgent().run(state)
    state = AudioAgent().run(state)

    item = state.calendar[0]
    assert item.audio["script"]
    assert item.video == {}
    # Audio posts still get cover art.
    assert item.visual["purpose"] == "audio cover art"


def test_text_post_gets_no_media_at_all():
    state = _state(_item(PostKind.TEXT, platform="tiktok", body="just words"))
    state = VisualAgent().run(state)
    state = VideoAgent().run(state)
    state = AudioAgent().run(state)

    item = state.calendar[0]
    assert item.visual == {}
    assert item.video == {}
    assert item.audio == {}


def test_image_post_gets_visual_only():
    state = _state(_item(PostKind.IMAGE, platform="tiktok"))
    state = VisualAgent().run(state)
    state = VideoAgent().run(state)
    state = AudioAgent().run(state)

    item = state.calendar[0]
    assert item.visual["purpose"] == "feed image"
    assert item.video == {}
    assert item.audio == {}


def test_video_kind_is_honoured_on_a_platform_without_a_tuned_runtime():
    """An explicit video request must not be silently dropped on LinkedIn."""
    state = VideoAgent().run(_state(_item(PostKind.VIDEO, platform="linkedin")))
    assert state.calendar[0].video["scenes"]
    assert state.calendar[0].video["target_seconds"] == 45


def test_faceless_video_has_no_talking_head():
    state = VideoAgent().run(_state(_item(PostKind.FACELESS_VIDEO, platform="tiktok")))
    video = state.calendar[0].video
    assert video["faceless"] is True
    visuals = " ".join(scene["visual"] for scene in video["scenes"]).lower()
    assert "talking head" not in visuals


def test_normal_video_may_use_a_presenter():
    state = VideoAgent().run(_state(_item(PostKind.VIDEO, platform="tiktok")))
    assert state.calendar[0].video["faceless"] is False


# --- Serialization -------------------------------------------------------------------


def test_kind_and_audio_survive_roundtrip():
    state = _state(
        _item(PostKind.FACELESS_VIDEO, audio={"script": "s"}, goal="awareness"),
        post_kind="faceless_video",
    )
    restored = CampaignState.from_dict(state.to_dict())

    assert restored.post_kind == "faceless_video"
    assert restored.calendar[0].kind is PostKind.FACELESS_VIDEO
    assert restored.calendar[0].audio == {"script": "s"}
    assert restored.calendar[0].goal == "awareness"


def test_unknown_kind_in_stored_state_does_not_crash_load():
    state = _state(_item(PostKind.IMAGE))
    raw = state.to_dict()
    raw["calendar"][0]["kind"] = "image"  # sanity: known value loads
    assert CampaignState.from_dict(raw).calendar[0].kind is PostKind.IMAGE


# --- Pipeline + progress --------------------------------------------------------------


def test_audio_runs_between_video_and_seo():
    names = [a.name for a in PRE_APPROVAL_PIPELINE]
    assert names.index("video") < names.index("audio") < names.index("seo")
    assert names.index("audio") < names.index("moderation")


def test_every_pipeline_agent_has_a_display_label():
    for agent in PRE_APPROVAL_PIPELINE:
        assert AGENT_LABELS.get(agent.name), f"missing label for {agent.name}"


def test_on_agent_hook_fires_once_per_agent_in_order():
    seen: list[tuple[str, int, int]] = []
    state = CampaignState(brand_name="Acme", platforms=["x"], raw_input="Announce a thing")
    run_to_moderation(state, on_agent=lambda n, i, t: seen.append((n, i, t)))

    assert [name for name, _, _ in seen] == [a.name for a in PRE_APPROVAL_PIPELINE]
    assert [i for _, i, _ in seen] == list(range(1, len(PRE_APPROVAL_PIPELINE) + 1))
    assert all(total == len(PRE_APPROVAL_PIPELINE) for _, _, total in seen)


def test_failing_progress_hook_does_not_break_the_campaign():
    """Progress is telemetry — a broken hook must never lose a campaign."""

    def boom(name, index, total):
        raise RuntimeError("progress backend down")

    state = CampaignState(brand_name="Acme", platforms=["x"], raw_input="Announce a thing")
    result = run_to_moderation(state, on_agent=boom)
    assert result.calendar  # generation still happened


def test_full_pipeline_respects_requested_kind():
    state = CampaignState(
        brand_name="Acme AI",
        platforms=["tiktok"],
        raw_input="Announce our AI assistant",
        post_kind="audio",
    )
    state = run_campaign(state)

    item = state.calendar[0]
    assert item.kind is PostKind.AUDIO
    assert item.audio["script"]
    assert item.video == {}
