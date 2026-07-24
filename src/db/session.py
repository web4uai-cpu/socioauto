"""SQLAlchemy engine/session factory.

Not yet wired into the API routes (which still use the in-memory placeholder in
src/api/store.py) — this module exists so real persistence can be adopted incrementally
without changing route signatures. See IMPLEMENTATION_PLAN.md Phase 1.
"""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite:///./socialmedia.db"
)

engine_options: dict[str, object] = {"pool_pre_ping": True, "future": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
