"""Normalize platform webhook payloads into a common inbound-engagement shape.

Each platform ships a different envelope; these functions reduce them to
`(external_id, kind, author, message)` tuples so the Engagement Agent sees one format.
Parsing is deliberately tolerant — an unrecognized or partial entry is skipped rather than
raising, because a malformed item must not cause us to reject (and have the platform
endlessly redeliver) the whole batch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InboundEngagement:
    external_id: str
    kind: str  # "mention" | "comment" | "dm"
    author: str | None
    message: str


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def parse_meta(payload: dict[str, Any]) -> list[InboundEngagement]:
    """Extract comments and DMs from a Meta (Facebook/Instagram) webhook payload.

    Meta nests events as `entry[].changes[]` (comments/mentions) and `entry[].messaging[]`
    (direct messages).
    """
    events: list[InboundEngagement] = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue

        for change in entry.get("changes") or []:
            value = (change or {}).get("value") or {}
            external_id = _clean(value.get("id") or value.get("comment_id"))
            message = _clean(value.get("text") or value.get("message"))
            if not external_id or not message:
                continue
            author = _clean((value.get("from") or {}).get("id")) or None
            kind = (
                "comment"
                if value.get("comment_id") or change.get("field") == "comments"
                else "mention"
            )
            events.append(
                InboundEngagement(
                    external_id=f"meta:{external_id}",
                    kind=kind,
                    author=author,
                    message=message,
                )
            )

        for messaging in entry.get("messaging") or []:
            message_obj = (messaging or {}).get("message") or {}
            external_id = _clean(message_obj.get("mid"))
            message = _clean(message_obj.get("text"))
            if not external_id or not message:
                continue
            events.append(
                InboundEngagement(
                    external_id=f"meta:{external_id}",
                    kind="dm",
                    author=_clean((messaging.get("sender") or {}).get("id")) or None,
                    message=message,
                )
            )
    return events


def parse_x(payload: dict[str, Any]) -> list[InboundEngagement]:
    """Extract mentions and DMs from an X (Twitter) Account Activity payload."""
    events: list[InboundEngagement] = []

    for tweet in payload.get("tweet_create_events") or []:
        if not isinstance(tweet, dict):
            continue
        external_id = _clean(tweet.get("id_str") or str(tweet.get("id") or ""))
        message = _clean(tweet.get("text") or tweet.get("full_text"))
        if not external_id or not message:
            continue
        events.append(
            InboundEngagement(
                external_id=f"x:{external_id}",
                kind="mention",
                author=_clean((tweet.get("user") or {}).get("screen_name")) or None,
                message=message,
            )
        )

    for dm in payload.get("direct_message_events") or []:
        if not isinstance(dm, dict):
            continue
        external_id = _clean(dm.get("id"))
        message_create = dm.get("message_create") or {}
        message = _clean((message_create.get("message_data") or {}).get("text"))
        if not external_id or not message:
            continue
        events.append(
            InboundEngagement(
                external_id=f"x:{external_id}",
                kind="dm",
                author=_clean(message_create.get("sender_id")) or None,
                message=message,
            )
        )
    return events
