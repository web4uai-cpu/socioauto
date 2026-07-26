"""Platform client, circuit breaker, and webhook signature tests (network mocked)."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.main import app
from src.api.schemas import AccountConnectRequest
from src.orchestrator.state import PostKind, resolve_kind
from src.platforms import clients, http_client
from src.platforms.circuit_breaker import CircuitBreaker, CircuitOpenError
from src.platforms.http_client import PlatformHttpError
from src.runtime_config import invalidate_cache

client = TestClient(app)


def test_publish_simulate_mode_returns_synthetic_id():
    external_id = http_client.publish_post("x", "hello world")
    assert external_id.startswith("x-sim-")


def test_publish_empty_body_rejected():
    with pytest.raises(PlatformHttpError):
        http_client.publish_post("x", "   ")


def test_publish_real_path_uses_request_json(monkeypatch):
    captured = {}

    def _fake_request_json(method, url, *, headers=None, params=None, data=None, json=None):
        captured["method"] = method
        captured["url"] = url
        captured["auth"] = headers.get("Authorization")
        captured["payload"] = json
        return {"data": {"id": "999"}}

    monkeypatch.setattr(clients, "request_json", _fake_request_json)
    external_id = clients.get_client("x").publish("launch day", access_token="tok")
    assert external_id == "999"
    assert captured["url"] == "https://api.twitter.com/2/tweets"
    assert captured["auth"] == "Bearer tok"
    assert captured["payload"] == {"text": "launch day"}


# --- YouTube / YouTube Shorts ------------------------------------------------------------


def test_youtube_publish_builds_snippet_payload(monkeypatch):
    captured = {}

    def _fake_request_json(method, url, *, headers=None, params=None, data=None, json=None):
        captured["url"] = url
        captured["payload"] = json
        return {"id": "vid123"}

    monkeypatch.setattr(clients, "request_json", _fake_request_json)
    external_id = clients.get_client("youtube").publish("Launch day\n\nDetails.", access_token="t")

    assert external_id == "vid123"
    assert captured["url"] == "https://www.googleapis.com/youtube/v3/videos?part=snippet,status"
    assert captured["payload"]["snippet"]["title"] == "Launch day"
    assert captured["payload"]["snippet"]["description"] == "Launch day\n\nDetails."
    assert captured["payload"]["status"]["privacyStatus"] == "public"


def test_youtube_title_is_truncated_on_a_word_boundary():
    body = " ".join(["word"] * 40)  # 199 chars, far over the 100-char title limit
    title = clients._derive_title(body)
    assert len(title) <= 100
    assert not title.endswith("wor")  # never cut mid-word
    assert title == " ".join(["word"] * 20)


def test_youtube_metrics_are_flattened_from_the_items_envelope(monkeypatch):
    def _fake_request_json(method, url, *, headers=None, params=None, data=None, json=None):
        assert "id=vid123" in url
        return {"items": [{"statistics": {"viewCount": "42", "likeCount": "7"}}]}

    monkeypatch.setattr(clients, "request_json", _fake_request_json)
    metrics = clients.get_client("youtube").fetch_metrics("vid123", access_token="t")
    assert metrics == {"viewCount": "42", "likeCount": "7"}


def test_youtube_permalinks_differ_between_surfaces():
    assert clients.build_post_url("youtube", "abc") == "https://www.youtube.com/watch?v=abc"
    assert clients.build_post_url("youtube_shorts", "abc") == "https://www.youtube.com/shorts/abc"


def test_youtube_simulate_mode_has_no_permalink():
    external_id = http_client.publish_post("youtube_shorts", "hello")
    assert external_id.startswith("youtube_shorts-sim-")
    # A simulated post does not exist, so no URL should be invented for it.
    assert clients.build_post_url("youtube_shorts", external_id) is None


@pytest.mark.parametrize("platform", ["youtube", "youtube_shorts"])
def test_youtube_platforms_default_to_video(platform):
    assert resolve_kind(None, platform) is PostKind.VIDEO


@pytest.mark.parametrize("platform", ["youtube", "youtube_shorts"])
def test_account_connect_schema_accepts_youtube(platform):
    req = AccountConnectRequest(platform=platform, external_account_id="chan-1", api_key="k")
    assert req.platform == platform


def test_account_connect_schema_still_rejects_unknown_platform():
    with pytest.raises(ValidationError):
        AccountConnectRequest(platform="myspace", external_account_id="1", api_key="k")


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=60)

    def _boom():
        raise RuntimeError("fail")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            breaker.call(_boom)
    # Circuit now open — further calls fast-fail without invoking the function.
    with pytest.raises(CircuitOpenError):
        breaker.call(_boom)


def test_meta_webhook_rejects_bad_signature():
    resp = client.post(
        "/webhooks/meta", content=b"{}", headers={"X-Hub-Signature-256": "sha256=bad"}
    )
    assert resp.status_code == 401


def test_meta_webhook_accepts_valid_signature(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "shh")
    invalidate_cache()
    body = json.dumps({"entry": []}).encode()
    sig = hmac.new(b"shh", body, hashlib.sha256).hexdigest()
    resp = client.post(
        "/webhooks/meta", content=body, headers={"X-Hub-Signature-256": f"sha256={sig}"}
    )
    assert resp.status_code == 200
    # No entries in the payload, so nothing is queued for the Engagement Agent.
    assert resp.json() == {"status": "accepted", "queued": 0}


def test_connected_account_token_reaches_real_publish(monkeypatch):
    """End-to-end: a connected account's token flows into the live publish call on approval."""
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "publisher@brand.com", "password": "password123"},
    )
    token = (
        reg.json()["access_token"]
        if reg.status_code == 201
        else client.post(
            "/api/v1/auth/token",
            data={"username": "publisher@brand.com", "password": "password123"},
        ).json()["access_token"]
    )
    headers = {"Authorization": f"Bearer {token}"}

    connect = client.post(
        "/api/v1/accounts/connect",
        json={"platform": "x", "external_account_id": "acct-1", "api_key": "live-token-xyz"},
        headers=headers,
    )
    assert connect.status_code == 201

    captured = {}

    def _fake_request_json(method, url, *, headers=None, params=None, data=None, json=None):
        captured["auth"] = headers.get("Authorization")
        return {"data": {"id": "live-123"}}

    monkeypatch.setattr(clients, "request_json", _fake_request_json)

    created = client.post(
        "/api/v1/campaigns",
        json={"prompt": "Launch announcement", "platforms": ["x"]},
        headers=headers,
    )
    campaign_id = created.json()["id"]
    approved = client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=headers)
    assert approved.status_code == 200

    # The real API path ran with the decrypted account token (not simulate mode).
    assert captured.get("auth") == "Bearer live-token-xyz"
    published = [i for i in approved.json()["calendar"] if i["status"] == "published"]
    assert published and all(i["external_post_id"] == "live-123" for i in published)


def test_meta_verify_handshake(monkeypatch):
    monkeypatch.setenv("META_WEBHOOK_VERIFY_TOKEN", "verify-me")
    resp = client.get(
        "/webhooks/meta",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-me",
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "12345"
