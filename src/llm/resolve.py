"""Resolve what provider, model and key a given AI slot is currently configured with.

One place owns the fallback chain so the text clients (`src.llm.provider`) and the image
client (`src.media.image_provider`) cannot drift apart:

    provider = AI_<ROLE>_PROVIDER  or  LLM_PROVIDER   or  the catalog's default provider
    model    = AI_<ROLE>_MODEL     or  LLM_MODEL      or  the catalog's recommended model
    api_key  = <PROVIDER>_API_KEY  or  LLM_API_KEY    (legacy single-key installs)

The `LLM_*` rungs exist purely for backward compatibility: a deployment that configured the
old single-provider board keeps working after this upgrade without touching its settings.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.llm.catalog import (
    key_setting_for,
    model_setting_key,
    provider_setting_key,
    role_spec,
)
from src.runtime_config import get_setting

# Values that mean "deliberately switched off", not "unset".
_DISABLED = ("none", "null", "off")


@dataclass(frozen=True)
class RoleConfig:
    """The effective configuration of one workload slot."""

    role: str
    provider: str
    model: str
    api_key: str

    @property
    def enabled(self) -> bool:
        """True when this slot has both a live provider and a key to call it with."""
        return bool(self.provider and self.provider not in _DISABLED and self.api_key)


def _legacy_image_key(provider: str) -> str:
    """The old board kept a separate image key; honour it for the image slot."""
    return get_setting("IMAGE_API_KEY") if provider == "openai" else ""


def resolve_role(role: str) -> RoleConfig:
    """Resolve `role` to its effective provider/model/key. Never raises for unset values."""
    spec = role_spec(role)

    # The image slot's legacy settings are the IMAGE_* pair; every other slot falls back to
    # the single LLM_* set the old board wrote.
    legacy_provider_key = "IMAGE_PROVIDER" if role == "image" else "LLM_PROVIDER"
    legacy_model_key = "IMAGE_MODEL" if role == "image" else "LLM_MODEL"
    legacy_provider = get_setting(legacy_provider_key).strip().lower()

    provider = get_setting(provider_setting_key(role)).strip().lower()
    if not provider:
        provider = legacy_provider
    if not provider:
        provider = spec.default_provider

    if provider in _DISABLED:
        return RoleConfig(role=role, provider="none", model="", api_key="")

    model = get_setting(model_setting_key(role)).strip()
    if not model and provider == (legacy_provider or spec.default_provider):
        # Only inherit the legacy model when the slot still points at the vendor that model
        # belongs to — otherwise a Claude id would be sent to Gemini.
        model = get_setting(legacy_model_key).strip()
    if not model:
        model = spec.recommended_model(provider)

    key_setting = key_setting_for(provider)
    api_key = get_setting(key_setting) if key_setting else ""
    if not api_key:
        api_key = _legacy_image_key(provider) if role == "image" else get_setting("LLM_API_KEY")

    return RoleConfig(role=role, provider=provider, model=model, api_key=api_key)
