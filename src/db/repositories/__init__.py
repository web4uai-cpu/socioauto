"""Repository layer: all persistence goes through these modules.

Each function takes a SQLAlchemy ``Session`` and returns plain domain objects/dicts, keeping
route handlers free of ORM query details. Replaces the former in-memory ``src/api/store.py``.
"""

from __future__ import annotations

from src.db.repositories import accounts, analytics, audit, billing, campaigns, users

__all__ = ["accounts", "analytics", "audit", "billing", "campaigns", "users"]
