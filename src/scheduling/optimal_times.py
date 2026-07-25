"""Per-platform optimal send-time scoring.

Preferred posting hours (UTC) are drawn from widely published engagement heuristics per
platform. ``next_optimal_slot`` finds the next preferred hour at or after a given moment; the
Scheduling Agent uses it to space a campaign's posts across upcoming optimal windows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# Preferred hours of day (UTC, 24h) per platform, best first. Weekends are de-prioritised for
# professional networks by skipping Sat/Sun in ``next_optimal_slot``.
_OPTIMAL_HOURS: dict[str, list[int]] = {
    "x": [13, 15, 17, 9, 21],
    "instagram": [11, 13, 19, 21, 9],
    "linkedin": [8, 10, 12, 17, 7],
    "tiktok": [18, 20, 22, 12, 16],
    "facebook": [13, 15, 19, 9, 20],
}
_DEFAULT_HOURS = [9, 12, 15, 18]
_WEEKDAY_ONLY = {"linkedin"}


def optimal_hours(platform: str) -> list[int]:
    """Return the ranked list of preferred posting hours (UTC) for a platform."""
    return _OPTIMAL_HOURS.get(platform, _DEFAULT_HOURS)


def next_optimal_slot(platform: str, after: datetime) -> datetime:
    """Return the next optimal posting time strictly after ``after`` for ``platform``.

    Scans forward hour-by-hour (up to two weeks) for the first slot whose hour is in the
    platform's preferred set, skipping weekends for weekday-only platforms. ``after`` is treated
    as UTC; the result is timezone-aware UTC on the hour.
    """
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    hours = set(optimal_hours(platform))
    weekday_only = platform in _WEEKDAY_ONLY
    # Start from the next whole hour after `after`.
    candidate = after.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    for _ in range(24 * 14):
        is_weekend = candidate.weekday() >= 5
        if candidate.hour in hours and not (weekday_only and is_weekend):
            return candidate
        candidate += timedelta(hours=1)
    return candidate  # fallback: two weeks out (should never hit with sane config)
