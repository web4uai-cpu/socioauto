# 📅 SocialMediaAI — Implementation Plan

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## Phase 1: Foundation
- [x] Project scaffolding & CI/CD setup (`.github/workflows/ci.yml` runs ruff + pytest)
- [x] Database schema design & migration (`src/db/models.py`, `db/migrations/001_init.sql` + `002_persistence.sql`, Alembic in `alembic/`; routes now use `get_db`)
- [x] API Gateway & authentication (JWT in `src/security/auth.py`; OAuth2 for platform accounts done in `src/platforms/oauth/`)
- [x] Basic user management & roles (`src/api/routes/users.py`: create/list/role-update, now DB-backed via `src/db/repositories/users.py`)
- [x] Docker & Kubernetes deployment (`Dockerfile`, `docker-compose.yml` incl. Celery worker, `k8s/`)

## Phase 2: Core Agents
- [x] Research Agent (baseline `TrendResearchAgent`; CrewAI + web search integration pending)
- [x] Content Agent (baseline `ContentCreationAgent`, multi-platform limits)
- [ ] Prompt template engine
- [x] Agent message bus (event-driven) — Celery queue per orchestrator run (`src/orchestrator/tasks.py`)
- [ ] Basic review queue UI

## Phase 3: Visual & Video
- [ ] Visual Agent (Stable Diffusion integration)
- [ ] Image generation pipeline
- [ ] Video Agent (script + thumbnail)
- [ ] Asset storage & CDN (AWS S3 + CloudFront)
- [ ] Asset management UI

## Phase 4: Publishing & Automation
- [x] Social media API integrations (OAuth) — `src/platforms/oauth/` (X/LinkedIn/Meta/TikTok) + REST clients `src/platforms/clients.py`
- [x] Publishing Agent with optimal timing (real API clients + per-platform circuit breaker; simulate mode without live creds)
- [x] Auto-scheduling engine (`src/scheduling/`: optimal-time scoring, `/campaigns/{id}/schedule`, Celery-beat due-post runner `scheduling.publish_due_posts`)
- [ ] Content calendar view
- [x] Human-in-the-loop approval workflow (moderation gate: `verdict != approved` blocks scheduling/publishing)
- [x] Inbound webhooks with signature verification (`src/api/routes/webhooks.py`: `/webhooks/meta`, `/webhooks/x`)

## Phase 5: Analytics & SEO
- [x] Analytics Agent (baseline `AnalyticsAgent`; engagement tracking pending real platform data)
- [ ] Lead generation & scoring
- [ ] SEO optimization engine
- [ ] Performance dashboard
- [ ] Automated reporting

## Phase 6: Admin & Financial
- [ ] Advanced admin panel
- [ ] Subscription management (Stripe)
- [ ] Revenue tracking & reporting
- [ ] User analytics board
- [ ] Financial management module

## Phase 7: Scale & Optimize
- [ ] Performance optimization
- [ ] Multi-tenant architecture
- [ ] White-label capabilities
- [ ] Advanced ML models
- [~] Production hardening & security audit (audit-log table, encrypted OAuth tokens, prod secret fail-fast `src/security/startup.py`, TLS/retry/circuit-breaker on outbound calls; full pen-test pending)

## Traceability

| Phase item | Code / Doc |
|---|---|
| Research Agent | [src/agents/trend_research.py](src/agents/trend_research.py) |
| Content Agent | [src/agents/content_creation.py](src/agents/content_creation.py) |
| Human-in-the-loop approval | [src/agents/moderation.py](src/agents/moderation.py) |
| CI/CD | [.github/workflows/ci.yml](.github/workflows/ci.yml) |
| DB schema & migration | [src/db/models.py](src/db/models.py), [db/migrations/001_init.sql](db/migrations/001_init.sql), [src/db/session.py](src/db/session.py) |
| User management & roles | [src/api/routes/users.py](src/api/routes/users.py) |
| Docker & Kubernetes | [Dockerfile](Dockerfile), [docker-compose.yml](docker-compose.yml), [k8s/](k8s/) |
| Publishing Agent | [src/agents/publishing.py](src/agents/publishing.py) |
| Auto-scheduling (baseline) | [src/agents/scheduling.py](src/agents/scheduling.py) |
| Analytics Agent | [src/agents/analytics.py](src/agents/analytics.py) |
| Orchestrator | [src/orchestrator/graph.py](src/orchestrator/graph.py) |
| API Gateway (baseline) | [src/api/main.py](src/api/main.py) |
| System design / data model | [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) |
| Agent specs | [docs/AGENTS.md](docs/AGENTS.md) |

Notes:
- Phase 2/4/5 items above are marked done only for their **baseline in-process implementation**
  (no external APIs, no message bus, no persistence yet) — see Phase 1/3/4 remaining items for
  what's needed to make them production-ready.
- Keep this file in sync: update checkboxes as work lands, and add new rows to the traceability
  table when new modules are created.
