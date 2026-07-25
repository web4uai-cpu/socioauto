"""Authentication: self-service registration + JWT access/refresh token login.

Passwords are verified against the ``users`` table (PBKDF2, see src/security/passwords.py).
Tokens carry the user's email as ``sub`` so admin gating (ADMIN_EMAILS) and principal
resolution stay email-based.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.schemas import RefreshRequest, TokenResponse
from src.db.repositories import users as users_repo
from src.db.session import get_db
from src.security.auth import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str | None = None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = users_repo.register(
            db, email=req.email, password=req.password, full_name=req.full_name
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc
    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
    )


@router.post("/token", response_model=TokenResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = users_repo.authenticate(db, email=form_data.username, password=form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest) -> TokenResponse:
    try:
        payload = decode_token(req.refresh_token, expected_type=TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc
    return TokenResponse(
        access_token=create_access_token(payload.sub),
        refresh_token=create_refresh_token(payload.sub),
    )
