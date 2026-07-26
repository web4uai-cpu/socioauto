"""Runtime configuration resolved from the admin dashboard, falling back to the environment.

`get_setting()` is the single accessor every integration should use instead of reading
`os.environ` directly, so keys entered in the dashboard take effect without a redeploy.
Resolution order is: encrypted DB value -> environment variable -> default.

Values are cached in-process for `CACHE_TTL_SECONDS`; with multiple workers a change made
in the dashboard is visible everywhere within that window.

Deliberately NOT settable from the dashboard: `APP_ENCRYPTION_KEY` (rotating it from the UI
would make every stored secret undecryptable), `JWT_SECRET_KEY`, `DATABASE_URL`, and
`REDIS_URL`. Those stay environment/secret-manager only.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from src.logging_config import get_logger

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 30.0


@dataclass(frozen=True)
class SettingSpec:
    """One dashboard-editable setting."""

    key: str
    label: str
    group: str
    is_secret: bool = True
    help_text: str = ""
    choices: tuple[str, ...] = field(default=())


SETTING_SPECS: tuple[SettingSpec, ...] = (
    # --- AI provider ---------------------------------------------------------------
    SettingSpec(
        "LLM_PROVIDER",
        "Provider",
        "ai",
        is_secret=False,
        help_text="Leave as 'none' to run the agents with deterministic fallback copy.",
        choices=("none", "anthropic"),
    ),
    SettingSpec("LLM_API_KEY", "API key", "ai"),
    SettingSpec(
        "LLM_MODEL",
        "Model",
        "ai",
        is_secret=False,
        help_text="Defaults to the latest Claude model when blank.",
    ),
    SettingSpec(
        "LLM_COST_PER_MTOK_INPUT",
        "Input cost per million tokens (USD)",
        "ai",
        is_secret=False,
        help_text=(
            "Your contracted rate. Leave blank and reports show exact token counts but no "
            "dollar figure — costs are never guessed."
        ),
    ),
    SettingSpec(
        "LLM_COST_PER_MTOK_OUTPUT",
        "Output cost per million tokens (USD)",
        "ai",
        is_secret=False,
        help_text="Your contracted rate. Leave blank to omit dollar costs from reports.",
    ),
    # --- Image generation ------------------------------------------------------------
    SettingSpec(
        "IMAGE_PROVIDER",
        "Image provider",
        "ai",
        is_secret=False,
        help_text=(
            "Leave as 'none' and the Visual Agent writes image briefs without rendering "
            "them. Set to 'openai' plus a key to generate real images."
        ),
        choices=("none", "openai"),
    ),
    SettingSpec(
        "IMAGE_API_KEY",
        "Image API key",
        "ai",
        help_text="Separate from the LLM key — Claude does not generate images.",
    ),
    SettingSpec(
        "IMAGE_MODEL",
        "Image model",
        "ai",
        is_secret=False,
        help_text="Defaults to gpt-image-1 when blank.",
    ),
    # --- Billing -------------------------------------------------------------------
    SettingSpec("STRIPE_SECRET_KEY", "Secret key", "billing"),
    SettingSpec(
        "STRIPE_WEBHOOK_SECRET",
        "Webhook signing secret",
        "billing",
        help_text="From the Stripe dashboard webhook endpoint (starts with whsec_).",
    ),
    SettingSpec("STRIPE_PRICE_STARTER", "Starter price id", "billing", is_secret=False),
    SettingSpec("STRIPE_PRICE_PRO", "Pro price id", "billing", is_secret=False),
    SettingSpec("STRIPE_PRICE_AGENCY", "Agency price id", "billing", is_secret=False),
    SettingSpec("STRIPE_PRICE_ENTERPRISE", "Enterprise price id", "billing", is_secret=False),
    # --- Social platforms ----------------------------------------------------------
    SettingSpec("X_CLIENT_ID", "X client id", "platforms", is_secret=False),
    SettingSpec("X_CLIENT_SECRET", "X client secret", "platforms"),
    SettingSpec("X_WEBHOOK_SECRET", "X webhook secret", "platforms"),
    SettingSpec("META_APP_ID", "Meta app id", "platforms", is_secret=False),
    SettingSpec("META_APP_SECRET", "Meta app secret", "platforms"),
    SettingSpec("META_WEBHOOK_VERIFY_TOKEN", "Meta webhook verify token", "platforms"),
    SettingSpec("LINKEDIN_CLIENT_ID", "LinkedIn client id", "platforms", is_secret=False),
    SettingSpec("LINKEDIN_CLIENT_SECRET", "LinkedIn client secret", "platforms"),
    SettingSpec("TIKTOK_CLIENT_KEY", "TikTok client key", "platforms", is_secret=False),
    SettingSpec("TIKTOK_CLIENT_SECRET", "TikTok client secret", "platforms"),
    SettingSpec(
        "YOUTUBE_CLIENT_ID",
        "YouTube client id",
        "platforms",
        is_secret=False,
        help_text="Google Cloud OAuth client; covers both YouTube and YouTube Shorts.",
    ),
    SettingSpec("YOUTUBE_CLIENT_SECRET", "YouTube client secret", "platforms"),
    # --- URLs ----------------------------------------------------------------------
    SettingSpec(
        "APP_BASE_URL",
        "Frontend base URL",
        "general",
        is_secret=False,
        help_text="Used to build Stripe Checkout return URLs.",
    ),
    SettingSpec(
        "OAUTH_REDIRECT_BASE",
        "OAuth redirect base",
        "general",
        is_secret=False,
        help_text="Must match the redirect URIs registered with each platform.",
    ),
)

SPECS_BY_KEY = {spec.key: spec for spec in SETTING_SPECS}

_cache: dict[str, str] = {}
_cache_loaded_at = 0.0


def is_editable(key: str) -> bool:
    """True when a key may be written from the admin dashboard."""
    return key in SPECS_BY_KEY


def _load_overrides() -> dict[str, str]:
    """Read and decrypt all DB-stored settings. Never raises — falls back to no overrides."""
    # Imported lazily: this module is also used from contexts where the DB may be absent.
    from src.db.repositories.settings import all_settings
    from src.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            return all_settings(db)
    except Exception as exc:  # noqa: BLE001 - configuration must never break a request path
        logger.error("failed to load settings overrides", extra={"error": str(exc)})
        return {}


def _overrides() -> dict[str, str]:
    global _cache, _cache_loaded_at
    if time.monotonic() - _cache_loaded_at > CACHE_TTL_SECONDS:
        _cache = _load_overrides()
        _cache_loaded_at = time.monotonic()
    return _cache


def get_setting(key: str, default: str = "") -> str:
    """Return the effective value for `key`: DB override, else environment, else default."""
    value = _overrides().get(key)
    if value:
        return value
    return os.environ.get(key, default).strip()


def invalidate_cache() -> None:
    """Force the next `get_setting()` to re-read from the database."""
    global _cache, _cache_loaded_at
    _cache = {}
    _cache_loaded_at = 0.0
