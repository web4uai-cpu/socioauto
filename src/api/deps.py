"""Shared FastAPI dependencies: JWT auth + per-user rate limiting."""
from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.db.models import User
from src.db.repositories import users as users_repo
from src.db.session import get_db
from src.security.auth import InvalidTokenError, TokenType, decode_token
from src.security.rate_limit import RateLimitExceeded, rate_limiter

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = decode_token(token, expected_type=TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return payload.sub


def get_current_user(
    user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)
) -> User:
    """Resolve the authenticated principal to a persisted ``users`` row.

    The account is self-provisioned on first authenticated request so every principal maps to
    a real row, enabling brand-scoped ownership foreign keys on campaigns/accounts.
    """
    return users_repo.get_or_create_by_email(db, user_id)


def require_admin(user_id: str = Depends(get_current_user_id)) -> str:
    """Require an account listed in ADMIN_EMAILS (comma-separated) to access admin users."""
    configured_admins = os.environ.get("ADMIN_EMAILS", "demo@brand.com")
    admin_emails = {
        email.strip().lower() for email in configured_admins.split(",") if email.strip()
    }
    if user_id.lower() not in admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required"
        )
    return user_id


def enforce_rate_limit(request: Request, user_id: str = Depends(get_current_user_id)) -> None:
    tier = request.headers.get("X-Account-Tier", "free")
    try:
        rate_limiter.check(key=user_id, tier=tier)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc
