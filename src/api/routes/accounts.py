"""Connect a social media platform account. Raw API keys are AES-256-GCM encrypted before
being stored — only the ciphertext (`credentials_ref`) is ever persisted or returned."""

from __future__ import annotations

import json
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import enforce_rate_limit, get_current_user
from src.api.schemas import AccountConnectRequest, AccountConnectResponse
from src.db.models import User
from src.db.repositories import accounts as accounts_repo
from src.db.repositories import audit
from src.db.session import get_db
from src.logging_config import get_logger
from src.platforms.oauth import (
    InvalidState,
    UnknownPlatform,
    get_provider,
    sign_state,
    verify_state,
)
from src.platforms.oauth.provider import OAuthConfigError, generate_pkce_pair
from src.security.crypto import CryptoError, encrypt

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/accounts", tags=["accounts"], dependencies=[Depends(enforce_rate_limit)]
)

_OAUTH_REDIRECT_BASE = os.environ.get(
    "OAUTH_REDIRECT_BASE", "http://localhost:8000/api/v1/accounts"
)


def _redirect_uri(platform: str) -> str:
    return f"{_OAUTH_REDIRECT_BASE}/{platform}/callback"


@router.get("", response_model=list[AccountConnectResponse])
def list_accounts(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AccountConnectResponse]:
    """List social accounts owned by the authenticated user without exposing credentials."""
    return [
        AccountConnectResponse(
            id=account["id"],
            platform=account["platform"],
            external_account_id=account["external_account_id"],
            display_name=account["display_name"],
            connected=True,
        )
        for account in accounts_repo.for_user(db, current_user.id)
    ]


@router.post("/connect", response_model=AccountConnectResponse, status_code=status.HTTP_201_CREATED)
def connect_account(
    req: AccountConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountConnectResponse:
    """Connect a social platform account, encrypting the provided API key before storage.

    Raises:
        HTTPException: 500 if the API key cannot be encrypted (misconfigured encryption key).
    """
    try:
        credentials_ref = encrypt(req.api_key)  # never store/log the raw api_key
    except CryptoError as exc:
        logger.error(
            "account connect failed: encryption error",
            extra={"platform": req.platform, "user_id": str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to securely store credentials",
        ) from exc
    account = accounts_repo.create(
        db,
        user_id=current_user.id,
        platform=req.platform,
        external_account_id=req.external_account_id,
        display_name=req.display_name,
        credentials_ref=credentials_ref,
    )
    audit.record(
        db,
        actor=current_user.email,
        action="account.connected",
        entity_type="social_account",
        entity_id=account["id"],
        details={"platform": req.platform},
    )
    logger.info(
        "social account connected",
        extra={"platform": req.platform, "user_id": str(current_user.id)},
    )
    return AccountConnectResponse(
        id=account["id"],
        platform=req.platform,
        external_account_id=req.external_account_id,
        display_name=req.display_name,
        connected=True,
    )


@router.get("/{platform}/authorize")
def start_oauth(platform: str, current_user: User = Depends(get_current_user)) -> dict[str, str]:
    """Begin the OAuth2 authorization-code flow: return the provider consent URL to redirect to.

    The returned ``state`` is a signed token binding the flow to this user (and PKCE verifier),
    so the callback needs no server-side session and is safe from CSRF.
    """
    try:
        provider = get_provider(platform)
    except UnknownPlatform as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    code_verifier = code_challenge = None
    if provider.config.use_pkce:
        code_verifier, code_challenge = generate_pkce_pair()
    state = sign_state(user_id=str(current_user.id), platform=platform, code_verifier=code_verifier)
    try:
        url = provider.authorization_url(
            state=state,
            redirect_uri=_redirect_uri(platform),
            code_challenge=code_challenge,
        )
    except OAuthConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"authorization_url": url, "state": state}


# Callback router has NO auth dependency: OAuth providers redirect the user's browser here
# without our bearer token. The signed ``state`` re-establishes the authenticated identity.
callback_router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@callback_router.get("/{platform}/callback", response_model=AccountConnectResponse)
def oauth_callback(
    platform: str, code: str, state: str, db: Session = Depends(get_db)
) -> AccountConnectResponse:
    """Exchange the authorization ``code`` for tokens and persist an encrypted account."""
    try:
        claims = verify_state(state)
    except InvalidState as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state"
        ) from exc
    if claims["platform"] != platform:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="State/platform mismatch"
        )

    provider = get_provider(platform)
    try:
        tokens = provider.exchange_code(
            code=code,
            redirect_uri=_redirect_uri(platform),
            code_verifier=claims["code_verifier"],
        )
    except OAuthConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    # Never persist raw tokens — encrypt the whole bundle into credentials_ref.
    try:
        credentials_ref = encrypt(
            json.dumps(
                {
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "expires_in": tokens.expires_in,
                    "scope": tokens.scope,
                }
            )
        )
    except CryptoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to securely store credentials",
        ) from exc

    account = accounts_repo.create(
        db,
        user_id=uuid.UUID(claims["user_id"]),
        platform=platform,
        external_account_id=f"{platform}:connected",
        display_name=None,
        credentials_ref=credentials_ref,
    )
    audit.record(
        db,
        actor=claims["user_id"],
        action="account.oauth_connected",
        entity_type="social_account",
        entity_id=account["id"],
        details={"platform": platform},
    )
    logger.info("oauth account connected", extra={"platform": platform})
    return AccountConnectResponse(
        id=account["id"],
        platform=platform,
        external_account_id=account["external_account_id"],
        display_name=None,
        connected=True,
    )
