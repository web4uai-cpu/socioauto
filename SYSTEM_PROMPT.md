# 🛠️ SocialMediaAI — System Build Prompt

You are an expert Full-Stack AI Engineer building SocialMediaAI, a multi-agent
social media automation platform. Follow these instructions precisely.

## Tech Stack
- Backend: Python 3.11, FastAPI, LangGraph, CrewAI
- Frontend: React 18, TypeScript, Tailwind CSS, shadcn/ui
- Database: PostgreSQL, MongoDB, Redis
- AI: OpenAI GPT-4o, Claude 3.5, Stable Diffusion XL
- Infrastructure: Docker, Kubernetes, AWS/GCP

## Core Features to Implement

### 1. Natural Language Input Parser
```python
class CampaignRequest(BaseModel):
    prompt: str
    platforms: List[str] = ["instagram", "twitter", "linkedin"]
    tone: str = "professional"
    cta: Optional[str] = None
    target_audience: Optional[str] = None
    schedule: Optional[datetime] = None
```

### 3. Database Schema

Implement PostgreSQL tables: `users`, `social_accounts`, `campaigns`, `posts`, `analytics`,
`subscriptions`, `invoices`.

- SQLAlchemy ORM models: [src/db/models.py](src/db/models.py)
- Raw SQL migration: [db/migrations/001_init.sql](db/migrations/001_init.sql)
- Keep both in sync when the schema changes.

Key constraints enforced:
- `social_accounts.credentials_ref` stores only a secrets-manager pointer, never a raw token.
- `posts.status` follows the moderation-gated lifecycle from
  [docs/AGENTS.md](docs/AGENTS.md) (`draft` → `pending_moderation` → `approved`/`rejected` →
  `scheduled` → `published`/`failed`).
- `analytics` is append-only (one row per snapshot, never updated/deleted).
- `subscriptions.tier` matches the pricing tiers in [REVENUE_MODEL.md](REVENUE_MODEL.md).

### 4. API Endpoints

Implemented as FastAPI routers under `src/api/routes/`:

| Endpoint | File |
|---|---|
| `POST /api/v1/campaigns` (create from natural language) | [src/api/routes/campaigns.py](src/api/routes/campaigns.py) |
| `GET /api/v1/campaigns/{id}` | [src/api/routes/campaigns.py](src/api/routes/campaigns.py) |
| `POST /api/v1/campaigns/{id}/approve` | [src/api/routes/campaigns.py](src/api/routes/campaigns.py) |
| `GET /api/v1/analytics/dashboard` | [src/api/routes/analytics.py](src/api/routes/analytics.py) |
| `POST /api/v1/accounts/connect` | [src/api/routes/accounts.py](src/api/routes/accounts.py) |
| `POST /api/v1/auth/token`, `/refresh` | [src/api/routes/auth.py](src/api/routes/auth.py) |

`create_campaign` runs Trend Research → Content Strategy → Content Creation → Moderation;
`approve_campaign` only then runs Scheduling → Publishing (human-in-the-loop gate). Persistence
is currently an in-memory placeholder ([src/api/store.py](src/api/store.py)) pending real
Postgres session wiring against [src/db/models.py](src/db/models.py). Tests:
[tests/test_api.py](tests/test_api.py).

### 5. Admin Dashboard

React 18 + TypeScript components under `frontend/src/components/`, composed in
[frontend/src/pages/AdminDashboard.tsx](frontend/src/pages/AdminDashboard.tsx):

- `UserManagementTable.tsx` — user list/roles/status
- `SubscriptionManagement.tsx` — tier + billing status per brand
- `AnalyticsBoard.tsx` — charts (Recharts) backed by `/analytics/dashboard`
- `FinancialManagement.tsx` — invoices/outstanding balance
- `CampaignReviewQueue.tsx` — human-in-the-loop approval UI calling `/campaigns/{id}/approve`

All components fetch through [frontend/src/api/client.ts](frontend/src/api/client.ts), a thin
wrapper that attaches the JWT bearer token from `localStorage`. Several backing admin list
endpoints (`/admin/users`, `/admin/subscriptions`, `/admin/invoices`, campaign list) are marked
TODO — only the endpoints explicitly requested in Section 4 exist today.

### 6. Security

- **JWT auth with refresh tokens**: [src/security/auth.py](src/security/auth.py) (`HS256`,
  15-min access / 7-day refresh), enforced via [src/api/deps.py](src/api/deps.py)
  `get_current_user_id`.
- **OAuth2 for social platforms**: not yet implemented — `accounts/connect` currently accepts a
  raw API key directly (see below); real OAuth2 authorization-code flow per platform is a
  Phase 4 item in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
- **AES-256 encryption for API keys**: [src/security/crypto.py](src/security/crypto.py) —
  AES-256-GCM, used by `POST /api/v1/accounts/connect` so raw keys are never persisted/returned.
- **Rate limiting per user**: [src/security/rate_limit.py](src/security/rate_limit.py) — in-memory
  sliding window, tiered by plan (see [REVENUE_MODEL.md](REVENUE_MODEL.md)); swap for a
  Redis-backed limiter before running multiple API instances.
- **Input validation with Pydantic**: [src/api/schemas.py](src/api/schemas.py) validates every
  request body.

## Mapping to Current Codebase

This build prompt describes the **target** production stack (LangGraph/CrewAI orchestration,
React/TypeScript frontend, Postgres+MongoDB+Redis, GPT-4o/Claude/SDXL). The repository currently
has a baseline Python-only implementation that this prompt's features should extend, not replace:

| Target feature | Current equivalent |
|---|---|
| `CampaignRequest` (natural language prompt, tone, CTA, audience, schedule) | [src/api/main.py](src/api/main.py) — existing `CampaignRequest` model has `brand_name`, `platforms`, `voice_guidelines`, `trends`; needs `prompt`, `tone`, `cta`, `target_audience`, `schedule` fields added |
| LangGraph/CrewAI orchestration | [src/orchestrator/graph.py](src/orchestrator/graph.py) — sequential pipeline, no LangGraph/CrewAI runtime yet |
| React/TypeScript frontend | not yet implemented |
| MongoDB (content DB), Redis (queue/cache) | schema drafted in [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md), not wired up |
| GPT-4o / Claude 3.5 / SDXL calls | [src/agents/trend_research.py](src/agents/trend_research.py), [src/agents/content_creation.py](src/agents/content_creation.py) — placeholders, no LLM calls wired yet |
| PostgreSQL schema (`users`, `social_accounts`, `campaigns`, `posts`, `analytics`, `subscriptions`, `invoices`) | [src/db/models.py](src/db/models.py), [db/migrations/001_init.sql](db/migrations/001_init.sql) |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full layer breakdown and
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for phased rollout status.

> Note: this build prompt was pasted incrementally. Paste any remaining "Core Features to
> Implement" sections and I'll extend this document and wire up matching code.
