"""AES-256-GCM encryption for sensitive secrets (e.g. platform API keys).

Used by the accounts.connect endpoint so raw social-platform credentials are never persisted
in plaintext — only the resulting ciphertext (`credentials_ref`) is stored, per the mandatory
rule in .claude/CLAUDE.md.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.logging_config import get_logger

logger = get_logger(__name__)

_KEY_ENV_VAR = "APP_ENCRYPTION_KEY"  # 32-byte key, base64-encoded, set via secrets manager/.env


class CryptoError(Exception):
    """Raised when a secret cannot be encrypted or decrypted."""


def _load_key() -> bytes:
    """Load the 32-byte AES-256 key from the environment.

    Returns:
        The raw 32-byte key.

    Raises:
        CryptoError: If the configured key does not decode to exactly 32 bytes.
    """
    encoded = os.environ.get(_KEY_ENV_VAR)
    if not encoded:
        # Dev-only fallback so local runs/tests work without extra setup. Never used if
        # APP_ENCRYPTION_KEY is set, which it must be in any real deployment.
        encoded = base64.b64encode(b"0" * 32).decode()
    try:
        key = base64.b64decode(encoded)
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"{_KEY_ENV_VAR} is not valid base64") from exc
    if len(key) != 32:
        raise CryptoError(f"{_KEY_ENV_VAR} must decode to exactly 32 bytes for AES-256")
    return key


def encrypt(plaintext: str) -> str:
    """Encrypt a secret, returning a base64 string of `nonce || ciphertext`.

    Args:
        plaintext: The raw secret to encrypt (e.g. a platform API key).

    Returns:
        A base64-encoded ciphertext safe to store/log as a `credentials_ref`.

    Raises:
        CryptoError: If the encryption key is misconfigured or encryption fails.
    """
    try:
        key = _load_key()
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")
    except CryptoError:
        raise
    except Exception as exc:  # noqa: BLE001 - never leak raw secret material in the error
        logger.error("encryption failed", extra={"error": str(exc)})
        raise CryptoError("failed to encrypt secret") from exc


def decrypt(token: str) -> str:
    """Decrypt a ciphertext previously produced by `encrypt`.

    Args:
        token: Base64 string of `nonce || ciphertext` as returned by `encrypt`.

    Returns:
        The original plaintext secret.

    Raises:
        CryptoError: If the token is malformed or fails authentication (tampered/wrong key).
    """
    try:
        key = _load_key()
        raw = base64.b64decode(token)
        nonce, ciphertext = raw[:12], raw[12:]
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, associated_data=None)
        return plaintext.decode("utf-8")
    except CryptoError:
        raise
    except InvalidTag as exc:
        logger.error("decryption failed: invalid tag")
        raise CryptoError("ciphertext failed authentication (tampered or wrong key)") from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("decryption failed", extra={"error": str(exc)})
        raise CryptoError("failed to decrypt secret") from exc
