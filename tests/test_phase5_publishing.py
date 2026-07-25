"""Phase 5: audience-local scheduling windows and captured post URLs."""

from datetime import UTC, datetime

import pytest

from src.agents.publishing import PublishingAgent
from src.agents.scheduling import SchedulingAgent
from src.orchestrator.state import (
    DEFAULT_TIMEZONE,
    CampaignState,
    ContentItem,
    ContentStatus,
)
from src.platforms.clients import build_post_url
from src.scheduling.optimal_times import (
    next_optimal_slot,
    optimal_hours,
    resolve_timezone,
)

IST = resolve_timezone("Asia/Kolkata")
NY = resolve_timezone("America/New_York")


def _local(slot: datetime, tz) -> datetime:
    return slot.astimezone(tz)


# --- Optimal windows match the spec ------------------------------------------------------


@pytest.mark.parametrize(
    "platform,expected",
    [
        ("instagram", [11, 12, 19, 20]),  # 11 AM-1 PM, 7 PM-9 PM
        ("linkedin", [8, 9, 12, 13]),  # 8-10 AM, 12-2 PM
        ("x", [9, 12, 15, 18]),  # 9 AM, 12 PM, 3 PM, 6 PM
    ],
)
def test_windows_match_the_workflow_spec(platform, expected):
    assert optimal_hours(platform) == expected


# --- Timezone handling --------------------------------------------------------------------


def test_default_timezone_is_india():
    assert DEFAULT_TIMEZONE == "Asia/Kolkata"


def test_slot_lands_in_the_local_window_not_utc():
    """The whole point: 9 AM must mean 9 AM where the audience is."""
    start = datetime(2026, 7, 24, 0, 0, tzinfo=UTC)
    slot = next_optimal_slot("x", start, "Asia/Kolkata")
    assert _local(slot, IST).hour in optimal_hours("x")


def test_same_window_gives_different_utc_times_per_timezone():
    start = datetime(2026, 7, 24, 0, 0, tzinfo=UTC)
    ist = next_optimal_slot("x", start, "Asia/Kolkata")
    ny = next_optimal_slot("x", start, "America/New_York")

    assert _local(ist, IST).hour in optimal_hours("x")
    assert _local(ny, NY).hour in optimal_hours("x")
    # Same local window, genuinely different absolute moments.
    assert ist != ny


def test_ist_half_hour_offset_is_preserved():
    """IST is UTC+5:30, so an on-the-hour local slot is on the half hour in UTC."""
    start = datetime(2026, 7, 24, 0, 0, tzinfo=UTC)
    slot = next_optimal_slot("x", start, "Asia/Kolkata")
    assert slot.minute == 30
    assert _local(slot, IST).minute == 0


def test_unknown_timezone_degrades_instead_of_raising():
    start = datetime(2026, 7, 24, 0, 0, tzinfo=UTC)
    slot = next_optimal_slot("x", start, "Mars/Olympus_Mons")
    assert slot > start


def test_naive_input_is_treated_as_utc():
    naive = datetime(2026, 7, 24, 0, 0)
    slot = next_optimal_slot("x", naive, "Asia/Kolkata")
    assert slot.tzinfo is not None


def test_linkedin_skips_weekends_in_the_audience_week():
    saturday = datetime(2026, 7, 25, 0, 0, tzinfo=UTC)
    slot = next_optimal_slot("linkedin", saturday, "Asia/Kolkata")
    assert _local(slot, IST).weekday() < 5


def test_scheduling_agent_uses_the_campaign_timezone():
    state = CampaignState(brand_name="Acme", platforms=["x"], timezone="Asia/Kolkata")
    state.calendar = [
        ContentItem(platform="x", topic="t", body="b", status=ContentStatus.APPROVED)
    ]
    state = SchedulingAgent().run(state)

    item = state.calendar[0]
    assert item.status == ContentStatus.SCHEDULED
    assert _local(item.scheduled_at, IST).hour in optimal_hours("x")


def test_timezone_survives_serialization():
    state = CampaignState(brand_name="Acme", timezone="America/New_York")
    assert CampaignState.from_dict(state.to_dict()).timezone == "America/New_York"


# --- Post URLs ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "platform,post_id,expected",
    [
        ("x", "1234567890", "https://x.com/i/web/status/1234567890"),
        ("facebook", "abc123", "https://www.facebook.com/abc123"),
        ("tiktok", "999", "https://www.tiktok.com/video/999"),
    ],
)
def test_permalinks_are_built_for_supported_platforms(platform, post_id, expected):
    assert build_post_url(platform, post_id) == expected


def test_no_url_for_simulated_posts():
    """A simulated post does not exist — a link to it would be a dead link."""
    assert build_post_url("x", "x-sim-abc123") is None


def test_no_url_for_instagram():
    """The Graph API media id is not the permalink shortcode; guessing would 404."""
    assert build_post_url("instagram", "17900000000000000") is None


def test_no_url_without_an_id():
    assert build_post_url("x", None) is None
    assert build_post_url("x", "") is None


def test_publishing_captures_the_post_url():
    state = CampaignState(brand_name="Acme", platforms=["x"])
    state.calendar = [
        ContentItem(platform="x", topic="t", body="b", status=ContentStatus.SCHEDULED)
    ]
    state = PublishingAgent().run(state)

    item = state.calendar[0]
    assert item.status == ContentStatus.PUBLISHED
    assert item.external_post_id
    # No token configured, so this ran in simulate mode: id yes, URL no.
    assert item.external_post_url is None


def test_post_url_survives_serialization():
    state = CampaignState(brand_name="Acme")
    state.calendar = [
        ContentItem(platform="x", topic="t", external_post_url="https://x.com/i/web/status/1")
    ]
    restored = CampaignState.from_dict(state.to_dict())
    assert restored.calendar[0].external_post_url == "https://x.com/i/web/status/1"
