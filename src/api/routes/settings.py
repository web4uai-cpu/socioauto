"""Admin settings API: configure integration keys from the dashboard instead of `.env`.

Secret values are write-only. A GET never returns a stored secret — only whether it is
configured and a masked preview — so a compromised admin session cannot exfiltrate keys
that were entered earlier.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import enforce_rate_limit, require_admin
from src.db.repositories import audit as audit_repo
from src.db.repositories.settings import all_settings, set_setting, stored_keys
from src.db.session import get_db
from src.llm.provider import reset_provider
from src.logging_config import get_logger
from src.runtime_config import SETTING_SPECS, SPECS_BY_KEY, invalidate_cache

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/settings",
    tags=["admin"],
    dependencies=[Depends(enforce_rate_limit)],
)


class SettingView(BaseModel):
    key: str
    label: str
    group: str
    is_secret: bool
    help_text: str
    choices: list[str]
    # Where the effective value comes from, so an operator can tell whether the dashboard
    # or the deployment environment is currently winning.
    source: str  # "database" | "environment" | "unset"
    configured: bool
    # Plain value for non-secrets; a masked preview for secrets.
    value: str


class SettingsUpdate(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"


def _build_views(db: Session) -> list[SettingView]:
    """Describe every editable setting and its current effective value."""
    overrides = all_settings(db)
    views: list[SettingView] = []
    for spec in SETTING_SPECS:
        db_value = overrides.get(spec.key, "")
        env_value = os.environ.get(spec.key, "").strip()
        effective = db_value or env_value
        if db_value:
            source = "database"
        elif env_value:
            source = "environment"
        else:
            source = "unset"
        views.append(
            SettingView(
                key=spec.key,
                label=spec.label,
                group=spec.group,
                is_secret=spec.is_secret,
                help_text=spec.help_text,
                choices=list(spec.choices),
                source=source,
                configured=bool(effective),
                value=_mask(effective)
                if (spec.is_secret and effective)
                else ("" if spec.is_secret else effective),
            )
        )
    return views


@router.get("", response_model=list[SettingView])
def list_settings(
    _: str = Depends(require_admin), db: Session = Depends(get_db)
) -> list[SettingView]:
    """Return every editable setting with its current effective value."""
    return _build_views(db)


@router.put("", response_model=list[SettingView])
def update_settings(
    payload: SettingsUpdate,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[SettingView]:
    """Persist settings. Sending an empty string for a key clears its override.

    Only keys in the published catalog are accepted — infrastructure secrets such as the
    encryption key and database URL are intentionally not editable here.
    """
    unknown = sorted(set(payload.values) - set(SPECS_BY_KEY))
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"not configurable from the dashboard: {', '.join(unknown)}",
        )

    for key, raw in payload.values.items():
        spec = SPECS_BY_KEY[key]
        value = raw.strip()
        if spec.choices and value and value not in spec.choices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{key} must be one of: {', '.join(spec.choices)}",
            )
        set_setting(db, key, value, is_secret=spec.is_secret, actor=admin)

    # New keys must take effect immediately, and the LLM client caches its credentials.
    invalidate_cache()
    reset_provider()

    audit_repo.record(
        db,
        actor=admin,
        action="settings.updated",
        entity_type="app_settings",
        # Names only — never record the values themselves in the audit trail.
        details={"keys": sorted(payload.values)},
    )
    logger.info("settings updated", extra={"keys": sorted(payload.values), "actor": admin})

    return _build_views(db)


@router.get("/status")
def integration_status(
    _: str = Depends(require_admin), db: Session = Depends(get_db)
) -> dict[str, bool]:
    """Quick per-integration readiness flags for dashboard badges."""
    overrides = all_settings(db)

    def ready(key: str) -> bool:
        return bool(overrides.get(key) or os.environ.get(key, "").strip())

    return {
        "ai": ready("LLM_API_KEY"),
        "billing": ready("STRIPE_SECRET_KEY") and ready("STRIPE_WEBHOOK_SECRET"),
        "x": ready("X_CLIENT_ID") and ready("X_CLIENT_SECRET"),
        "meta": ready("META_APP_ID") and ready("META_APP_SECRET"),
        "linkedin": ready("LINKEDIN_CLIENT_ID") and ready("LINKEDIN_CLIENT_SECRET"),
        "tiktok": ready("TIKTOK_CLIENT_KEY") and ready("TIKTOK_CLIENT_SECRET"),
        "stored_in_database": bool(stored_keys(db)),
    }
