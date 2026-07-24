---
name: engagement
description: Monitor comments/replies/DMs on published content, draft on-brand responses, and flag anything needing human escalation. Use for inbound social interactions.
---

# Engagement Skill

1. Ingest inbound events (webhook or poll) for comments, replies, DMs, mentions.
2. Draft a response matching brand voice guidelines — keep it concise and platform-appropriate.
3. Escalate to a human queue (`escalated = true`) for: complaints, legal/compliance topics, PR-risk situations, angry/abusive users, anything ambiguous.
4. Never auto-send a response to escalated items — a human must approve first.
5. Return `{engagement_id, draft_response, escalated}`.
