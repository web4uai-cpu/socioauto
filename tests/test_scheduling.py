"""Auto-scheduling engine: optimal slotting, /schedule endpoint, and due-post runner."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from src.agents import scheduling as scheduling_agent
from src.api.main import app
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus
from src.scheduling.optimal_times import (
    DEFAULT_TIMEZONE,
    next_optimal_slot,
    optimal_hours,
    resolve_timezone,
)
from src.scheduling.runner import publish_due_items

client = TestClient(app)


def _auth(email: str) -> str:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    if resp.status_code == 201:
        return resp.json()["access_token"]
    login = client.post("/api/v1/auth/token", data={"username": email, "password": "password123"})
    return login.json()["access_token"]


def test_next_optimal_slot_is_future_and_in_preferred_hours():
    """Preferred hours are audience-local, so the returned UTC slot must be converted back."""
    now = datetime(2026, 7, 24, 3, 0, tzinfo=UTC)  # a Friday, off-peak
    slot = next_optimal_slot("x", now)
    assert slot > now
    assert slot.tzinfo is not None
    local = slot.astimezone(resolve_timezone(DEFAULT_TIMEZONE))
    assert local.hour in optimal_hours("x")


def test_linkedin_slots_skip_weekends():
    saturday = datetime(2026, 7, 25, 6, 0, tzinfo=UTC)  # Saturday
    slot = next_optimal_slot("linkedin", saturday)
    local = slot.astimezone(resolve_timezone(DEFAULT_TIMEZONE))
    assert local.weekday() < 5  # Mon–Fri only in the audience's own week


def test_publish_due_items_only_publishes_due():
    now = datetime.now(UTC)
    due = ContentItem(platform="x", topic="t", body="due", status=ContentStatus.SCHEDULED)
    due.scheduled_at = now - timedelta(minutes=5)
    future = ContentItem(platform="x", topic="t", body="later", status=ContentStatus.SCHEDULED)
    future.scheduled_at = now + timedelta(hours=5)
    state = CampaignState(brand_name="b", calendar=[due, future])

    published = publish_due_items(state, {}, now)
    assert published == 1
    assert due.status == ContentStatus.PUBLISHED
    assert future.status == ContentStatus.SCHEDULED


def test_schedule_endpoint_queues_without_publishing():
    headers = {"Authorization": f"Bearer {_auth('scheduler@brand.com')}"}
    created = client.post(
        "/api/v1/campaigns",
        json={"prompt": "Weekly tips series", "platforms": ["x", "linkedin"]},
        headers=headers,
    )
    campaign_id = created.json()["id"]

    resp = client.post(f"/api/v1/campaigns/{campaign_id}/schedule", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "scheduled"
    assert body["calendar"]
    for item in body["calendar"]:
        assert item["status"] == "scheduled"
        assert item["scheduled_at"] is not None
        assert item["published_at"] is None


def test_due_post_runner_publishes_scheduled_campaign(monkeypatch):
    # Force scheduling to place slots in the past so they are immediately due.
    past = datetime.now(UTC) - timedelta(minutes=1)
    monkeypatch.setattr(
        scheduling_agent, "next_optimal_slot", lambda platform, after, timezone=None: past
    )

    headers = {"Authorization": f"Bearer {_auth('due-runner@brand.com')}"}
    created = client.post(
        "/api/v1/campaigns",
        json={"prompt": "Flash sale", "platforms": ["x"]},
        headers=headers,
    )
    campaign_id = created.json()["id"]
    client.post(f"/api/v1/campaigns/{campaign_id}/schedule", headers=headers)

    from src.orchestrator.tasks import publish_due_posts

    result = publish_due_posts.apply().get()
    assert result["published"] >= 1

    fetched = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers)
    assert fetched.json()["status"] == "published"
    assert all(i["status"] == "published" for i in fetched.json()["calendar"])
