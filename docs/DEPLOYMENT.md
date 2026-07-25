# Deployment

## Environments

| Piece | Where | URL |
|---|---|---|
| Backend API | Railway | `https://socioauto-production.up.railway.app` |
| Frontend (admin dashboard) | Static host (Vercel/Netlify/Railway) | set via `VITE_API_BASE_URL` |
| Postgres + Redis | Railway plugins (or the `k8s/` manifests) | private network URLs |

## 0. Deploying with the Railway CLI

The backend lives in the Railway project **`aware-adaptation`** as the service
**`socioauto`** (alongside its Postgres and Redis plugins).

```bash
railway login
railway link -p aware-adaptation -e production -s socioauto
railway up --ci
```

`.railwayignore` keeps `.venv/` and `frontend/node_modules/` out of the upload — without it
the CLI ships ~200 MB the image never uses.

The image is built from the repo `Dockerfile`, which copies only `src/` and `db/`. Alembic
is therefore *not* in the container: new tables are created by `Base.metadata.create_all()`
at startup. That is fine for additive changes, but a destructive migration must be run
against the database separately before deploying.

## 1. Backend configuration

Only five values *must* come from the environment. Everything else can be entered later in
the dashboard's **Integrations** panel, which stores values AES-256-GCM encrypted in the
database and takes precedence over environment variables.

| Variable | Why it must be an env var |
|---|---|
| `APP_ENV=production` | Makes the API fail-fast on insecure defaults at boot |
| `DATABASE_URL` | Needed before the settings table can be read |
| `REDIS_URL` | Celery broker, needed at worker start |
| `JWT_SECRET_KEY` | Rotating it from a web form would invalidate all sessions |
| `APP_ENCRYPTION_KEY` | Rotating it from a web form would make every stored secret undecryptable |

Generate the two secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"                 # JWT_SECRET_KEY
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"  # APP_ENCRYPTION_KEY
```

> **These are not optional.** With `JWT_SECRET_KEY` unset the app falls back to the literal
> string in `src/security/auth.py`, which is public in this repo — anyone can then forge a
> valid token for any account. With `ADMIN_EMAILS` unset it defaults to `demo@brand.com`, so
> a forged token for that address gets admin. `APP_ENV=production` is what turns on the
> fail-fast guard that refuses to boot in this state; leaving it unset silently disables the
> check. Set all four together.
>
> Rotating `APP_ENCRYPTION_KEY` later makes every stored platform token undecryptable —
> users must reconnect their social accounts. Rotating `JWT_SECRET_KEY` only invalidates
> live sessions.

Set them on the service without triggering a redeploy per variable:

```bash
railway variables --skip-deploys \
  --set "APP_ENV=production" \
  --set "JWT_SECRET_KEY=..." \
  --set "APP_ENCRYPTION_KEY=..." \
  --set "ADMIN_EMAILS=you@yourdomain.com"
```

Also set on Railway:

```
ADMIN_EMAILS=you@yourdomain.com
CORS_ALLOW_ORIGINS=https://your-frontend-domain
APP_BASE_URL=https://your-frontend-domain
OAUTH_REDIRECT_BASE=https://socioauto-production.up.railway.app/api/v1/accounts
```

`ADMIN_EMAILS` gates the Integrations panel — only these accounts can read or write settings.

## 2. Database migrations

Run before/with each deploy:

```bash
alembic upgrade head
```

The app also calls `Base.metadata.create_all()` at startup as a safety net, but Alembic is
the source of truth for schema changes.

## 3. Everything else via the dashboard

Sign in as an `ADMIN_EMAILS` account and open **Integrations** to set:

- **AI provider** — `LLM_PROVIDER=anthropic` + `LLM_API_KEY`. Until this is set the agents
  emit deterministic placeholder copy rather than generated content.
- **Billing** — Stripe secret key, webhook signing secret, and the four price IDs.
- **Social platforms** — OAuth client IDs/secrets and webhook secrets for X, Meta,
  LinkedIn, TikTok.

Each field shows whether its current value comes from the database or the environment.

## 4. Third-party webhook endpoints

Register these against the Railway host:

| Provider | URL | Secret setting |
|---|---|---|
| Stripe | `https://socioauto-production.up.railway.app/webhooks/stripe` | `STRIPE_WEBHOOK_SECRET` |
| Meta | `https://socioauto-production.up.railway.app/webhooks/meta` | `META_APP_SECRET` + `META_WEBHOOK_VERIFY_TOKEN` |
| X | `https://socioauto-production.up.railway.app/webhooks/x` | `X_WEBHOOK_SECRET` |

Stripe events consumed: `checkout.session.completed`, `customer.subscription.*`, `invoice.*`.

## 5. Worker + scheduler

The API alone does not publish scheduled posts or draft engagement replies. Run both:

```bash
celery -A src.orchestrator.tasks.celery_app worker -Q orchestrator -l info
celery -A src.orchestrator.tasks.celery_app beat -l info
```

On Railway these are separate services sharing the same image and env vars. `beat` drives
`scheduling.publish_due_posts` once a minute.

## 6. Frontend

```bash
cd frontend
npm install
VITE_API_BASE_URL=https://socioauto-production.up.railway.app/api/v1 npm run build
# deploy the generated dist/ directory
```

Whatever origin the frontend is served from must appear in the backend's
`CORS_ALLOW_ORIGINS`.

## 7. Smoke test

```bash
curl https://socioauto-production.up.railway.app/health   # {"status":"ok"}
curl https://socioauto-production.up.railway.app/ready    # {"status":"ready"} — checks the DB
```

Then sign in to the dashboard, set the LLM key in Integrations, create a campaign, and
confirm the generated copy is real content rather than the topic string echoed back.

## Kubernetes alternative

`k8s/` holds a full manifest set (namespace, Postgres, Redis, API, worker, ingress). Copy
`k8s/secrets.example.yaml` to `secrets.yaml`, fill in base64 values, and apply — never
commit the filled-in file.
