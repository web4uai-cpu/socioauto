"""Billing views for the admin dashboard, plus Stripe Checkout initiation.

Reads are normalized subscription/invoice records. The only write path is the
signature-verified Stripe webhook (`src/api/routes/webhooks.py`) — this module never
mutates billing state from user input; it only hands the user off to Stripe Checkout.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import enforce_rate_limit, get_current_user
from src.billing.stripe_client import StripeNotConfigured, create_checkout_session
from src.db.models import User
from src.db.repositories.billing import invoices_for_user, subscriptions_for_user
from src.db.session import get_db
from src.logging_config import get_logger
from src.platforms.http_client import PlatformHttpError
from src.runtime_config import get_setting

logger = get_logger(__name__)

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


class CheckoutRequest(BaseModel):
    tier: Literal["starter", "pro", "agency", "enterprise"]


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/checkout-session", response_model=CheckoutResponse)
def start_checkout(
    payload: CheckoutRequest, current_user: User = Depends(get_current_user)
) -> CheckoutResponse:
    """Create a Stripe Checkout session and return the URL to redirect the user to.

    The subscription itself is not recorded here — it is written when Stripe delivers the
    `checkout.session.completed` webhook, so an abandoned checkout leaves no state behind.
    """
    base_url = get_setting("APP_BASE_URL", "http://localhost:5173").rstrip("/")
    try:
        session = create_checkout_session(
            tier=payload.tier,
            user_id=str(current_user.id),
            customer_email=current_user.email,
            success_url=f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/billing/cancelled",
        )
    except StripeNotConfigured as exc:
        logger.error("checkout unavailable", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="billing not configured"
        ) from exc
    except PlatformHttpError as exc:
        logger.error("stripe rejected checkout session", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="could not start checkout"
        ) from exc

    return CheckoutResponse(checkout_url=session["url"], session_id=session["id"])
