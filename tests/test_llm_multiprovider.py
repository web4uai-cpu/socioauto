"""Per-role provider selection: each agent's slot resolves independently.

No network: the vendor SDK classes are replaced with recorders, so these tests assert what
we *would* construct and call rather than hitting an API.
"""

from __future__ import annotations

import pytest

from src.llm import provider as provider_module
from src.llm.provider import (
    AnthropicProvider,
    GoogleProvider,
    NullProvider,
    OpenAIProvider,
    get_provider,
    reset_provider,
)
from src.llm.resolve import resolve_role
from src.runtime_config import invalidate_cache

_AI_KEYS = (
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_API_KEY",
    "IMAGE_PROVIDER",
    "IMAGE_MODEL",
    "IMAGE_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "ELEVENLABS_API_KEY",
    "AI_ANALYSIS_PROVIDER",
    "AI_ANALYSIS_MODEL",
    "AI_RESEARCH_PROVIDER",
    "AI_RESEARCH_MODEL",
    "AI_WRITING_PROVIDER",
    "AI_WRITING_MODEL",
    "AI_VOICE_PROVIDER",
    "AI_IMAGE_PROVIDER",
    "AI_IMAGE_MODEL",
)


@pytest.fixture(autouse=True)
def _isolated_ai_config(monkeypatch):
    """Start every test from a blank AI configuration and an empty client cache."""
    for key in _AI_KEYS:
        monkeypatch.delenv(key, raising=False)
    invalidate_cache()
    reset_provider()
    yield
    invalidate_cache()
    reset_provider()


class _Recorder:
    """Stands in for a vendor client class; records how it was constructed."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, api_key: str, model: str = ""):
        self.calls.append((api_key, model))
        return self

    name = "recorder"


def _use_recorders(monkeypatch) -> dict[str, _Recorder]:
    recorders = {name: _Recorder() for name in ("anthropic", "openai", "google")}
    monkeypatch.setattr(provider_module, "PROVIDER_CLASSES", recorders)
    return recorders


# --- resolution ------------------------------------------------------------------------


def test_unconfigured_slot_resolves_to_the_recommended_model_but_stays_disabled():
    config = resolve_role("research")
    assert config.provider == "anthropic"
    assert config.model == "claude-opus-5"
    assert config.enabled is False  # no key -> deterministic fallbacks


def test_each_slot_resolves_independently(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai")
    monkeypatch.setenv("AI_RESEARCH_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "openai")
    monkeypatch.setenv("AI_ANALYSIS_MODEL", "gpt-5")
    invalidate_cache()

    research = resolve_role("research")
    analysis = resolve_role("analysis")
    assert (research.provider, research.model, research.api_key) == (
        "anthropic",
        "claude-opus-5",
        "sk-ant",
    )
    assert (analysis.provider, analysis.model, analysis.api_key) == ("openai", "gpt-5", "sk-oai")


def test_slot_set_to_none_is_disabled_even_with_a_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    monkeypatch.setenv("AI_WRITING_PROVIDER", "none")
    invalidate_cache()

    config = resolve_role("writing")
    assert config.enabled is False


def test_legacy_single_provider_settings_still_drive_every_slot(monkeypatch):
    """An existing deployment must keep working without touching its configuration."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_API_KEY", "sk-legacy")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
    invalidate_cache()

    for role in ("analysis", "research", "writing"):
        config = resolve_role(role)
        assert (config.provider, config.model, config.api_key) == (
            "anthropic",
            "claude-sonnet-5",
            "sk-legacy",
        )
        assert config.enabled is True


def test_per_slot_settings_win_over_the_legacy_ones(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_API_KEY", "sk-legacy")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("GOOGLE_API_KEY", "sk-goog")
    monkeypatch.setenv("AI_RESEARCH_PROVIDER", "google")
    invalidate_cache()

    config = resolve_role("research")
    assert (config.provider, config.model, config.api_key) == ("google", "gemini-3-pro", "sk-goog")


def test_image_slot_honours_the_older_image_settings(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("IMAGE_API_KEY", "sk-img")
    invalidate_cache()

    config = resolve_role("image")
    assert (config.provider, config.model, config.api_key) == ("openai", "gpt-image-1", "sk-img")
    assert config.enabled is True


# --- client construction ---------------------------------------------------------------


def test_two_slots_can_run_on_two_different_vendors(monkeypatch):
    recorders = _use_recorders(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    monkeypatch.setenv("GOOGLE_API_KEY", "sk-goog")
    monkeypatch.setenv("AI_RESEARCH_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_WRITING_PROVIDER", "google")
    monkeypatch.setenv("AI_WRITING_MODEL", "gemini-3-pro")
    invalidate_cache()

    get_provider("research")
    get_provider("writing")

    assert recorders["anthropic"].calls == [("sk-ant", "claude-opus-5")]
    assert recorders["google"].calls == [("sk-goog", "gemini-3-pro")]


def test_provider_is_cached_per_role(monkeypatch):
    recorders = _use_recorders(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    invalidate_cache()

    first = get_provider("writing")
    second = get_provider("writing")
    assert first is second
    assert len(recorders["anthropic"].calls) == 1

    reset_provider()
    get_provider("writing")
    assert len(recorders["anthropic"].calls) == 2


def test_no_argument_call_uses_the_writing_slot(monkeypatch):
    recorders = _use_recorders(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai")
    monkeypatch.setenv("AI_WRITING_PROVIDER", "openai")
    invalidate_cache()

    get_provider()
    assert recorders["openai"].calls == [("sk-oai", "gpt-5")]


def test_slot_without_a_key_degrades_to_null_without_touching_the_others(monkeypatch):
    """One misconfigured slot must never break a campaign."""
    recorders = _use_recorders(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "openai")  # no OPENAI_API_KEY set
    monkeypatch.setenv("AI_RESEARCH_PROVIDER", "anthropic")
    invalidate_cache()

    assert isinstance(get_provider("analysis"), NullProvider)
    assert get_provider("research") is recorders["anthropic"]


def test_voice_and_video_slots_have_no_text_client_yet(monkeypatch):
    """Configured but not generating — the slot must degrade, not raise."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-11")
    monkeypatch.setenv("AI_VOICE_PROVIDER", "elevenlabs")
    invalidate_cache()

    assert isinstance(get_provider("voice"), NullProvider)


def test_a_broken_client_constructor_degrades_to_null(monkeypatch):
    """A missing SDK or bad key must not crash boot."""

    def explode(api_key: str, model: str = ""):
        raise RuntimeError("package not installed")

    monkeypatch.setattr(provider_module, "PROVIDER_CLASSES", {"anthropic": explode})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    invalidate_cache()

    assert isinstance(get_provider("writing"), NullProvider)


def test_every_real_client_satisfies_the_agent_contract():
    for cls in (AnthropicProvider, OpenAIProvider, GoogleProvider, NullProvider):
        assert callable(cls.complete)
        assert callable(cls.complete_json)
