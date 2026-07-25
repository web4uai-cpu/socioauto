"""Phase 6: per-post metrics, performance rollups, and recommendation generation."""

from datetime import UTC, datetime

import pytest

from src.agents.analytics import AnalyticsAgent
from src.analytics.insights import (
    MIN_POSTS_PER_GROUP,
    build_recommendations,
    click_through_rate,
    engagement_rate,
    summarize,
)
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus


def _post(platform="x", kind="image", hour=9, **metrics) -> dict:
    return {"platform": platform, "kind": kind, "hour": hour, "metrics": metrics}


def _published(platform="x", metrics=None) -> ContentItem:
    item = ContentItem(platform=platform, topic="t", body="b", status=ContentStatus.PUBLISHED)
    item.external_post_id = f"{platform}-real-1"
    item.published_at = datetime(2026, 7, 26, 9, 0, tzinfo=UTC)
    item.metrics = metrics or {}
    return item


# --- Rate maths -------------------------------------------------------------------------


def test_engagement_rate_is_engagements_over_impressions():
    assert engagement_rate({"impressions": 1000, "likes": 20, "shares": 5, "comments": 5}) == 0.03


def test_engagement_rate_is_none_without_impressions():
    assert engagement_rate({"likes": 10}) is None
    assert engagement_rate({"impressions": 0, "likes": 10}) is None


def test_ctr_is_none_when_clicks_are_not_reported():
    """Most platforms omit clicks; absent must not become zero."""
    assert click_through_rate({"impressions": 1000}) is None
    assert click_through_rate({"impressions": 1000, "clicks": 50}) == 0.05


# --- Summary ----------------------------------------------------------------------------


def test_summary_totals_across_posts():
    summary = summarize(
        [
            _post(impressions=1000, likes=10, shares=5, comments=5),
            _post(impressions=1000, likes=30, shares=0, comments=0),
        ]
    )
    assert summary["posts_measured"] == 2
    assert summary["impressions"] == 2000
    assert summary["likes"] == 40
    assert summary["engagement_rate"] == 0.025


def test_summary_reports_no_clicks_as_none_not_zero():
    summary = summarize([_post(impressions=100, likes=1)])
    assert summary["clicks"] is None
    assert summary["click_through_rate"] is None


def test_summary_reports_clicks_when_present():
    summary = summarize([_post(impressions=1000, likes=1, clicks=100)])
    assert summary["clicks"] == 100
    assert summary["click_through_rate"] == 0.1


def test_unmeasured_posts_are_excluded():
    summary = summarize([_post(impressions=100, likes=5), {"platform": "x", "metrics": {}}])
    assert summary["posts_measured"] == 1


# --- Recommendations ---------------------------------------------------------------------


def test_no_data_yields_an_explicit_note_not_advice():
    recs = build_recommendations([])
    assert len(recs) == 1
    assert recs[0]["type"] == "no_data"


def test_single_post_does_not_produce_comparative_advice():
    """Advice from n=1 is noise dressed up as analysis."""
    recs = build_recommendations([_post(impressions=1000, likes=100)])
    assert all(not r["type"].startswith("best_") for r in recs)
    assert any(r["type"] in ("insufficient_sample", "no_click_data") for r in recs)


def test_platform_comparison_needs_enough_posts_per_group():
    # One post each — below MIN_POSTS_PER_GROUP, so no comparison.
    posts = [
        _post(platform="x", impressions=1000, likes=100),
        _post(platform="linkedin", impressions=1000, likes=1),
    ]
    assert all(r["type"] != "best_platform" for r in build_recommendations(posts))


def test_platform_comparison_fires_with_enough_data():
    posts = [
        *[_post(platform="x", impressions=1000, likes=100) for _ in range(MIN_POSTS_PER_GROUP)],
        *[
            _post(platform="linkedin", impressions=1000, likes=1)
            for _ in range(MIN_POSTS_PER_GROUP)
        ],
    ]
    recs = build_recommendations(posts)
    best = next(r for r in recs if r["type"] == "best_platform")
    assert best["evidence"]["best"] == "x"
    assert best["evidence"]["worst"] == "linkedin"
    assert "x" in best["message"]


def test_negligible_difference_is_not_reported_as_an_insight():
    posts = [
        *[_post(platform="x", impressions=1000, likes=50) for _ in range(MIN_POSTS_PER_GROUP)],
        *[
            _post(platform="linkedin", impressions=1000, likes=51)
            for _ in range(MIN_POSTS_PER_GROUP)
        ],
    ]
    assert all(r["type"] != "best_platform" for r in build_recommendations(posts))


def test_missing_click_data_is_called_out():
    posts = [_post(impressions=1000, likes=10) for _ in range(4)]
    assert any(r["type"] == "no_click_data" for r in build_recommendations(posts))


# --- Agent -------------------------------------------------------------------------------


def test_agent_records_a_snapshot_and_recommendations():
    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.calendar = [_published()]
    state = AnalyticsAgent().run(state)

    assert len(state.analytics) == 1
    assert state.analytics[0]["published_count"] == 1
    assert state.recommendations


def test_agent_does_not_invent_metrics_in_simulate_mode():
    """No connected account means no measurement — not a row of zeros."""
    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.calendar = [_published()]
    state = AnalyticsAgent().run(state)

    assert state.calendar[0].metrics == {}
    assert state.analytics[0]["posts_measured"] == 0
    assert state.recommendations[0]["type"] == "no_data"


def test_agent_fetches_metrics_for_connected_accounts(monkeypatch):
    class _Client:
        def fetch_metrics(self, external_id, *, access_token=None):
            return {"impressions": 500, "likes": 25, "shares": 5, "comments": 0, "clicks": 10}

    monkeypatch.setattr("src.agents.analytics.get_client", lambda platform: _Client())

    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.access_tokens = {"x": "token"}
    state.calendar = [_published()]
    state = AnalyticsAgent().run(state)

    assert state.calendar[0].metrics["impressions"] == 500
    assert state.analytics[0]["posts_measured"] == 1
    assert state.analytics[0]["engagement_rate"] == 0.06


def test_all_zero_metrics_are_not_recorded_as_data(monkeypatch):
    """Zeros are indistinguishable from 'not measured yet' and would drag averages down."""

    class _Client:
        def fetch_metrics(self, external_id, *, access_token=None):
            return {"impressions": 0, "likes": 0, "shares": 0, "comments": 0}

    monkeypatch.setattr("src.agents.analytics.get_client", lambda platform: _Client())

    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.access_tokens = {"x": "token"}
    state.calendar = [_published()]
    state = AnalyticsAgent().run(state)

    assert state.calendar[0].metrics == {}


def test_metrics_failure_does_not_break_the_pipeline(monkeypatch):
    from src.platforms.http_client import PlatformHttpError

    class _Client:
        def fetch_metrics(self, external_id, *, access_token=None):
            raise PlatformHttpError("rate limited")

    monkeypatch.setattr("src.agents.analytics.get_client", lambda platform: _Client())

    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.access_tokens = {"x": "token"}
    state.calendar = [_published()]
    state = AnalyticsAgent().run(state)  # must not raise

    assert state.calendar[0].status == ContentStatus.PUBLISHED
    assert state.analytics


def test_metrics_and_recommendations_survive_serialization():
    state = CampaignState(brand_name="Acme")
    state.recommendations = [{"type": "best_platform", "message": "m", "evidence": {}}]
    state.calendar = [_published(metrics={"impressions": 10})]
    restored = CampaignState.from_dict(state.to_dict())

    assert restored.recommendations[0]["type"] == "best_platform"
    assert restored.calendar[0].metrics == {"impressions": 10}


@pytest.mark.parametrize("status", [ContentStatus.APPROVED, ContentStatus.REJECTED])
def test_unpublished_items_are_never_measured(status):
    state = CampaignState(brand_name="Acme", platforms=["x"])
    item = _published()
    item.status = status
    state.calendar = [item]
    state = AnalyticsAgent().run(state)

    assert state.analytics[0]["published_count"] == 0
