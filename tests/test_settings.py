"""Admin-configurable settings: storage, masking, precedence over env, access control."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.db.repositories.settings import set_setting
from src.db.session import SessionLocal
from src.runtime_config import get_setting, invalidate_cache, is_editable

client = TestClient(app)

_PASSWORD = "password123"
ADMIN_EMAIL = "demo@brand.com"  # conftest sets ADMIN_EMAILS to this


def _token(email: str) -> str:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": _PASSWORD})
    if resp.status_code == 201:
        return resp.json()["access_token"]
    login = client.post("/api/v1/auth/token", data={"username": email, "password": _PASSWORD})
    assert login.status_code == 200
    return login.json()["access_token"]


def _headers(email: str = ADMIN_EMAIL) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(email)}"}


@pytest.fixture(autouse=True)
def _clean_settings():
    """Remove any settings a test wrote, so tests stay independent."""
    invalidate_cache()
    yield
    with SessionLocal() as db:
        for key in ("LLM_API_KEY", "LLM_PROVIDER", "LLM_MODEL", "STRIPE_SECRET_KEY"):
            set_setting(db, key, "", is_secret=True, actor="test-cleanup")
    invalidate_cache()


def _find(views: list[dict], key: str) -> dict:
    return next(v for v in views if v["key"] == key)


def test_non_admin_cannot_read_settings():
    response = client.get("/api/v1/admin/settings", headers=_headers("outsider@brand.com"))
    assert response.status_code == 403


def test_settings_require_authentication():
    assert client.get("/api/v1/admin/settings").status_code == 401


def test_catalog_lists_editable_keys():
    response = client.get("/api/v1/admin/settings", headers=_headers())
    assert response.status_code == 200
    keys = {v["key"] for v in response.json()}
    assert {"LLM_API_KEY", "STRIPE_SECRET_KEY", "X_CLIENT_SECRET"} <= keys


def test_infrastructure_secrets_are_not_editable():
    # Rotating these from a web form would break decryption / connectivity.
    for key in ("APP_ENCRYPTION_KEY", "JWT_SECRET_KEY", "DATABASE_URL", "REDIS_URL"):
        assert not is_editable(key)


def test_update_stores_value_and_masks_secret():
    response = client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"LLM_API_KEY": "sk-ant-supersecret-1234"}},
    )
    assert response.status_code == 200

    view = _find(response.json(), "LLM_API_KEY")
    assert view["configured"] is True
    assert view["source"] == "database"
    # The raw secret must never come back out of the API.
    assert "supersecret" not in view["value"]
    assert view["value"].endswith("1234")


def test_non_secret_value_is_returned_in_full():
    client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"LLM_MODEL": "claude-opus-5"}},
    )
    response = client.get("/api/v1/admin/settings", headers=_headers())
    assert _find(response.json(), "LLM_MODEL")["value"] == "claude-opus-5"


def test_stored_setting_overrides_environment(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_from_env")
    invalidate_cache()
    assert get_setting("STRIPE_SECRET_KEY") == "sk_from_env"

    client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"STRIPE_SECRET_KEY": "sk_from_dashboard"}},
    )
    assert get_setting("STRIPE_SECRET_KEY") == "sk_from_dashboard"


def test_clearing_a_value_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_from_env")
    client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"STRIPE_SECRET_KEY": "sk_from_dashboard"}},
    )
    assert get_setting("STRIPE_SECRET_KEY") == "sk_from_dashboard"

    client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"STRIPE_SECRET_KEY": ""}},
    )
    invalidate_cache()
    assert get_setting("STRIPE_SECRET_KEY") == "sk_from_env"


def test_unknown_key_is_rejected():
    response = client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"APP_ENCRYPTION_KEY": "attacker-supplied"}},
    )
    assert response.status_code == 400
    assert "APP_ENCRYPTION_KEY" in response.json()["detail"]


def test_value_outside_allowed_choices_is_rejected():
    response = client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"LLM_PROVIDER": "openai"}},
    )
    assert response.status_code == 400


def test_secret_is_encrypted_at_rest():
    client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"LLM_API_KEY": "sk-ant-plaintext-check"}},
    )
    from src.db.models import AppSetting

    with SessionLocal() as db:
        row = db.get(AppSetting, "LLM_API_KEY")
        assert row is not None
        assert "plaintext-check" not in row.value_encrypted


def test_status_endpoint_reports_readiness():
    client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"LLM_API_KEY": "sk-ant-configured"}},
    )
    response = client.get("/api/v1/admin/settings/status", headers=_headers())
    assert response.status_code == 200
    assert response.json()["ai"] is True
