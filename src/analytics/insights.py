"""Turn published-post metrics into a performance summary and concrete recommendations.

Everything here is computed from metrics the platforms actually returned. Two rules keep the
output honest:

1. **No advice from a sample of one.** Comparative claims ("X outperforms LinkedIn") need at
   least `MIN_GROUPS_FOR_COMPARISON` groups with `MIN_POSTS_PER_GROUP` posts each, otherwise
   the "insight" is noise dressed up as analysis.
2. **Absent data stays absent.** Click-through needs click counts most platforms do not return
   on the basic metrics endpoint; when they are missing, CTR is `None`, not zero.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

# Guards against drawing conclusions from too little data.
MIN_POSTS_PER_GROUP = 2
MIN_GROUPS_FOR_COMPARISON = 2
# A gap smaller than this between best and worst is not worth acting on.
MIN_MEANINGFUL_GAP = 0.005  # half a percentage point of engagement rate


def engagement_rate(metrics: dict[str, Any]) -> float | None:
    """Engagements per impression. None when impressions are unknown or zero."""
    impressions = metrics.get("impressions") or 0
    if impressions <= 0:
        return None
    engagements = (
        (metrics.get("likes") or 0) + (metrics.get("shares") or 0) + (metrics.get("comments") or 0)
    )
    return round(engagements / impressions, 4)


def click_through_rate(metrics: dict[str, Any]) -> float | None:
    """Clicks per impression, or None when the platform did not report clicks."""
    impressions = metrics.get("impressions") or 0
    clicks = metrics.get("clicks")
    if clicks is None or impressions <= 0:
        return None
    return round(clicks / impressions, 4)


def summarize(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll up metrics across published posts.

    Args:
        posts: dicts with `platform`, `kind`, `metrics`, and optionally `scheduled_hour`.
    """
    totals = defaultdict(int)
    measured = 0
    for post in posts:
        metrics = post.get("metrics") or {}
        if not metrics:
            continue
        measured += 1
        for key in ("impressions", "likes", "shares", "comments"):
            totals[key] += metrics.get(key) or 0
        if metrics.get("clicks") is not None:
            totals["clicks"] += metrics["clicks"]

    summary: dict[str, Any] = {
        "posts_measured": measured,
        "impressions": totals["impressions"],
        "likes": totals["likes"],
        "shares": totals["shares"],
        "comments": totals["comments"],
        "engagement_rate": engagement_rate(totals) if measured else None,
    }
    # Only claim a CTR if at least one platform actually reported clicks.
    any_clicks = any((p.get("metrics") or {}).get("clicks") is not None for p in posts)
    summary["clicks"] = totals["clicks"] if any_clicks else None
    summary["click_through_rate"] = (
        click_through_rate({**totals, "clicks": totals["clicks"]}) if any_clicks else None
    )
    return summary


def _rates_by(posts: list[dict[str, Any]], key: str) -> dict[str, float]:
    """Average engagement rate per group, keeping only groups with enough posts."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        rate = engagement_rate(post.get("metrics") or {})
        value = post.get(key)
        if rate is not None and value:
            grouped[str(value)].append(rate)
    return {
        name: round(sum(rates) / len(rates), 4)
        for name, rates in grouped.items()
        if len(rates) >= MIN_POSTS_PER_GROUP
    }


def _comparison(posts: list[dict[str, Any]], key: str, label: str) -> dict[str, Any] | None:
    """Best-vs-worst recommendation for one grouping, or None if it would be noise."""
    rates = _rates_by(posts, key)
    if len(rates) < MIN_GROUPS_FOR_COMPARISON:
        return None
    best, best_rate = max(rates.items(), key=lambda kv: kv[1])
    worst, worst_rate = min(rates.items(), key=lambda kv: kv[1])
    if best == worst or (best_rate - worst_rate) < MIN_MEANINGFUL_GAP:
        return None
    return {
        "type": f"best_{key}",
        "message": (
            f"{label} '{best}' is your strongest at {best_rate:.1%} engagement, "
            f"versus {worst_rate:.1%} for '{worst}'. Shift more of the mix toward '{best}'."
        ),
        "evidence": {
            "best": best,
            "best_rate": best_rate,
            "worst": worst,
            "worst_rate": worst_rate,
        },
    }


def build_recommendations(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate improvement suggestions from measured posts.

    Returns an explicit "not enough data" note rather than inventing advice when nothing can
    be concluded — an empty dashboard is more useful than a confident wrong one.
    """
    measured = [p for p in posts if (p.get("metrics") or {}).get("impressions")]
    if not measured:
        return [
            {
                "type": "no_data",
                "message": (
                    "No performance data yet. Metrics appear once posts are published to a "
                    "connected account — simulated posts return none."
                ),
                "evidence": {},
            }
        ]

    recommendations: list[dict[str, Any]] = []
    for key, label in (("platform", "Platform"), ("kind", "Post type"), ("hour", "Posting hour")):
        found = _comparison(measured, key, label)
        if found:
            recommendations.append(found)

    if not any((p.get("metrics") or {}).get("clicks") is not None for p in measured):
        recommendations.append(
            {
                "type": "no_click_data",
                "message": (
                    "Click-through rate is unavailable: no connected platform reported click "
                    "counts. Add UTM-tagged links and read clicks from your own analytics."
                ),
                "evidence": {},
            }
        )

    if not recommendations:
        recommendations.append(
            {
                "type": "insufficient_sample",
                "message": (
                    f"Not enough data to compare yet — needs {MIN_POSTS_PER_GROUP}+ measured "
                    f"posts in each of {MIN_GROUPS_FOR_COMPARISON}+ groups before differences "
                    "are meaningful."
                ),
                "evidence": {"posts_measured": len(measured)},
            }
        )
    return recommendations
