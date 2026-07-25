"""Translate verified Stripe webhook events into subscription/invoice records.

Only the events we actually act on are handled; anything else is acknowledged and ignored
so Stripe does not retry deliveries we have no use for.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.db.repositories.billing import (
    subscription_by_stripe_id,
    upsert_invoice,
    upsert_subscription,
)
from src.logging_config import get_logger

logger = get_logger(__name__)

# Stripe's subscription statuses are a superset of the ones our schema allows.
SUBSCRIPTION_STATUS_MAP = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "unpaid": "past_due",
    "incomplete": "past_due",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
}

VALID_TIERS = {"free", "starter", "pro", "agency", "enterprise"}


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _tier(obj: dict[str, Any]) -> str | None:
    tier = (obj.get("metadata") or {}).get("tier")
    return tier if tier in VALID_TIERS else None


def handle_event(db: Session, event: dict[str, Any]) -> str:
    """Apply a Stripe event. Returns a short outcome label for logging/tests."""
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        return _handle_checkout_completed(db, obj)
    if event_type.startswith("customer.subscription."):
        return _handle_subscription_event(db, event_type, obj)
    if event_type.startswith("invoice."):
        return _handle_invoice_event(db, obj)

    logger.info("ignoring stripe event", extra={"event_type": event_type})
    return "ignored"


def _handle_checkout_completed(db: Session, obj: dict[str, Any]) -> str:
    stripe_subscription_id = obj.get("subscription")
    user_reference = obj.get("client_reference_id")
    if not stripe_subscription_id or not user_reference:
        logger.warning("checkout session missing subscription or client_reference_id")
        return "skipped"
    try:
        user_id = uuid.UUID(str(user_reference))
    except ValueError:
        logger.warning("checkout session client_reference_id is not a user id")
        return "skipped"

    upsert_subscription(
        db,
        stripe_subscription_id=str(stripe_subscription_id),
        user_id=user_id,
        stripe_customer_id=obj.get("customer"),
        tier=_tier(obj) or "starter",
        status="active",
    )
    return "subscription_created"


def _handle_subscription_event(db: Session, event_type: str, obj: dict[str, Any]) -> str:
    stripe_subscription_id = obj.get("id")
    if not stripe_subscription_id:
        return "skipped"

    if event_type == "customer.subscription.deleted":
        status = "canceled"
    else:
        status = SUBSCRIPTION_STATUS_MAP.get(obj.get("status", ""))

    updated = upsert_subscription(
        db,
        stripe_subscription_id=str(stripe_subscription_id),
        stripe_customer_id=obj.get("customer"),
        tier=_tier(obj),
        status=status,
        current_period_end=_timestamp(obj.get("current_period_end")),
    )
    if updated is None:
        # Event arrived before the checkout that creates the record; Stripe will resend.
        logger.warning("unknown stripe subscription", extra={"id": str(stripe_subscription_id)})
        return "unknown_subscription"
    return "subscription_updated"


def _handle_invoice_event(db: Session, obj: dict[str, Any]) -> str:
    stripe_invoice_id = obj.get("id")
    stripe_subscription_id = obj.get("subscription")
    if not stripe_invoice_id or not stripe_subscription_id:
        return "skipped"

    subscription = subscription_by_stripe_id(db, str(stripe_subscription_id))
    if subscription is None:
        logger.warning("invoice for unknown subscription", extra={"id": str(stripe_invoice_id)})
        return "unknown_subscription"

    paid_at = _timestamp((obj.get("status_transitions") or {}).get("paid_at"))
    upsert_invoice(
        db,
        subscription_id=subscription.id,
        stripe_invoice_id=str(stripe_invoice_id),
        # Stripe reports money in the currency's smallest unit.
        amount_due=(obj.get("amount_due") or 0) / 100,
        currency=obj.get("currency", "usd"),
        status=obj.get("status", "open"),
        issued_at=_timestamp(obj.get("created")) or datetime.now(tz=timezone.utc),
        paid_at=paid_at,
    )
    return "invoice_synced"
