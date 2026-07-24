"""Read-only billing views (subscriptions + invoices) backed by the DB."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Invoice, Subscription


def subscriptions_for_user(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalars().all()
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
    rows = db.execute(
        select(Invoice)
        .join(Subscription, Invoice.subscription_id == Subscription.id)
        .where(Subscription.user_id == user_id)
    ).scalars().all()
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
