"""Stripe API access and webhook signature verification.

Outbound calls go through `src.platforms.http_client.request_json` so Stripe gets the same
timeout/retry/TLS enforcement as every other third-party API (per .claude/CLAUDE.md).
Secrets are resolved on each call (never captured at import time) so a key entered in the
admin dashboard takes effect without a restart.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from src.platforms.http_client import PlatformHttpError, request_json
from src.runtime_config import get_setting

STRIPE_API_BASE = "https://api.stripe.com/v1"
# Reject webhook payloads whose timestamp is older than this, to blunt replay attacks.
SIGNATURE_TOLERANCE_SECONDS = 300

# Tier -> setting key holding that tier's Stripe price id.
PRICE_ENV_BY_TIER = {
    "starter": "STRIPE_PRICE_STARTER",
    "pro": "STRIPE_PRICE_PRO",
    "agency": "STRIPE_PRICE_AGENCY",
    "enterprise": "STRIPE_PRICE_ENTERPRISE",
}


class StripeNotConfigured(RuntimeError):
    """Raised when a Stripe call is attempted without the required configuration."""


def _secret_key() -> str:
    key = get_setting("STRIPE_SECRET_KEY")
    if not key:
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set")
    return key


def price_id_for_tier(tier: str) -> str:
    setting_key = PRICE_ENV_BY_TIER.get(tier)
    price_id = get_setting(setting_key) if setting_key else ""
    if not price_id:
        raise StripeNotConfigured(f"no Stripe price configured for tier '{tier}'")
    return price_id


def create_checkout_session(
    *, tier: str, user_id: str, customer_email: str, success_url: str, cancel_url: str
) -> dict[str, Any]:
    """Create a Stripe Checkout session for a subscription and return the Stripe payload.

    `client_reference_id` carries our user id so the webhook can attribute the resulting
    subscription back to the right account.
    """
    payload = {
        "mode": "subscription",
        "line_items[0][price]": price_id_for_tier(tier),
        "line_items[0][quantity]": "1",
        "client_reference_id": user_id,
        "customer_email": customer_email,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata[tier]": tier,
    }
    return request_json(
        "POST",
        f"{STRIPE_API_BASE}/checkout/sessions",
        headers={
            "Authorization": f"Bearer {_secret_key()}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=payload,
    )


def verify_webhook_signature(body: bytes, signature_header: str, *, now: int | None = None) -> None:
    """Validate a `Stripe-Signature` header, raising PlatformHttpError when it doesn't match.

    Stripe signs the string `{timestamp}.{raw_body}` with HMAC-SHA256 and sends it as
    `t=<timestamp>,v1=<hex>` (multiple v1 values during secret rotation).
    """
    secret = get_setting("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise StripeNotConfigured("STRIPE_WEBHOOK_SECRET is not set")

    timestamp = ""
    signatures: list[str] = []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)

    if not timestamp or not signatures:
        raise PlatformHttpError("malformed Stripe-Signature header")

    try:
        age = (now if now is not None else int(time.time())) - int(timestamp)
    except ValueError as exc:
        raise PlatformHttpError("invalid Stripe-Signature timestamp") from exc
    if abs(age) > SIGNATURE_TOLERANCE_SECONDS:
        raise PlatformHttpError("Stripe-Signature timestamp outside tolerance")

    signed_payload = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise PlatformHttpError("Stripe-Signature mismatch")
