"""Analytics Agent: pulls per-post performance and turns it into recommendations.

Metrics come from each platform's own metrics endpoint via `RestPlatformClient.fetch_metrics`.
Without a connected account that call returns zeros (simulate mode), so `item.metrics` stays
empty rather than recording a fake row of zeros as if it were a real measurement.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.agents.base import BaseAgent
from src.analytics.insights import build_recommendations, summarize
from src.logging_config import get_logger
from src.orchestrator.state import CampaignState, ContentItem, ContentStatus
from src.platforms.clients import get_client
from src.platforms.http_client import PlatformHttpError

logger = get_logger(__name__)

_METRIC_KEYS = ("impressions", "likes", "shares", "comments", "clicks")


class AnalyticsAgent(BaseAgent):
    """Measure published posts, summarize performance, and suggest improvements."""

    name = "analytics"

    def run(self, state: CampaignState) -> CampaignState:
        """Fetch metrics for published items, then append a snapshot and recommendations."""
        published = [i for i in state.calendar if i.status == ContentStatus.PUBLISHED]
        for item in published:
            metrics = self._fetch(state, item)
            if metrics:
                item.metrics = metrics

        posts = [
            {
                "platform": item.platform,
                "kind": item.kind.value,
                # Bucket by publish hour so "best posting hour" is comparable.
                "hour": item.published_at.hour if item.published_at else None,
                "metrics": item.metrics,
            }
            for item in published
        ]
        summary = summarize(posts)
        state.recommendations = build_recommendations(posts)
        state.analytics.append(
            {
                "captured_at": datetime.now(UTC).isoformat(),
                "published_count": len(published),
                **summary,
            }
        )
        state.note(
            f"[{self.name}] measured {summary['posts_measured']}/{len(published)} published "
            f"items, {len(state.recommendations)} recommendations"
        )
        return state

    def _fetch(self, state: CampaignState, item: ContentItem) -> dict | None:
        """Pull one post's metrics. Returns None when unavailable or all-zero.

        A failure here must never break the pipeline: analytics is a read-only feedback loop,
        and a metrics outage should cost insight, not the campaign.
        """
        if not item.external_post_id:
            return None
        token = state.access_tokens.get(item.platform)
        if token is None:
            return None  # simulate mode — no real post to measure
        try:
            raw = get_client(item.platform).fetch_metrics(item.external_post_id, access_token=token)
        except PlatformHttpError as exc:
            logger.warning(
                "metrics fetch failed", extra={"platform": item.platform, "error": str(exc)}
            )
            return None

        metrics = {key: raw[key] for key in _METRIC_KEYS if isinstance(raw.get(key), int)}
        # An all-zero response is indistinguishable from "not measured yet"; don't record it
        # as data, or it will drag every average toward zero.
        return metrics if any(metrics.get(k) for k in _METRIC_KEYS) else None
