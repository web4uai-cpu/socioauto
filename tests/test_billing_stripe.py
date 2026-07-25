"""Stripe checkout, webhook signature verification, and event synchronization."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.billing.stripe_client import StripeNotConfigured, verify_webhook_signature
from src.billing.sync import handle_event
from src.db.models import Subscription, User
from src.db.session import SessionLocal
from src.platforms.http_client import PlatformHttpError
from src.runtime_config import invalidate_cache

client = TestClient(app)

WEBHOOK_SECRET = "whsec_test_secret"


@pytest.fixture(autouse=True)
def _stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_123")
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _sign(body: bytes, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def _post_webhook(event: dict, signature: str | None = None):
    body = json.dumps(event).encode()
    return client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature or _sign(body)},
    )


def _make_user(db, email: str) -> User:
    user = User(email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- signature verification ---------------------------------------------------------


def test_valid_signature_accepted():
    body = b'{"type":"ping"}'
    verify_webhook_signature(body, _sign(body))  # does not raise


def test_wrong_secret_rejected():
    body = b'{"type":"ping"}'
    with pytest.raises(PlatformHttpError):
        verify_webhook_signature(body, _sign(body, secret="whsec_wrong"))


def test_stale_timestamp_rejected():
    body = b'{"type":"ping"}'
    stale = int(time.time()) - 3600
    with pytest.raises(PlatformHttpError):
        verify_webhook_signature(body, _sign(body, timestamp=stale))


def test_malformed_signature_header_rejected():
    with pytest.raises(PlatformHttpError):
        verify_webhook_signature(b"{}", "not-a-signature")


def test_missing_secret_raises_not_configured(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    invalidate_cache()
    with pytest.raises(StripeNotConfigured):
        verify_webhook_signature(b"{}", "t=1,v1=abc")


# --- webhook endpoint ---------------------------------------------------------------


def test_webhook_rejects_bad_signature():
    response = _post_webhook({"type": "ping"}, signature="t=1,v1=deadbeef")
    assert response.status_code == 401


def test_webhook_ignores_unhandled_event():
    response = _post_webhook({"type": "customer.created", "data": {"object": {}}})
    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"


# --- event synchronization ----------------------------------------------------------


def test_checkout_completed_creates_subscription(db):
    user = _make_user(db, f"checkout-{uuid.uuid4().hex[:8]}@brand.com")
    sub_id = f"sub_{uuid.uuid4().hex[:10]}"
    outcome = handle_event(
        db,
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "subscription": sub_id,
                    "customer": "cus_123",
                    "client_reference_id": str(user.id),
                    "metadata": {"tier": "pro"},
                }
            },
        },
    )
    assert outcome == "subscription_created"

    subscription = (
        db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).one()
    )
    assert subscription.user_id == user.id
    assert subscription.tier == "pro"
    assert subscription.status == "active"


def test_checkout_without_user_reference_is_skipped(db):
    outcome = handle_event(
        db,
        {
            "type": "checkout.session.completed",
            "data": {"object": {"subscription": "sub_orphan"}},
        },
    )
    assert outcome == "skipped"


def test_subscription_updated_maps_stripe_status(db):
    user = _make_user(db, f"status-{uuid.uuid4().hex[:8]}@brand.com")
    sub_id = f"sub_{uuid.uuid4().hex[:10]}"
    handle_event(
        db,
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "subscription": sub_id,
                    "client_reference_id": str(user.id),
                    "metadata": {"tier": "pro"},
                }
            },
        },
    )

    # Stripe's "unpaid" has no direct equivalent in our schema; it maps to past_due.
    outcome = handle_event(
        db,
        {
            "type": "customer.subscription.updated",
            "data": {"object": {"id": sub_id, "status": "unpaid"}},
        },
    )
    assert outcome == "subscription_updated"

    subscription = (
        db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).one()
    )
    assert subscription.status == "past_due"


def test_subscription_event_for_unknown_id_is_not_invented(db):
    outcome = handle_event(
        db,
        {
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_never_seen", "status": "active"}},
        },
    )
    assert outcome == "unknown_subscription"


def test_invoice_paid_is_recorded_in_major_units(db):
    user = _make_user(db, f"invoice-{uuid.uuid4().hex[:8]}@brand.com")
    sub_id = f"sub_{uuid.uuid4().hex[:10]}"
    handle_event(
        db,
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "subscription": sub_id,
                    "client_reference_id": str(user.id),
                    "metadata": {"tier": "pro"},
                }
            },
        },
    )

    invoice_id = f"in_{uuid.uuid4().hex[:10]}"
    outcome = handle_event(
        db,
        {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": invoice_id,
                    "subscription": sub_id,
                    "amount_due": 4900,  # cents
                    "currency": "usd",
                    "status": "paid",
                    "created": int(time.time()),
                    "status_transitions": {"paid_at": int(time.time())},
                }
            },
        },
    )
    assert outcome == "invoice_synced"

    from src.db.repositories.billing import invoices_for_user

    invoices = invoices_for_user(db, user.id)
    assert [i["amount_due"] for i in invoices] == [49.0]
    assert invoices[0]["status"] == "paid"


def test_invoice_replay_is_idempotent(db):
    user = _make_user(db, f"replay-{uuid.uuid4().hex[:8]}@brand.com")
    sub_id = f"sub_{uuid.uuid4().hex[:10]}"
    handle_event(
        db,
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "subscription": sub_id,
                    "client_reference_id": str(user.id),
                    "metadata": {"tier": "pro"},
                }
            },
        },
    )
    event = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": f"in_{uuid.uuid4().hex[:10]}",
                "subscription": sub_id,
                "amount_due": 1000,
                "currency": "usd",
                "status": "paid",
                "created": int(time.time()),
            }
        },
    }
    handle_event(db, event)
    handle_event(db, event)  # Stripe retries deliveries

    from src.db.repositories.billing import invoices_for_user

    assert len(invoices_for_user(db, user.id)) == 1
