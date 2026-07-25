"""Billing persistence: admin read views plus the Stripe-webhook write path.

Writes are only ever driven by a signature-verified Stripe webhook
(`src/api/routes/webhooks.py`), which is the single source of truth for subscription and
invoice state — the API never mutates billing records directly from user input.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Invoice, Subscription


def subscriptions_for_user(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(select(Subscription).where(Subscription.user_id == user_id)).scalars().all()
    return [
        {
            "id": str(s.id),
            "tier": s.tier,
            "status": s.status,
            "current_period_end": s.current_period_end,
        }
        for s in rows
    ]


def invoices_for_user(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(Invoice)
            .join(Subscription, Invoice.subscription_id == Subscription.id)
            .where(Subscription.user_id == user_id)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(i.id),
            "amount_due": float(i.amount_due),
            "currency": i.currency,
            "status": i.status,
            "issued_at": i.issued_at,
        }
        for i in rows
    ]


def subscription_by_stripe_id(db: Session, stripe_subscription_id: str) -> Subscription | None:
    return db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
    ).scalar_one_or_none()


def upsert_subscription(
    db: Session,
    *,
    stripe_subscription_id: str,
    user_id: uuid.UUID | None = None,
    stripe_customer_id: str | None = None,
    tier: str | None = None,
    status: str | None = None,
    current_period_end: datetime | None = None,
) -> Subscription | None:
    """Create or update the subscription identified by `stripe_subscription_id`.

    Returns None when the record does not exist yet and no `user_id` was supplied to create
    it — Stripe can deliver subscription events out of order, and an event we cannot
    attribute to a user is dropped rather than guessed at.
    """
    subscription = subscription_by_stripe_id(db, stripe_subscription_id)
    if subscription is None:
        if user_id is None:
            return None
        subscription = Subscription(user_id=user_id, stripe_subscription_id=stripe_subscription_id)
        db.add(subscription)

    # Only overwrite fields the event actually carried.
    if stripe_customer_id is not None:
        subscription.stripe_customer_id = stripe_customer_id
    if tier is not None:
        subscription.tier = tier
    if status is not None:
        subscription.status = status
    if current_period_end is not None:
        subscription.current_period_end = current_period_end

    db.commit()
    db.refresh(subscription)
    return subscription


def upsert_invoice(
    db: Session,
    *,
    subscription_id: uuid.UUID,
    stripe_invoice_id: str,
    amount_due: float,
    currency: str,
    status: str,
    issued_at: datetime,
    paid_at: datetime | None = None,
) -> Invoice:
    """Create or update the invoice identified by `stripe_invoice_id` (idempotent on retries)."""
    invoice = db.execute(
        select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice_id)
    ).scalar_one_or_none()
    if invoice is None:
        invoice = Invoice(subscription_id=subscription_id, stripe_invoice_id=stripe_invoice_id)
        db.add(invoice)

    invoice.amount_due = amount_due
    invoice.currency = currency
    invoice.status = status
    invoice.issued_at = issued_at
    invoice.paid_at = paid_at

    db.commit()
    db.refresh(invoice)
    return invoice
