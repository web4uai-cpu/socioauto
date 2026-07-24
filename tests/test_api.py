import base64

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


_PASSWORD = "password123"


def _auth(email: str = "demo@brand.com") -> str:
    """Register the user (idempotent) and return an access token."""
    resp = client.post(
        "/api/v1/auth/register", json={"email": email, "password": _PASSWORD}
    )
    if resp.status_code == 201:
        return resp.json()["access_token"]
    login = client.post(
        "/api/v1/auth/token", data={"username": email, "password": _PASSWORD}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _get_token() -> str:
    return _auth("demo@brand.com")


def test_login_issues_access_and_refresh_tokens():
    _auth("login-test@brand.com")
    resp = client.post(
        "/api/v1/auth/token", data={"username": "login-test@brand.com", "password": _PASSWORD}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_rejects_wrong_password():
    _auth("wrongpw@brand.com")
    resp = client.post(
        "/api/v1/auth/token", data={"username": "wrongpw@brand.com", "password": "not-it"}
    )
    assert resp.status_code == 401



def test_readiness_checks_database_connectivity():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_campaign_create_get_and_approve_flow():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/v1/campaigns",
        json={"prompt": "Announce our new AI feature", "platforms": ["x", "linkedin"]},
        headers=headers,
    )
    assert create_resp.status_code == 201
    campaign = create_resp.json()
    campaign_id = campaign["id"]
    assert len(campaign["calendar"]) == 2

    get_resp = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers)
    assert get_resp.status_code == 200

    approve_resp = client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=headers)
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert all(item["status"] == "published" for item in approved["calendar"])


def test_campaign_endpoints_require_auth():
    resp = client.get("/api/v1/campaigns/does-not-exist")
    assert resp.status_code == 401


def test_analytics_dashboard():
    token = _get_token()
    resp = client.get("/api/v1/analytics/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "total_campaigns" in resp.json()


def test_connect_account_never_returns_raw_api_key():
    token = _get_token()
    resp = client.post(
        "/api/v1/accounts/connect",
        json={"platform": "x", "external_account_id": "abc123", "api_key": "super-secret-token"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "api_key" not in body
    assert "credentials_ref" not in body


def test_rate_limit_encryption_roundtrip():
    from src.security.crypto import decrypt, encrypt

    ciphertext = encrypt("my-secret-key")
    assert ciphertext != "my-secret-key"
    assert decrypt(ciphertext) == "my-secret-key"
    assert base64.b64decode(ciphertext)  # valid base64


def test_admin_user_create_list_and_role_update():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/v1/admin/users",
        json={"email": "new.member@brand.com", "full_name": "New Member", "role": "editor"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    user = create_resp.json()
    assert user["role"] == "editor"

    list_resp = client.get("/api/v1/admin/users", headers=headers)
    assert list_resp.status_code == 200
    assert any(u["id"] == user["id"] for u in list_resp.json())

    update_resp = client.patch(
        f"/api/v1/admin/users/{user['id']}/role", json={"role": "admin"}, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["role"] == "admin"


def test_admin_user_create_rejects_invalid_role():
    token = _get_token()
    resp = client.post(
        "/api/v1/admin/users",
        json={"email": "bad.role@brand.com", "role": "superuser"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_user_management_requires_an_administrator():
    token = _auth("non-admin@brand.com")
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_dashboard_list_endpoints_are_authenticated_and_return_lists():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    for path in (
        "/api/v1/campaigns",
        "/api/v1/accounts",
        "/api/v1/admin/subscriptions",
        "/api/v1/admin/invoices",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_campaigns_are_isolated_by_authenticated_user():
    first_token = _get_token()
    second_token = _auth("other@brand.com")

    create_response = client.post(
        "/api/v1/campaigns",
        json={"prompt": "First user's private campaign", "platforms": ["linkedin"]},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert create_response.status_code == 201
    campaign_id = create_response.json()["id"]

    list_response = client.get(
        "/api/v1/campaigns", headers={"Authorization": f"Bearer {second_token}"}
    )
    assert all(campaign["id"] != campaign_id for campaign in list_response.json())

    details_response = client.get(
        f"/api/v1/campaigns/{campaign_id}", headers={"Authorization": f"Bearer {second_token}"}
    )
    assert details_response.status_code == 404
