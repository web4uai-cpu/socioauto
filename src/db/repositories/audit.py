"""Append-only audit-log writes for compliance (docs/SYSTEM_DESIGN.md §5)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.db.models import AuditLog


def record(
    db: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )
    db.commit()
