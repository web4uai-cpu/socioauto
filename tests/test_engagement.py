"""Inbound engagement ingestion: payload normalization, dedupe, drafting, escalation."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from src.agents.engagement import EngagementAgent, needs_escalation
from src.api.main import app
from src.db.repositories import engagements as engagements_repo
from src.db.session import SessionLocal
from src.llm.provider import NullProvider
from src.platforms.inbound import parse_meta, parse_x
from src.runtime_config import invalidate_cache

client = TestClient(app)

META_SECRET = "meta-secret"


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", META_SECRET)
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _post_meta(payload: dict):
    body = json.dumps(payload).encode()
    sig = hmac.new(META_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/meta", content=body, headers={"X-Hub-Signature-256": f"sha256={sig}"}
    )


# --- payload normalization ----------------------------------------------------------


def test_parse_meta_extracts_comments_and_dms():
    events = parse_meta(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "field": "comments",
                            "value": {
                                "id": "c1",
                                "comment_id": "c1",
                                "text": "Love this!",
                                "from": {"id": "user-9"},
                            },
                        }
                    ],
                    "messaging": [
                        {
                            "sender": {"id": "user-7"},
                            "message": {"mid": "m1", "text": "Do you ship to Spain?"},
                        }
                    ],
                }
            ]
        }
    )
    assert {e.kind for e in events} == {"comment", "dm"}
    assert {e.external_id for e in events} == {"meta:c1", "meta:m1"}


def test_parse_meta_skips_entries_without_text():
    events = parse_meta({"entry": [{"changes": [{"value": {"id": "c1"}}]}]})
    assert events == []


def test_parse_meta_tolerates_garbage():
    # A malformed batch must not raise — the platform would redeliver it forever.
    assert parse_meta({"entry": ["not-a-dict", None]}) == []
    assert parse_meta({}) == []


def test_parse_x_extracts_mentions_and_dms():
    events = parse_x(
        {
            "tweet_create_events": [
                {"id_str": "t1", "text": "@brand nice work", "user": {"screen_name": "fan"}}
            ],
            "direct_message_events": [
                {
                    "id": "d1",
                    "message_create": {
                        "sender_id": "99",
                        "message_data": {"text": "question about pricing"},
                    },
                }
            ],
        }
    )
    assert {e.external_id for e in events} == {"x:t1", "x:d1"}
    assert {e.kind for e in events} == {"mention", "dm"}


# --- escalation + drafting ----------------------------------------------------------


@pytest.mark.parametrize(
    "message", ["I want a refund now", "my LAWYER will call", "this is a scam"]
)
def test_escalation_keywords_detected(message):
    assert needs_escalation(message) is True


def test_ordinary_message_is_not_escalated():
    assert needs_escalation("love the new product") is False


def test_escalated_message_gets_no_draft(monkeypatch):
    # Even with a working LLM, legal/refund complaints must go to a human undrafted.
    class LoudProvider:
        name = "loud"

        def complete(self, prompt, *, system="", max_tokens=4096):
            return "Sure, here is your refund!"

        def complete_json(self, prompt, schema, *, system="", max_tokens=4096):
            return None

    monkeypatch.setattr("src.agents.engagement.get_provider", lambda: LoudProvider())
    draft, escalated = EngagementAgent().draft_reply("I demand a refund")
    assert escalated is True
    assert draft is None


def test_draft_reply_uses_llm(monkeypatch):
    class StubProvider:
        name = "stub"

        def complete(self, prompt, *, system="", max_tokens=4096):
            return "Thanks for reaching out — we ship to Spain!"

        def complete_json(self, prompt, schema, *, system="", max_tokens=4096):
            return None

    monkeypatch.setattr("src.agents.engagement.get_provider", lambda: StubProvider())
    draft, escalated = EngagementAgent().draft_reply("Do you ship to Spain?")
    assert escalated is False
    assert draft == "Thanks for reaching out — we ship to Spain!"


def test_draft_reply_without_llm_returns_none(monkeypatch):
    monkeypatch.setattr("src.agents.engagement.get_provider", lambda: NullProvider())
    draft, escalated = EngagementAgent().draft_reply("Do you ship to Spain?")
    assert draft is None
    assert escalated is False


# --- end-to-end ingestion -----------------------------------------------------------


def test_webhook_records_and_queues_engagement(db):
    external = uuid.uuid4().hex[:10]
    response = _post_meta(
        {
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "user-1"},
                            "message": {"mid": external, "text": "Do you ship to Spain?"},
                        }
                    ]
                }
            ]
        }
    )
    assert response.status_code == 200
    assert response.json()["queued"] == 1

    from src.db.models import Engagement

    stored = (
        db.query(Engagement).filter(Engagement.external_id == f"meta:{external}").one()
    )
    assert stored.message == "Do you ship to Spain?"
    # Celery runs eagerly in tests, so the agent has already processed it.
    assert stored.status in ("drafted", "escalated")
    assert stored.processed_at is not None


def test_redelivered_webhook_is_not_queued_twice(db):
    external = uuid.uuid4().hex[:10]
    payload = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user-2"},
                        "message": {"mid": external, "text": "hello there"},
                    }
                ]
            }
        ]
    }
    assert _post_meta(payload).json()["queued"] == 1
    # Platforms redeliver; the second delivery must be a no-op.
    assert _post_meta(payload).json()["queued"] == 0

    from src.db.models import Engagement

    assert db.query(Engagement).filter(Engagement.external_id == f"meta:{external}").count() == 1


def test_escalating_message_is_flagged_for_a_human(db):
    external = uuid.uuid4().hex[:10]
    _post_meta(
        {
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "user-3"},
                            "message": {"mid": external, "text": "I want a refund"},
                        }
                    ]
                }
            ]
        }
    )
    from src.db.models import Engagement

    stored = db.query(Engagement).filter(Engagement.external_id == f"meta:{external}").one()
    assert stored.escalated is True
    assert stored.status == "escalated"
    assert stored.draft_response is None


def test_malformed_json_is_acknowledged_not_retried():
    body = b"not json at all"
    sig = hmac.new(META_SECRET.encode(), body, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhooks/meta", content=body, headers={"X-Hub-Signature-256": f"sha256={sig}"}
    )
    assert response.status_code == 200
    assert response.json()["queued"] == 0


def test_pending_queue_helper(db):
    engagement = engagements_repo.record_inbound(
        db,
        platform="x",
        external_id=f"x:{uuid.uuid4().hex[:10]}",
        kind="mention",
        author="someone",
        message="hi",
    )
    assert engagement is not None
    assert any(e.id == engagement.id for e in engagements_repo.pending(db))
