---
name: analytics
description: Collect post performance metrics and feed insights back into content strategy for the next planning cycle. Use after content has been live for the platform's typical measurement window.
---

# Analytics Skill

1. Pull impressions/likes/shares/comments per published item via platform APIs.
2. Store as `analytics_snapshots` rows (append-only, timestamped).
3. Aggregate by topic/format/platform to identify top performers.
4. Feed the aggregated summary back to `content-strategy` so the next cycle prioritizes what worked.
5. Do not delete or overwrite historical snapshots — analytics history must remain auditable.
