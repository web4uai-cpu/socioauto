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
        for key in (
            "LLM_API_KEY",
            "LLM_PROVIDER",
            "LLM_MODEL",
            "STRIPE_SECRET_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "AI_ANALYSIS_PROVIDER",
            "AI_ANALYSIS_MODEL",
            "AI_RESEARCH_PROVIDER",
            "AI_RESEARCH_MODEL",
        ):
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
        json={"values": {"AI_ANALYSIS_PROVIDER": "not-a-vendor"}},
    )
    assert response.status_code == 400


def test_model_field_accepts_a_model_id_outside_the_curated_list():
    # A model released after this build must be usable without waiting for a deploy.
    response = client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={"values": {"AI_ANALYSIS_MODEL": "some-model-shipped-tomorrow"}},
    )
    assert response.status_code == 200
    view = _find(response.json(), "AI_ANALYSIS_MODEL")
    assert view["allow_custom"] is True
    assert view["value"] == "some-model-shipped-tomorrow"


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


def test_status_reports_each_ai_slot_separately():
    """One configured slot must not imply the others are usable."""
    client.put(
        "/api/v1/admin/settings",
        headers=_headers(),
        json={
            "values": {
                "ANTHROPIC_API_KEY": "sk-ant-configured",
                "AI_RESEARCH_PROVIDER": "anthropic",
                # Analysis points at a vendor with no key, so it must read as not ready.
                "AI_ANALYSIS_PROVIDER": "openai",
            }
        },
    )
    body = client.get("/api/v1/admin/settings/status", headers=_headers()).json()
    assert body["ai_research"] is True
    assert body["ai_analysis"] is False


def test_ai_catalog_describes_slots_and_key_readiness():
    response = client.get("/api/v1/admin/settings/ai-catalog", headers=_headers())
    assert response.status_code == 200
    roles = {role["role"]: role for role in response.json()["roles"]}
    assert {"analysis", "research", "writing", "voice", "video", "image"} <= set(roles)

    analysis = roles["analysis"]
    assert analysis["provider_setting"] == "AI_ANALYSIS_PROVIDER"
    providers = {p["id"]: p for p in analysis["providers"]}
    assert "anthropic" in providers
    assert providers["anthropic"]["key_setting"] == "ANTHROPIC_API_KEY"
    assert providers["anthropic"]["key_configured"] is False
    assert any(m["recommended"] for m in providers["anthropic"]["models"])

    # Voice and video are configurable but not yet generating — the UI must be able to say so.
    assert roles["voice"]["connected"] is False
    assert roles["video"]["connected"] is False


def test_ai_catalog_requires_admin():
    assert client.get("/api/v1/admin/settings/ai-catalog").status_code == 401
    forbidden = client.get(
        "/api/v1/admin/settings/ai-catalog", headers=_headers("outsider@brand.com")
    )
    assert forbidden.status_code == 403
