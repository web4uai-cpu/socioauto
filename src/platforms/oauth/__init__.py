"""OAuth2 authorization-code flow for connecting platform accounts.

Public surface:
- ``get_provider(platform)`` -> configured ``OAuth2Provider`` (raises ``UnknownPlatform``)
- ``OAuthTokens`` -> exchanged/refreshed token bundle
- ``sign_state`` / ``verify_state`` -> CSRF-safe, stateless OAuth ``state`` handling
"""

from __future__ import annotations

from src.platforms.oauth.provider import (
    OAuth2Provider,
    OAuthTokens,
    UnknownPlatform,
    get_provider,
)
from src.platforms.oauth.state import InvalidState, sign_state, verify_state

__all__ = [
    "OAuthTokens",
    "OAuth2Provider",
    "UnknownPlatform",
    "get_provider",
    "InvalidState",
    "sign_state",
    "verify_state",
]
