"""Basic user management & roles (admin). Backed by the in-memory store today — swap for
real `users` table queries (src/db/models.py) once src/db/session.py is wired into routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.deps import enforce_rate_limit, get_current_user, require_admin
from src.db.models import User
from src.db.repositories import audit
from src.db.repositories import users as users_repo
from src.db.session import get_db
from src.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["admin"],
    dependencies=[Depends(enforce_rate_limit), Depends(require_admin)],
)

ALLOWED_ROLES = {"owner", "admin", "editor", "viewer"}


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None
    role: str = Field(default="viewer")


class UserRoleUpdateRequest(BaseModel):
    role: str


@router.get("", response_model=list[UserResponse])
def list_users(
    requester: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[UserResponse]:
    """List all users. Backs the UserManagementTable admin dashboard component."""
    return [UserResponse(**u) for u in users_repo.list_all(db)]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: UserCreateRequest,
    requester: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    if req.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"role must be one of {sorted(ALLOWED_ROLES)}",
        )
    try:
        record = users_repo.create(db, email=req.email, full_name=req.full_name, role=req.role)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A user with that email already exists"
        ) from exc
    audit.record(
        db,
        actor=requester.email,
        action="user.created",
        entity_type="user",
        entity_id=record["id"],
        details={"role": req.role},
    )
    logger.info("user created", extra={"user_id": record["id"], "role": req.role})
    return UserResponse(**record)


@router.patch("/{target_user_id}/role", response_model=UserResponse)
def update_user_role(
    target_user_id: str,
    req: UserRoleUpdateRequest,
    requester: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update a user's role. Gated to administrators via the router-level `require_admin`."""
    if req.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"role must be one of {sorted(ALLOWED_ROLES)}",
        )
    record = users_repo.update_role(db, target_user_id, req.role)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    audit.record(
        db,
        actor=requester.email,
        action="user.role_updated",
        entity_type="user",
        entity_id=target_user_id,
        details={"new_role": req.role},
    )
    logger.info("user role updated", extra={"user_id": target_user_id, "new_role": req.role})
    return UserResponse(**record)
