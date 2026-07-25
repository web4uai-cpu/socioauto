"""Startup security checks: refuse to boot a production deployment with insecure defaults."""

from __future__ import annotations

import os

from src.logging_config import get_logger
from src.security.auth import SECRET_KEY

logger = get_logger(__name__)

_DEV_JWT_DEFAULT = "dev-only-insecure-secret-change-me"


class InsecureConfigurationError(RuntimeError):
    """Raised at startup when a production deployment is missing required secrets."""


def _is_production() -> bool:
    return os.environ.get("APP_ENV", "development").lower() in ("production", "prod")


def verify_production_secrets() -> None:
    """Fail fast if running in production with dev-default or missing secrets.

    No-op outside production so local/dev/test runs keep working with the built-in fallbacks.
    """
    if not _is_production():
        return
    problems: list[str] = []
    if SECRET_KEY == _DEV_JWT_DEFAULT:
        problems.append("JWT_SECRET_KEY is unset (using the insecure dev default)")
    if not os.environ.get("APP_ENCRYPTION_KEY"):
        problems.append("APP_ENCRYPTION_KEY is unset (credential encryption key)")
    if problems:
        for problem in problems:
            logger.error("insecure production configuration", extra={"problem": problem})
        raise InsecureConfigurationError("; ".join(problems))
