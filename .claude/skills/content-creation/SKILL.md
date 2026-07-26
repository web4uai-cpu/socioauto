---
name: content-creation
description: Generate platform-specific copy, hashtags, and media briefs for a calendar item. Use when drafting the actual post text/media brief before moderation.
---

# Content Creation Skill

1. Respect per-platform character limits (X 280, LinkedIn ~3000, Instagram caption ~2200,
   YouTube/Shorts description ~5000 — YouTube's separate title is capped at 100 chars).
2. Match brand tone/voice from `brand.voice_guidelines`.
3. Produce `{platform, body, hashtags[], media_brief, cta}`.
4. Never invent statistics, quotes, or claims not supplied in context.
5. Flag any regulated-industry claims (medical/financial/legal) explicitly so Moderation can review.
6. Hand off the draft to `moderation` — never skip straight to scheduling/publishing.
