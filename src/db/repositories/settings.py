"""Persistence for dashboard-editable settings.

Every value is encrypted at rest with AES-256-GCM (`src/security/crypto.py`), including the
non-secret ones — a uniform representation means no code path can accidentally persist a key
in plaintext because it was misclassified.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AppSetting
from src.logging_config import get_logger
from src.security.crypto import CryptoError, decrypt, encrypt

logger = get_logger(__name__)


def all_settings(db: Session) -> dict[str, str]:
    """Return every stored setting decrypted, keyed by setting name.

    A value that fails to decrypt (key rotated without re-entry) is skipped rather than
    raised, so one bad row cannot take the whole application down.
    """
    values: dict[str, str] = {}
    for row in db.execute(select(AppSetting)).scalars().all():
        try:
            values[row.key] = decrypt(row.value_encrypted)
        except CryptoError:
            logger.error("could not decrypt setting", extra={"key": row.key})
    return values


def stored_keys(db: Session) -> set[str]:
    """Names of settings that have a stored value (without decrypting them)."""
    return set(db.execute(select(AppSetting.key)).scalars().all())


def set_setting(db: Session, key: str, value: str, *, is_secret: bool, actor: str) -> None:
    """Create or replace one setting. An empty value deletes the override."""
    row = db.get(AppSetting, key)
    if not value:
        if row is not None:
            db.delete(row)
            db.commit()
        return

    encrypted = encrypt(value)
    if row is None:
        row = AppSetting(key=key, value_encrypted=encrypted, is_secret=is_secret)
        db.add(row)
    else:
        row.value_encrypted = encrypted
        row.is_secret = is_secret
    row.updated_by = actor
    db.commit()
