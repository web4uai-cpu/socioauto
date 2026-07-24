---
name: publishing
description: Call platform APIs to publish approved, scheduled content with retry/backoff and rate-limit handling. Use only for content that is scheduled and approved.
---

# Publishing Skill

1. Hard requirement: refuse to publish unless `status == 'approved'` and a `scheduled_at` job exists. Never bypass this check.
2. Use `src/platforms/http_client.py` for all outbound calls (enforces TLS, timeout, retry/backoff with jitter).
3. On 429/5xx: requeue with exponential backoff, respecting the platform's rate-limit window.
4. On 4xx (bad request/policy rejection from platform): mark `status = 'failed'`, notify Orchestrator for human review — do not silently retry.
5. On success: record `published_at` and the platform's external post id.
6. Never log or persist raw API credentials in plaintext logs.
