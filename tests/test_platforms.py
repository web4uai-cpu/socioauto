"""Platform client, circuit breaker, and webhook signature tests (network mocked)."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
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
