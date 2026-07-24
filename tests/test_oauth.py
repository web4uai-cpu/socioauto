"""OAuth2 account-connection flow: authorize URL + callback token exchange (mocked network)."""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from src.api.main import app
from src.platforms.oauth import provider as oauth_provider
from src.platforms.oauth.provider import OAuthTokens

client = TestClient(app)


def _token() -> str:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "oauth-user@brand.com", "password": "password123"},
    )
    if resp.status_code == 201:
        return resp.json()["access_token"]
    login = client.post(
        "/api/v1/auth/token",
        data={"username": "oauth-user@brand.com", "password": "password123"},
    )
    return login.json()["access_token"]


def test_authorize_returns_signed_url(monkeypatch):
    monkeypatch.setenv("X_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("X_CLIENT_SECRET", "test-secret")
    headers = {"Authorization": f"Bearer {_token()}"}

    resp = client.get("/api/v1/accounts/x/authorize", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorization_url"].startswith("https://twitter.com/i/oauth2/authorize?")
    assert "code_challenge=" in body["authorization_url"]  # PKCE enforced for X
    assert "client_id=test-client-id" in body["authorization_url"]
    assert body["state"]


def test_authorize_unknown_platform_is_404():
    headers = {"Authorization": f"Bearer {_token()}"}
    resp = client.get("/api/v1/accounts/myspace/authorize", headers=headers)
    assert resp.status_code == 404


def test_callback_exchanges_code_and_persists_encrypted_account(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "li-id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "li-secret")
    headers = {"Authorization": f"Bearer {_token()}"}

    start = client.get("/api/v1/accounts/linkedin/authorize", headers=headers)
    state = start.json()["state"]

    def _fake_exchange(self, *, code, redirect_uri, code_verifier=None):
        assert code == "the-auth-code"
        return OAuthTokens(
            access_token="secret-access",
            refresh_token="secret-refresh",
            expires_in=3600,
            scope="w_member_social",
            raw={},
        )

    monkeypatch.setattr(oauth_provider.OAuth2Provider, "exchange_code", _fake_exchange)

    resp = client.get(
        "/api/v1/accounts/linkedin/callback",
        params={"code": "the-auth-code", "state": state},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["platform"] == "linkedin"
    assert body["connected"] is True
    # No token material must ever be returned to the client.
    assert "secret-access" not in resp.text
    assert "credentials_ref" not in body

    # The connected account is now listed for the user.
    listed = client.get("/api/v1/accounts", headers=headers)
    assert any(a["platform"] == "linkedin" for a in listed.json())


def test_callback_rejects_tampered_state():
    resp = client.get(
        "/api/v1/accounts/linkedin/callback",
        params={"code": "x", "state": "not-a-valid-jwt"},
    )
    assert resp.status_code == 400


def teardown_module(module):  # noqa: D401 - cleanup env leakage between modules
    for var in ("X_CLIENT_ID", "X_CLIENT_SECRET", "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"):
        os.environ.pop(var, None)
