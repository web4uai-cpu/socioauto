"""Stateless, CSRF-safe OAuth ``state`` handling.

The ``state`` passed to the provider is a short-lived signed JWT binding the flow to the
initiating user, platform, and (for PKCE) the code verifier. On callback we verify the
signature, so no server-side session store is required.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from src.security.auth import ALGORITHM, SECRET_KEY

_STATE_TTL = timedelta(minutes=10)


class InvalidState(Exception):
    """Raised when an OAuth ``state`` value is missing, tampered, or expired."""


def sign_state(*, user_id: str, platform: str, code_verifier: str | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "platform": platform,
        "cv": code_verifier,
        "iat": now,
        "exp": now + _STATE_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_state(state: str) -> dict[str, str | None]:
    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidState(str(exc)) from exc
    return {
        "user_id": payload["sub"],
        "platform": payload["platform"],
        "code_verifier": payload.get("cv"),
    }
