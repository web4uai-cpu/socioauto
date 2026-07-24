"""Read-only billing views for the admin dashboard.

Stripe webhook synchronization is deliberately outside this module. These endpoints expose
only normalized subscription and invoice records and remain empty until a billing provider
creates those records.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import enforce_rate_limit, get_current_user
from src.db.models import User
from src.db.repositories.billing import invoices_for_user, subscriptions_for_user
from src.db.session import get_db

router = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(enforce_rate_limit)]
)


class SubscriptionResponse(BaseModel):
    id: str
    tier: Literal["free", "starter", "pro", "agency", "enterprise"]
    status: Literal["active", "past_due", "canceled", "trialing"]
    current_period_end: datetime | None


class InvoiceResponse(BaseModel):
    id: str
    amount_due: float
    currency: str
    status: Literal["draft", "open", "paid", "void", "uncollectible"]
    issued_at: datetime


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
def list_subscriptions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SubscriptionResponse]:
    """Return subscriptions belonging to the authenticated user."""
    return [
        SubscriptionResponse(**subscription)
        for subscription in subscriptions_for_user(db, current_user.id)
    ]


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[InvoiceResponse]:
    """Return invoices belonging to the authenticated user."""
    return [InvoiceResponse(**invoice) for invoice in invoices_for_user(db, current_user.id)]
