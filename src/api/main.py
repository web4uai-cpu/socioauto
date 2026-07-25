"""FastAPI app exposing the social media automation platform's API."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from src.api.routes import (
    accounts,
    analytics,
    auth,
    billing,
    campaigns,
    media,
    settings,
    users,
    webhooks,
)
from src.db.models import Base
from src.db.session import engine
from src.orchestrator.graph import run_campaign
from src.orchestrator.state import CampaignState
from src.security.startup import verify_production_secrets
from src.storage import media_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration and initialize persistence before serving requests."""
    verify_production_secrets()  # refuse to boot prod with insecure defaults
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Social Media AI Agent Platform", lifespan=lifespan)

cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Account-Tier"],
)


app.include_router(auth.router)
app.include_router(campaigns.router)
app.include_router(analytics.router)
app.include_router(accounts.router)
app.include_router(accounts.callback_router)  # OAuth redirect target (no bearer auth)
app.include_router(users.router)
app.include_router(billing.router)
app.include_router(settings.router)
app.include_router(webhooks.router)
app.include_router(media.router)

# Dev-only static serving of uploaded media; production should point at a real object store
# (S3/R2) behind the same `MediaStorage` interface instead of mounting local disk.
app.mount("/media", StaticFiles(directory=media_storage.root), name="media")


class CampaignRequest(BaseModel):
    brand_name: str
    platforms: list[str]
    voice_guidelines: dict = {}
    trends: list[dict] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    """Readiness probe: verify the application can reach its configured database."""
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.post("/campaigns/run")
def run(req: CampaignRequest) -> dict:
    state = CampaignState(
        brand_name=req.brand_name,
        platforms=req.platforms,
        voice_guidelines=req.voice_guidelines,
        trends=req.trends,
    )
    result = run_campaign(state)
    return {
        "log": result.log,
        "calendar": [item.__dict__ for item in result.calendar],
    }
