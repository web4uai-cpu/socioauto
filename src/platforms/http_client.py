"""Shared HTTP client for outbound platform API calls: timeout, retry, backoff, TLS.

Every outbound call to a third-party platform API must go through this module so timeouts,
TLS verification, and exponential-backoff retries are enforced uniformly (per .claude/CLAUDE.md).
"""
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from src.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class PlatformHttpError(Exception):
    """Raised for non-retryable platform API failures (bad request, policy rejection, etc.)."""


class PlatformTransientError(Exception):
    """Raised for retryable failures (network errors, 429, 5xx). Retried with backoff."""


def _raise_for_status(response: httpx.Response) -> httpx.Response:
    if response.status_code == 429 or response.status_code >= 500:
        raise PlatformTransientError(f"transient {response.status_code} from {response.url}")
    if response.status_code >= 400:
        raise PlatformHttpError(
            f"{response.status_code} from {response.url}: {response.text[:200]}"
        )
    return response


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((PlatformTransientError, httpx.TransportError)),
    reraise=True,
)
def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a TLS-verified HTTP request with retry/backoff and return the parsed JSON body.

    Raises:
        PlatformHttpError: On a non-retryable 4xx response.
        PlatformTransientError: On 429/5xx after retries are exhausted.
    """
    with httpx.Client(timeout=DEFAULT_TIMEOUT, verify=True) as client:
        response = client.request(
            method, url, headers=headers, params=params, data=data, json=json
        )
    _raise_for_status(response)
    return response.json() if response.content else {}


def publish_post(platform: str, body: str, *, access_token: str | None = None) -> str:
    """Publish a post to the given platform via its real API client.

    Delegates to ``src.platforms.clients.get_client`` (config-driven REST client with a
    per-platform circuit breaker). With no ``access_token`` the client runs in simulate mode
    and returns a synthetic id, so the pipeline stays runnable without live credentials.

    Args:
        platform: Target platform key (e.g. "x", "linkedin").
        body: Rendered post text to publish.
        access_token: Decrypted OAuth access token for the connected account, if available.

    Returns:
        The external post id assigned by the platform.

    Raises:
        PlatformHttpError: If the body is invalid or the platform rejects the request.
    """
    # Imported here to avoid a circular import (clients imports from this module).
    from src.platforms.clients import get_client

    try:
        return get_client(platform).publish(body, access_token=access_token)
    except PlatformHttpError:
        raise
    except Exception as exc:  # noqa: BLE001 - convert any transport-layer error uniformly
        logger.error("unexpected platform error", extra={"platform": platform, "error": str(exc)})
        raise PlatformHttpError(f"unexpected error publishing to {platform}: {exc}") from exc
