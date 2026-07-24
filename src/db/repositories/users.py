"""User persistence: self-provisioned principals + admin-managed users."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import User
from src.security.passwords import hash_password, verify_password


def _to_dict(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
    }


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_or_create_by_email(db: Session, email: str, *, role: str = "owner") -> User:
    """Return the user for ``email``, creating a self-provisioned record if absent.

    Used by the auth dependency so an authenticated principal always maps to a real
    ``users`` row (enabling brand-scoped ownership/foreign keys).
    """
    user = get_by_email(db, email)
    if user is None:
        user = User(email=email, role=role, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def register(
    db: Session, *, email: str, password: str, full_name: str | None = None, role: str = "owner"
) -> User:
    """Create a user with a hashed password (self-service signup)."""
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str) -> User | None:
    """Return the user iff the email exists, is active, and the password verifies."""
    user = get_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get(db: Session, user_id: str) -> dict[str, Any] | None:
    try:
        pk = uuid.UUID(user_id)
    except ValueError:
        return None
    user = db.get(User, pk)
    return _to_dict(user) if user else None


def create(db: Session, *, email: str, full_name: str | None, role: str) -> dict[str, Any]:
    user = User(email=email, full_name=full_name, role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_dict(user)


def list_all(db: Session) -> list[dict[str, Any]]:
    return [_to_dict(u) for u in db.execute(select(User)).scalars().all()]


def update_role(db: Session, user_id: str, role: str) -> dict[str, Any] | None:
    try:
        pk = uuid.UUID(user_id)
    except ValueError:
        return None
    user = db.get(User, pk)
    if user is None:
        return None
    user.role = role
    db.commit()
    db.refresh(user)
    return _to_dict(user)
