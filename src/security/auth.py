"""JWT authentication: access + refresh tokens.

SECRET_KEY must come from the environment in production — the default below is only for
local/dev convenience and must never be used in a deployed environment.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from enum import Enum

import jwt
from pydantic import BaseModel

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str
    type: TokenType
    exp: datetime


class InvalidTokenError(Exception):
    pass


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {"sub": subject, "type": token_type.value, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject: str) -> str:
    return _create_token(subject, TokenType.ACCESS, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, TokenType.REFRESH, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str, expected_type: TokenType = TokenType.ACCESS) -> TokenPayload:
    try:
        raw = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if raw.get("type") != expected_type.value:
        raise InvalidTokenError(f"expected a {expected_type.value} token")
    return TokenPayload(sub=raw["sub"], type=raw["type"], exp=raw["exp"])
