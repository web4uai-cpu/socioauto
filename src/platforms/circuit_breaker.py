"""Per-platform circuit breaker so one platform's outage can't cascade (SYSTEM_DESIGN §6).

A simple in-process breaker: after ``failure_threshold`` consecutive failures the circuit
opens and calls fast-fail for ``reset_timeout`` seconds, then allows a trial call (half-open).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, reset_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    def _allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.reset_timeout:
            return True  # half-open: allow a trial call
        return False

    def call(self, fn: Callable[[], T]) -> T:
        with self._lock:
            if not self._allow():
                raise CircuitOpenError("circuit is open")
        try:
            result = fn()
        except Exception:
            with self._lock:
                self._failures += 1
                if self._failures >= self.failure_threshold:
                    self._opened_at = time.monotonic()
            raise
        with self._lock:
            self._failures = 0
            self._opened_at = None
        return result


_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_breaker(platform: str) -> CircuitBreaker:
    with _registry_lock:
        if platform not in _breakers:
            _breakers[platform] = CircuitBreaker()
        return _breakers[platform]
