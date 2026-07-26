"""Per-platform optimal send-time scoring.

Preferred posting hours are **local to the audience**, not UTC: "11 AM on Instagram" only means
anything in the audience's own timezone. `next_optimal_slot` converts into that timezone, finds
the next preferred hour, and returns a UTC-aware datetime for storage — so the scheduler and DB
stay in UTC while the windows stay meaningful.

Windows come from docs/AGENT_WORKFLOW.md Phase 5.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.logging_config import get_logger
from src.orchestrator.state import DEFAULT_TIMEZONE as STATE_DEFAULT_TIMEZONE

logger = get_logger(__name__)

# Canonical default lives with the campaign state it belongs to.
DEFAULT_TIMEZONE = STATE_DEFAULT_TIMEZONE

# Preferred posting hours in the audience's local time, best first.
_OPTIMAL_HOURS: dict[str, list[int]] = {
    # 11 AM - 1 PM and 7 PM - 9 PM
    "instagram": [11, 12, 19, 20],
    # 8 AM - 10 AM and 12 PM - 2 PM, weekdays only
    "linkedin": [8, 9, 12, 13],
    # 9 AM, 12 PM, 3 PM, 6 PM
    "x": [9, 12, 15, 18],
    # Not specified in the workflow doc; these follow the same evening-skew heuristic.
    "facebook": [9, 13, 15, 19],
    "tiktok": [12, 16, 18, 20],
    # Afternoon/evening skew — long-form watch sessions start after work.
    "youtube": [14, 16, 17, 20],
    "youtube_shorts": [12, 15, 18, 21],
}
_DEFAULT_HOURS = [9, 12, 15, 18]
_WEEKDAY_ONLY = {"linkedin"}

# How far ahead to scan before giving up (2 weeks of hourly candidates).
_MAX_LOOKAHEAD_HOURS = 24 * 14


def optimal_hours(platform: str) -> list[int]:
    """Return the ranked list of preferred posting hours (audience-local) for a platform."""
    return _OPTIMAL_HOURS.get(platform, _DEFAULT_HOURS)


def resolve_timezone(name: str | None) -> tzinfo:
    """Resolve an IANA timezone name, degrading rather than raising.

    A bad or unavailable timezone should mis-time a post, never fail a campaign. Falls back to
    the default, then to UTC — the last step matters on hosts with no system tz database, where
    even the default lookup can fail unless `tzdata` is installed.
    """
    for candidate in filter(None, (name, DEFAULT_TIMEZONE)):
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            logger.warning("timezone unavailable", extra={"timezone": candidate})
    return UTC


def next_optimal_slot(
    platform: str, after: datetime, timezone: str | None = DEFAULT_TIMEZONE
) -> datetime:
    """Return the next optimal posting time strictly after ``after`` for ``platform``.

    Scans forward hour by hour in the audience's local timezone for the first slot whose local
    hour is preferred, skipping weekends for weekday-only platforms. A naive ``after`` is
    treated as UTC. The result is always timezone-aware UTC.
    """
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)

    tz = resolve_timezone(timezone)
    hours = set(optimal_hours(platform))
    weekday_only = platform in _WEEKDAY_ONLY

    # Work in local time so "9 AM" means 9 AM where the audience is.
    local = after.astimezone(tz)
    candidate = local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    for _ in range(_MAX_LOOKAHEAD_HOURS):
        is_weekend = candidate.weekday() >= 5
        if candidate.hour in hours and not (weekday_only and is_weekend):
            return candidate.astimezone(UTC)
        candidate += timedelta(hours=1)

    # Unreachable with any sane hour set; return something valid rather than looping forever.
    return candidate.astimezone(UTC)
