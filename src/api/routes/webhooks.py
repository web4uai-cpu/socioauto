"""Inbound platform webhooks for mentions/DMs (docs/SYSTEM_DESIGN.md §4).

Signatures are verified before any payload is processed. Secrets come from the environment
(never hardcoded). Meta also performs a GET verification handshake on subscription.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import APIRouter, HTTPException, Request, Response, status

from src.logging_config import get_logger

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
    verify_token = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "")
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == verify_token:
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verification failed")


@router.post("/meta")
async def meta_webhook(request: Request) -> dict:
    secret = os.environ.get("META_APP_SECRET", "")
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()
    if not secret or not _verify_hmac_sha256(secret, body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad signature")
    logger.info("meta webhook received", extra={"bytes": len(body)})
    # TODO(engagement): enqueue inbound mentions/DMs for the Engagement Agent.
    return {"status": "accepted"}


@router.post("/x")
async def x_webhook(request: Request) -> dict:
    secret = os.environ.get("X_WEBHOOK_SECRET", "")
    signature = request.headers.get("X-Twitter-Webhooks-Signature", "")
    body = await request.body()
    if not secret or not _verify_hmac_sha256(secret, body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad signature")
    logger.info("x webhook received", extra={"bytes": len(body)})
    return {"status": "accepted"}
