---
name: scheduling
description: Pick optimal publish times per platform/audience timezone and enqueue jobs. Use only for content with an approved moderation verdict.
---

# Scheduling Skill

1. Verify `content_item.status == 'approved'` before doing anything — refuse otherwise.
2. Use historical `analytics_snapshots` engagement-by-hour data if available; else use platform best-practice defaults.
3. Account for audience timezone distribution per brand/platform.
4. Avoid collisions: don't schedule two items on the same platform within the brand's minimum gap window.
5. Enqueue the job (Celery/Redis) and record `{content_id, scheduled_at, queue_job_id}`.
