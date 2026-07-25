"""Config-driven OAuth2 authorization-code provider (with optional PKCE)."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

from src.platforms.http_client import request_json
from src.platforms.oauth.config import PLATFORM_OAUTH, OAuthConfig


class UnknownPlatform(Exception):
    """Raised when an OAuth flow is requested for an unconfigured platform."""


class OAuthConfigError(Exception):
    """Raised when a platform's client credentials are not configured in the environment."""


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    scope: str | None
    raw: dict


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for the S256 PKCE method."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class OAuth2Provider:
    def __init__(self, config: OAuthConfig) -> None:
        self.config = config

    def _client_id(self) -> str:
        client_id = os.environ.get(self.config.client_id_env)
        if not client_id:
            raise OAuthConfigError(f"{self.config.client_id_env} is not configured")
        return client_id

    def _client_secret(self) -> str:
        secret = os.environ.get(self.config.client_secret_env)
        if not secret:
            raise OAuthConfigError(f"{self.config.client_secret_env} is not configured")
        return secret

    def authorization_url(
        self, *, state: str, redirect_uri: str, code_challenge: str | None = None
    ) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id(),
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
            **self.config.extra_authorize_params,
        }
        if self.config.use_pkce and code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        return f"{self.config.authorize_url}?{urlencode(params)}"

    def exchange_code(
        self, *, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OAuthTokens:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id(),
            "client_secret": self._client_secret(),
        }
        if self.config.use_pkce and code_verifier:
            data["code_verifier"] = code_verifier
        payload = request_json("POST", self.config.token_url, data=data)
        return _to_tokens(payload)

    def refresh(self, *, refresh_token: str) -> OAuthTokens:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id(),
            "client_secret": self._client_secret(),
        }
        payload = request_json("POST", self.config.token_url, data=data)
        return _to_tokens(payload)


def _to_tokens(payload: dict) -> OAuthTokens:
    return OAuthTokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
        scope=payload.get("scope"),
        raw=payload,
    )


def get_provider(platform: str) -> OAuth2Provider:
    config = PLATFORM_OAUTH.get(platform)
    if config is None:
        raise UnknownPlatform(f"no OAuth configuration for platform '{platform}'")
    return OAuth2Provider(config)
