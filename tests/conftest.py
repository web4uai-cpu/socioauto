"""Shared pytest setup: isolate every run in a fresh temporary SQLite database.

`src/db/session.py` reads `DATABASE_URL` at import time, so this must run before any
`src.*` import — pytest imports conftest first, satisfying that ordering.
"""
from __future__ import annotations

import os
import tempfile

# Point the app at a throwaway DB file created per test session.
_tmp_db = os.path.join(tempfile.mkdtemp(prefix="smai-test-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
os.environ.setdefault("ADMIN_EMAILS", "demo@brand.com")
# Run Celery tasks in-process during tests (no external broker required).
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

import pytest  # noqa: E402

from src.db.models import Base  # noqa: E402
from src.db.session import engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> None:
    """Create all tables once for the test session against the temp DB."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
