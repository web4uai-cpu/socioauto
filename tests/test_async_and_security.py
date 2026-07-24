"""Async campaign enqueue (Celery eager) + production secret fail-fast checks."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.security.startup import InsecureConfigurationError, verify_production_secrets

client = TestClient(app)


def _token() -> str:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "async-user@brand.com", "password": "password123"},
    )
    if resp.status_code == 201:
        return resp.json()["access_token"]
    login = client.post(
        "/api/v1/auth/token",
        data={"username": "async-user@brand.com", "password": "password123"},
    )
    return login.json()["access_token"]


def test_enqueue_campaign_runs_eagerly_and_persists():
    headers = {"Authorization": f"Bearer {_token()}"}
    resp = client.post(
        "/api/v1/campaigns/async",
        json={"prompt": "Promote the summer sale", "platforms": ["x"]},
        headers=headers,
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["task_id"]
    campaign_id = body["campaign_id"]

    # Eager execution means the pipeline already ran and persisted the result.
    fetched = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["status"] in ("pending_review", "needs_revision")
    assert len(fetched.json()["calendar"]) >= 1


def test_production_secrets_check_noop_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    verify_production_secrets()  # must not raise


def test_production_secrets_check_fails_fast_on_dev_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    # SECRET_KEY is the dev default in tests, so this must refuse to boot.
    with pytest.raises(InsecureConfigurationError):
        verify_production_secrets()
