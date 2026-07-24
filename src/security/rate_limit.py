"""Simple in-memory per-user sliding-window rate limiter.

Production note: this is process-local and resets on restart — swap for a Redis-backed
implementation (e.g. via `slowapi` + `REDIS_URL`) before running multiple API instances.
"""
from __future__ import annotations

import time
from collections import defaultdict

TIER_LIMITS_PER_MINUTE = {
    "free": 100,
    "starter": 300,
    "pro": 1000,
    "agency": 5000,
    "enterprise": 20000,
}


class RateLimitExceeded(Exception):
    pass


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, tier: str = "free") -> None:
        limit = TIER_LIMITS_PER_MINUTE.get(tier, TIER_LIMITS_PER_MINUTE["free"])
        now = time.monotonic()
        window_start = now - 60
        hits = [t for t in self._hits[key] if t > window_start]
        if len(hits) >= limit:
            raise RateLimitExceeded(f"rate limit of {limit} req/min exceeded for '{key}'")
        hits.append(now)
        self._hits[key] = hits


rate_limiter = RateLimiter()
