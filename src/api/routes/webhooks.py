"""Inbound platform webhooks for mentions/DMs and Stripe billing (docs/SYSTEM_DESIGN.md §4).

Signatures are verified before any payload is processed. Secrets are resolved via
`src.runtime_config` (never hardcoded). Meta also performs a GET verification handshake on
subscription. Platform events are normalized, persisted, and handed to the Engagement Agent
asynchronously.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.billing.stripe_client import StripeNotConfigured, verify_webhook_signature
from src.billing.sync import handle_event
from src.db.repositories import engagements as engagements_repo
from src.db.session import get_db
from src.logging_config import get_logger
from src.platforms.http_client import PlatformHttpError
from src.platforms.inbound import InboundEngagement, parse_meta, parse_x
from src.runtime_config import get_setting

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_hmac_sha256(secret: str, body: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    # Meta sends "sha256=<hex>"; X sends the bare hex — handle both.
    provided = signature.split("=", 1)[-1]
    return hmac.compare_digest(expected, provided)


@router.get("/meta")
def meta_verify(request: Request) -> Response:
    """Meta subscription verification handshake (echoes hub.challenge when the token matches)."""
    params = request.query_params
    verify_token = get_setting("META_WEBHOOK_VERIFY_TOKEN")
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == verify_token:
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verification failed")


def _ingest(db: Session, platform: str, events: list[InboundEngagement]) -> int:
    """Persist inbound engagements and queue each new one for the Engagement Agent.

    Rows are written synchronously so nothing is lost if the worker is down; drafting runs
    off the request thread. Duplicates (platforms redeliver) are dropped by the repository.
    """
    from src.orchestrator.tasks import process_inbound_engagement

    queued = 0
    for event in events:
        engagement = engagements_repo.record_inbound(
            db,
            platform=platform,
            external_id=event.external_id,
            kind=event.kind,
            author=event.author,
            message=event.message,
        )
        if engagement is None:
            continue  # already recorded by an earlier delivery
        process_inbound_engagement.delay(str(engagement.id))
        queued += 1
    return queued


@router.post("/meta")
async def meta_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    secret = get_setting("META_APP_SECRET")
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()
    if not secret or not _verify_hmac_sha256(secret, body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        # Acknowledge so Meta stops redelivering a payload we can never parse.
        logger.warning("meta webhook payload was not JSON", extra={"bytes": len(body)})
        return {"status": "accepted", "queued": 0}

    queued = _ingest(db, "meta", parse_meta(payload))
    logger.info("meta webhook received", extra={"bytes": len(body), "queued": queued})
    return {"status": "accepted", "queued": queued}


@router.post("/x")
async def x_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    secret = get_setting("X_WEBHOOK_SECRET")
    signature = request.headers.get("X-Twitter-Webhooks-Signature", "")
    body = await request.body()
    if not secret or not _verify_hmac_sha256(secret, body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("x webhook payload was not JSON", extra={"bytes": len(body)})
        return {"status": "accepted", "queued": 0}

    queued = _ingest(db, "x", parse_x(payload))
    logger.info("x webhook received", extra={"bytes": len(body), "queued": queued})
    return {"status": "accepted", "queued": queued}


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Sync subscription/invoice state from Stripe.

    Stripe is the source of truth for billing: nothing here trusts the request body until
    the signature is verified against STRIPE_WEBHOOK_SECRET.
    """
    body = await request.body()
    try:
        verify_webhook_signature(body, request.headers.get("Stripe-Signature", ""))
    except StripeNotConfigured as exc:
        logger.error("stripe webhook not configured", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="billing not configured"
        ) from exc
    except PlatformHttpError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="bad signature"
        ) from exc

    try:
        event = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="malformed payload"
        ) from exc

    outcome = handle_event(db, event)
    logger.info(
        "stripe webhook processed", extra={"event_type": event.get("type"), "outcome": outcome}
    )
    return {"status": "accepted", "outcome": outcome}
