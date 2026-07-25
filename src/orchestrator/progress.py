"""Per-campaign pipeline progress, so the UI can show agents completing one by one.

Backed by Redis when `REDIS_URL` is set (progress must be readable by whichever process
serves the poll request), with a process-local dict fallback so dev and tests work with no
broker running.

Progress is telemetry: **nothing here may raise into the pipeline**. A campaign that generates
correctly but fails to report progress is a far better outcome than the reverse, so every
public function swallows backend errors and degrades to the in-memory store.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from src.logging_config import get_logger

logger = get_logger(__name__)

# Progress is only interesting while a run is in flight or just finished.
TTL_SECONDS = 3600
_KEY_PREFIX = "campaign-progress:"

# Fallback store: campaign_id -> (payload, expires_at).
_memory: dict[str, tuple[dict[str, Any], float]] = {}
_lock = threading.Lock()

_redis_client: Any | None = None
_redis_checked = False


def _redis() -> Any | None:
    """Return a Redis client, or None when unavailable. Connection is attempted once."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
    except Exception as exc:  # noqa: BLE001 - fall back to memory, never break the pipeline
        logger.warning("progress store falling back to memory", extra={"error": str(exc)})
        _redis_client = None
    return _redis_client


def _prune() -> None:
    now = time.time()
    for key, (_, expires) in list(_memory.items()):
        if expires <= now:
            _memory.pop(key, None)


def set_progress(campaign_id: str, payload: dict[str, Any]) -> None:
    """Store the current progress snapshot for a campaign."""
    client = _redis()
    if client is not None:
        try:
            client.setex(f"{_KEY_PREFIX}{campaign_id}", TTL_SECONDS, json.dumps(payload))
            return
        except Exception as exc:  # noqa: BLE001 - degrade to memory
            logger.warning("progress write failed", extra={"error": str(exc)})
    with _lock:
        _prune()
        _memory[campaign_id] = (payload, time.time() + TTL_SECONDS)


def get_progress(campaign_id: str) -> dict[str, Any] | None:
    """Return the latest progress snapshot, or None if nothing was recorded."""
    client = _redis()
    if client is not None:
        try:
            raw = client.get(f"{_KEY_PREFIX}{campaign_id}")
            if raw is not None:
                return json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - fall through to memory
            logger.warning("progress read failed", extra={"error": str(exc)})
    with _lock:
        _prune()
        entry = _memory.get(campaign_id)
    return entry[0] if entry else None


def reset() -> None:
    """Clear all progress and the cached client. Used by tests."""
    global _redis_client, _redis_checked
    with _lock:
        _memory.clear()
    _redis_client = None
    _redis_checked = False
