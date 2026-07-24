# Project Memory — Social Media AI Agent Platform

This file is loaded automatically by Claude Code as persistent project context.

## What this project is
An 8-agent AI system automating social media: trend research → content strategy → content
creation → moderation → scheduling → publishing → engagement → analytics. See
[README.md](../README.md), [docs/SYSTEM_DESIGN.md](../docs/SYSTEM_DESIGN.md), and
[docs/AGENTS.md](../docs/AGENTS.md).

## Conventions
- Language: Python 3.11+ for backend/agents, FastAPI for the API layer.
- Each agent lives in `src/agents/<name>/` with `agent.py` (logic) + `prompt.md` (LLM prompt).
- Never hardcode API keys/secrets — use `os.environ` + `.env` (never commit `.env`).
- All platform API calls go through `src/platforms/http_client.py` (enforces timeout/retry/TLS).
- Moderation Agent is a **mandatory gate** — Publishing Agent must refuse unapproved content.
- Pydantic models validate every API boundary input.
- Tests live in `tests/`, mirroring `src/` structure; use `pytest`.

## Build / run commands
```powershell
pip install -r requirements.txt
uvicorn src.api.main:app --reload
python -m src.orchestrator.run
pytest
```

## Do
- Keep agent functions pure: `(CampaignState) -> CampaignState`, side effects logged.
- Add new platforms under `src/platforms/<platform>/` implementing the `PlatformClient` protocol.
- Update `docs/AGENTS.md` when changing an agent's prompt/output schema.

## Don't
- Don't let Publishing Agent call platform APIs without a prior `approved` moderation verdict.
- Don't commit secrets, tokens, or `.env` files.
- Don't bypass rate limiting/backoff logic in `http_client.py`.

## Active skills
See `.claude/skills/` — one skill per agent domain (trend-research, content-strategy,
content-creation, moderation, scheduling, publishing, engagement, analytics).

## Hooks
See `.claude/settings.json` — pre-commit secret scan, post-edit Python lint/format on
`src/**/*.py`, and a session-start reminder of the moderation gate rule.
