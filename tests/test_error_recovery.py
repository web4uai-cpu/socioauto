"""Error handling and recovery: retry queue, backoff, and human escalation."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.agents.publishing import PublishingAgent
from src.agents.trend_research import TrendResearchAgent
from src.api.main import app
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus
from src.platforms.delivery import MAX_PUBLISH_ATTEMPTS, backoff_for, deliver, is_due
from src.platforms.http_client import PlatformHttpError
from src.scheduling.runner import items_needing_attention, publish_due_items

client = TestClient(app)
NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


def _scheduled(**kwargs) -> ContentItem:
    item = ContentItem(platform="x", topic="t", body="b", status=ContentStatus.SCHEDULED, **kwargs)
    item.scheduled_at = NOW - timedelta(minutes=1)
    return item


def _fail(monkeypatch, message="platform rejected the post"):
    def _boom(platform, body, *, access_token=None):
        raise PlatformHttpError(message)

    monkeypatch.setattr("src.platforms.delivery.publish_post", _boom)


# --- Backoff ------------------------------------------------------------------------------


def test_backoff_grows_with_each_attempt():
    delays = [backoff_for(n) for n in range(1, MAX_PUBLISH_ATTEMPTS + 1)]
    assert delays == sorted(delays)
    assert delays[0] < delays[-1]


def test_backoff_is_capped_beyond_the_last_step():
    assert backoff_for(99) == backoff_for(MAX_PUBLISH_ATTEMPTS)


def test_backoff_handles_a_zero_attempt():
    assert backoff_for(0) == backoff_for(1)


# --- Retry queue --------------------------------------------------------------------------


def test_failed_publish_is_requeued_not_killed(monkeypatch):
    """A transient failure must not permanently destroy the post."""
    _fail(monkeypatch)
    item = _scheduled()

    assert deliver(item, None, NOW) is False
    assert item.status == ContentStatus.SCHEDULED  # still queued
    assert item.retry_count == 1
    assert item.next_retry_at == NOW + backoff_for(1)
    assert item.last_error
    assert item.needs_human is False


def test_item_is_not_retried_before_its_backoff_elapses(monkeypatch):
    _fail(monkeypatch)
    item = _scheduled()
    deliver(item, None, NOW)

    assert is_due(item, NOW) is False
    assert is_due(item, item.next_retry_at) is True


def test_runner_skips_items_still_in_backoff(monkeypatch):
    _fail(monkeypatch)
    state = CampaignState(brand_name="Acme", calendar=[_scheduled()])
    publish_due_items(state, {}, NOW)
    attempts_after_first = state.calendar[0].retry_count

    # Immediately re-running must not burn another attempt.
    publish_due_items(state, {}, NOW)
    assert state.calendar[0].retry_count == attempts_after_first


def test_runner_retries_once_the_backoff_has_passed(monkeypatch):
    _fail(monkeypatch)
    state = CampaignState(brand_name="Acme", calendar=[_scheduled()])
    publish_due_items(state, {}, NOW)

    later = state.calendar[0].next_retry_at
    publish_due_items(state, {}, later)
    assert state.calendar[0].retry_count == 2


def test_eventual_success_clears_retry_state(monkeypatch):
    _fail(monkeypatch)
    item = _scheduled()
    deliver(item, None, NOW)
    assert item.retry_count == 1

    monkeypatch.setattr(
        "src.platforms.delivery.publish_post", lambda p, b, *, access_token=None: "x-123"
    )
    assert deliver(item, None, NOW) is True
    assert item.status == ContentStatus.PUBLISHED
    assert item.next_retry_at is None
    assert item.last_error is None
    assert item.needs_human is False


# --- Escalation ---------------------------------------------------------------------------


def test_exhausted_retries_escalate_to_a_human(monkeypatch):
    """Silent permanent failure is exactly what this policy exists to prevent."""
    _fail(monkeypatch)
    item = _scheduled()

    for _ in range(MAX_PUBLISH_ATTEMPTS):
        deliver(item, None, NOW)

    assert item.retry_count == MAX_PUBLISH_ATTEMPTS
    assert item.status == ContentStatus.FAILED
    assert item.needs_human is True
    assert item.next_retry_at is None  # no further automated attempts


def test_escalated_items_are_listed_for_the_operator(monkeypatch):
    _fail(monkeypatch, "quota exceeded")
    item = _scheduled()
    for _ in range(MAX_PUBLISH_ATTEMPTS):
        deliver(item, None, NOW)

    listed = items_needing_attention(CampaignState(brand_name="Acme", calendar=[item]))
    assert len(listed) == 1
    assert listed[0]["attempts"] == MAX_PUBLISH_ATTEMPTS
    assert "quota exceeded" in listed[0]["last_error"]


def test_healthy_campaigns_are_not_listed():
    state = CampaignState(brand_name="Acme", calendar=[_scheduled()])
    assert items_needing_attention(state) == []


def test_publishing_agent_respects_backoff(monkeypatch):
    _fail(monkeypatch)
    state = CampaignState(brand_name="Acme", calendar=[_scheduled()])
    PublishingAgent().run(state)
    first = state.calendar[0].retry_count

    PublishingAgent().run(state)  # still inside the backoff window
    assert state.calendar[0].retry_count == first


# --- Agent/runner parity ------------------------------------------------------------------


def test_runner_and_agent_both_capture_the_post_url(monkeypatch):
    """They used to duplicate this logic and drifted — the runner dropped the URL."""
    monkeypatch.setattr(
        "src.platforms.delivery.publish_post", lambda p, b, *, access_token=None: "1234567890"
    )

    via_agent = CampaignState(brand_name="Acme", calendar=[_scheduled()])
    PublishingAgent().run(via_agent)

    via_runner = CampaignState(brand_name="Acme", calendar=[_scheduled()])
    publish_due_items(via_runner, {}, NOW)

    assert via_agent.calendar[0].external_post_url
    assert via_agent.calendar[0].external_post_url == via_runner.calendar[0].external_post_url


def test_unapproved_content_is_never_delivered_by_either_path(monkeypatch):
    monkeypatch.setattr(
        "src.platforms.delivery.publish_post", lambda p, b, *, access_token=None: "x-1"
    )
    for status in (ContentStatus.APPROVED, ContentStatus.REJECTED, ContentStatus.DRAFT):
        item = _scheduled()
        item.status = status
        state = CampaignState(brand_name="Acme", calendar=[item])

        PublishingAgent().run(state)
        publish_due_items(state, {}, NOW)
        assert state.calendar[0].external_post_id is None


# --- Research retry -----------------------------------------------------------------------


class _Stub:
    """Fails the first call, then succeeds — mimics a too-narrow query."""

    name = "stub"

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.prompts: list[str] = []

    def complete_json(self, prompt, schema, *, system="", max_tokens=4096):
        self.prompts.append(prompt)
        return self.payloads.pop(0) if self.payloads else None

    def complete(self, prompt, *, system="", max_tokens=4096):
        return None


def test_research_retries_with_broader_terms(monkeypatch):
    stub = _Stub([None, {"trends": [], "keywords": [], "hashtags": [], "pain_points": []}])
    monkeypatch.setattr("src.agents.trend_research.get_provider", lambda *_: stub)

    TrendResearchAgent().run(CampaignState(brand_name="Acme", platforms=["x"]))

    assert len(stub.prompts) == 2, "expected one retry"
    assert "broader category" in stub.prompts[1]
    assert "broader category" not in stub.prompts[0]


def test_research_does_not_retry_when_the_first_call_works(monkeypatch):
    stub = _Stub([{"trends": [], "keywords": [], "hashtags": [], "pain_points": []}])
    monkeypatch.setattr("src.agents.trend_research.get_provider", lambda *_: stub)

    TrendResearchAgent().run(CampaignState(brand_name="Acme", platforms=["x"]))
    assert len(stub.prompts) == 1


# --- Serialization + endpoint --------------------------------------------------------------


def test_retry_state_survives_serialization(monkeypatch):
    _fail(monkeypatch)
    item = _scheduled()
    deliver(item, None, NOW)

    restored = CampaignState.from_dict(
        CampaignState(brand_name="Acme", calendar=[item]).to_dict()
    ).calendar[0]
    assert restored.retry_count == 1
    assert restored.next_retry_at == item.next_retry_at
    assert restored.last_error == item.last_error


def test_needs_attention_endpoint_requires_auth():
    assert client.get("/api/v1/campaigns/needs-attention").status_code == 401


def test_needs_attention_endpoint_is_empty_for_a_healthy_account():
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "attention@brand.com", "password": "password123"},
    )
    token = (
        resp.json()["access_token"]
        if resp.status_code == 201
        else client.post(
            "/api/v1/auth/token",
            data={"username": "attention@brand.com", "password": "password123"},
        ).json()["access_token"]
    )
    body = client.get(
        "/api/v1/campaigns/needs-attention", headers={"Authorization": f"Bearer {token}"}
    )
    assert body.status_code == 200
    assert body.json() == []


@pytest.mark.parametrize("attempts", [1, 3])
def test_partial_failures_stay_recoverable(monkeypatch, attempts):
    _fail(monkeypatch)
    item = _scheduled()
    for _ in range(attempts):
        deliver(item, None, NOW)

    assert item.needs_human is False
    assert item.status == ContentStatus.SCHEDULED
