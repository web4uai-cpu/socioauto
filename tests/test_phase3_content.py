"""Phase 3: per-platform copy shaping, X threads, and SEO/readability scoring."""

import pytest

from src.agents.content_creation import (
    MAX_THREAD_PARTS,
    PLATFORM_SPECS,
    ContentCreationAgent,
    spec_for,
    split_into_thread,
)
from src.agents.seo import PLATFORM_HASHTAG_LIMIT, SEOAgent
from src.orchestrator.state import CampaignState, ContentItem
from src.seo.readability import flesch_reading_ease, readability_label, seo_score


def _state(*items: ContentItem, **kwargs) -> CampaignState:
    kwargs.setdefault("platforms", ["x"])
    state = CampaignState(brand_name="Acme", **kwargs)
    state.calendar = list(items)
    return state


# --- Platform specs -------------------------------------------------------------------


@pytest.mark.parametrize(
    "platform,word_range",
    [
        ("instagram", (125, 150)),
        ("linkedin", (150, 300)),
    ],
)
def test_platform_word_targets_match_the_spec(platform, word_range):
    assert PLATFORM_SPECS[platform].word_range == word_range


def test_only_x_supports_threads():
    threading = {name for name, spec in PLATFORM_SPECS.items() if spec.supports_thread}
    assert threading == {"x"}


def test_unknown_platform_gets_a_safe_default():
    spec = spec_for("myspace")
    assert spec.char_limit == 280
    assert spec.supports_thread is False


# --- Thread splitting -----------------------------------------------------------------


def test_short_body_is_not_threaded():
    assert split_into_thread("Just a short post.", 280) == ["Just a short post."]


def test_thread_parts_are_numbered_and_within_limit():
    body = " ".join(["This is a sentence that takes up room."] * 20)
    parts = split_into_thread(body, 280)

    assert len(parts) > 1
    assert all(len(p) <= 280 for p in parts)
    assert parts[0].endswith(f"1/{len(parts)}")
    assert parts[-1].endswith(f"{len(parts)}/{len(parts)}")


def test_thread_splits_on_sentence_boundaries_where_possible():
    body = "First sentence here. " * 30
    parts = split_into_thread(body, 280)
    # No part should start mid-sentence with a lowercase fragment.
    assert all(p[0].isupper() for p in parts)


def test_a_single_overlong_sentence_is_hard_wrapped():
    """No sentence boundary to use — it must still fit rather than overflow."""
    parts = split_into_thread("word " * 200, 280)
    assert all(len(p) <= 280 for p in parts)


def test_thread_is_capped():
    parts = split_into_thread("Sentence here. " * 500, 280)
    assert len(parts) <= MAX_THREAD_PARTS


def test_threading_is_recorded_on_the_item():
    item = ContentItem(platform="x", topic="t", body="Long sentence to split. " * 30)
    ContentCreationAgent().run(_state(item))
    assert item.thread == []  # body already set, so the agent skips it


# --- Readability ----------------------------------------------------------------------


def test_simple_copy_reads_more_easily_than_dense_copy():
    simple = flesch_reading_ease("We ship fast. You save time. It just works.")
    dense = flesch_reading_ease(
        "Our organisation facilitates unprecedented operational optimisation through "
        "comprehensive infrastructural reconfiguration methodologies."
    )
    assert simple > dense


def test_empty_text_scores_zero():
    assert flesch_reading_ease("") == 0.0


def test_readability_is_bounded():
    for text in ["Go.", "word " * 500, "Supercalifragilistic expialidocious."]:
        assert 0.0 <= flesch_reading_ease(text) <= 100.0


def test_readability_label_bands():
    assert readability_label(95) == "very easy"
    assert readability_label(65) == "plain english"
    assert readability_label(10) == "very difficult"


# --- SEO scoring ----------------------------------------------------------------------


def test_perfect_post_scores_100():
    result = seo_score(
        body="We ship fast. You save time.",
        primary_keyword="ship",
        hashtags=["a", "b", "c"],
        hashtag_target=3,
        has_cta=True,
        readability=80.0,
        word_range=None,
    )
    assert result["score"] == 100
    assert result["suggestions"] == []


def test_missing_keyword_is_reported():
    result = seo_score(
        body="Nothing relevant here.",
        primary_keyword="triage",
        hashtags=["a", "b", "c"],
        hashtag_target=3,
        has_cta=True,
        readability=80.0,
    )
    assert result["score"] < 100
    assert any("triage" in s for s in result["suggestions"])
    assert "keyword" not in result["passed"]


def test_every_failure_produces_a_suggestion():
    result = seo_score(
        body="",
        primary_keyword="missing",
        hashtags=[],
        hashtag_target=10,
        has_cta=False,
        readability=5.0,
        word_range=(100, 200),
    )
    assert result["score"] == 0
    assert len(result["suggestions"]) == 5


# --- Agent integration ----------------------------------------------------------------


def test_seo_agent_attaches_scores():
    item = ContentItem(platform="x", topic="Faster triage", body="We ship faster triage. Try it.")
    SEOAgent().run(_state(item))

    seo = item.seo
    assert isinstance(seo["score"], int)
    assert 0 <= seo["score"] <= 100
    assert seo["readability_label"]
    assert isinstance(seo["suggestions"], list)


def test_score_accounts_for_thread_continuation():
    """The keyword may only appear in a later thread part — that still counts."""
    item = ContentItem(
        platform="x",
        topic="Update",
        body="Here is the news.",
        thread=["It makes triage faster. 2/2"],
    )
    item.seo = {}
    SEOAgent().run(_state(item))
    assert "triage" in " ".join([item.body, *item.thread]).lower()
    assert item.seo["score"] > 0


def test_instagram_allows_a_dense_hashtag_set():
    assert PLATFORM_HASHTAG_LIMIT["instagram"] >= 15
    assert PLATFORM_HASHTAG_LIMIT["x"] <= 3  # stuffing X costs reach


def test_youtube_tags_are_denser_than_shorts():
    # YouTube description tags feed search; Shorts is a feed surface and needs far fewer.
    assert PLATFORM_HASHTAG_LIMIT["youtube"] > PLATFORM_HASHTAG_LIMIT["youtube_shorts"]


def test_lead_capture_suggestion_is_present():
    item = ContentItem(platform="x", topic="Demo", body="Book a demo.", goal="conversion")
    SEOAgent().run(_state(item))
    assert item.seo["lead_magnet"]
    assert item.seo["lead_form_fields"]


def test_thread_survives_serialization():
    state = _state(ContentItem(platform="x", topic="t", body="a", thread=["b 2/2"]))
    restored = CampaignState.from_dict(state.to_dict())
    assert restored.calendar[0].thread == ["b 2/2"]
