"""Connected social-platform account persistence."""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import SocialAccount
from src.logging_config import get_logger
from src.security.crypto import CryptoError, decrypt

logger = get_logger(__name__)


def _to_dict(account: SocialAccount) -> dict[str, Any]:
    return {
        "id": str(account.id),
        "user_id": str(account.user_id),
        "platform": account.platform,
        "external_account_id": account.external_account_id,
        "display_name": account.display_name,
    }


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    platform: str,
    external_account_id: str,
    display_name: str | None,
    credentials_ref: str,
) -> dict[str, Any]:
    account = SocialAccount(
        user_id=user_id,
        platform=platform,
        external_account_id=external_account_id,
        display_name=display_name,
        credentials_ref=credentials_ref,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _to_dict(account)


def for_user(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(SocialAccount).where(SocialAccount.user_id == user_id)
    ).scalars().all()
    return [_to_dict(a) for a in rows]


def _extract_access_token(credentials_ref: str) -> str | None:
    """Decrypt a stored credentials_ref and pull out the usable access token.

    Handles both OAuth bundles (JSON with ``access_token``) and manually connected
    API keys (raw string). Returns ``None`` if decryption fails.
    """
    try:
        plaintext = decrypt(credentials_ref)
    except CryptoError:
        logger.error("failed to decrypt stored credentials")
        return None
    try:
        parsed = json.loads(plaintext)
    except (ValueError, TypeError):
        return plaintext  # manually connected raw API key/token
    if isinstance(parsed, dict):
        return parsed.get("access_token")
    return plaintext


def access_tokens_for_user(db: Session, user_id: uuid.UUID) -> dict[str, str]:
    """Return a ``{platform: access_token}`` map for a user's connected accounts.

    Tokens are decrypted transiently for the publish call and never persisted or logged.
    """
    rows = db.execute(
        select(SocialAccount).where(SocialAccount.user_id == user_id)
    ).scalars().all()
    tokens: dict[str, str] = {}
    for account in rows:
        token = _extract_access_token(account.credentials_ref)
        if token:
            tokens[account.platform] = token
    return tokens
