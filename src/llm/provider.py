"""Pluggable LLM providers, selected per workload rather than once per process.

Each agent asks for the slot matching its job — `get_provider("research")`,
`get_provider("analysis")`, `get_provider("writing")` — and the admin dashboard decides
which provider and model serves that slot (see `src.llm.catalog` and `src.llm.resolve`).
Two agents can therefore run on two different vendors in the same campaign.

When a slot has no provider or no key the module returns a `NullProvider`, so the whole
pipeline stays runnable — and every test stays green — without live credentials. Agents
treat a `None` result as "fall back to the deterministic draft" rather than failing the
campaign, and every implementation here upholds that by never raising.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Protocol

from src.llm.catalog import ROLES
from src.llm.resolve import resolve_role
from src.llm.usage import record
from src.logging_config import get_logger

logger = get_logger(__name__)

# The slot used when an agent does not name one — general copywriting.
DEFAULT_ROLE = "writing"

# Per-vendor defaults, used only when a provider is constructed directly. Normal selection
# goes through `src.llm.catalog`, which is the single source of truth for model ids.
# Latest and most capable Claude model; adaptive thinking is on by default on this model,
# so max_tokens must leave headroom for thinking *and* the response text.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "gpt-5"
DEFAULT_GOOGLE_MODEL = "gemini-3-pro"
DEFAULT_MAX_TOKENS = 4096
# Short marketing copy does not need deep reasoning. Lowering effort (rather than disabling
# thinking) is the recommended cost/latency lever on this model family.
DEFAULT_EFFORT = "low"


class LLMProvider(Protocol):
    """Minimal surface the agents depend on. Implementations must never raise."""

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = ...) -> str | None:
        """Return generated text, or None if generation is unavailable."""

    def complete_json(
        self, prompt: str, schema: dict[str, Any], *, system: str = "", max_tokens: int = ...
    ) -> Any | None:
        """Return a value matching `schema`, or None if generation is unavailable."""


class NullProvider:
    """No-op provider used when no LLM is configured. Agents fall back to rule-based output."""

    name = "null"

    def complete(
        self, prompt: str, *, system: str = "", max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> None:
        return None

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system: str = "",
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        return None


class AnthropicProvider:
    """Claude-backed provider.

    Every call is wrapped so an API failure degrades to the deterministic path instead of
    failing the campaign: on error (including a safety refusal) the method returns None.
    """

    name = "anthropic"

    def __init__(self, api_key: str, model: str = DEFAULT_ANTHROPIC_MODEL) -> None:
        import anthropic  # imported lazily so the package is optional at runtime

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def _create(self, **kwargs: Any) -> Any:
        # Server-side fallback re-runs a safety-declined request on another model in the
        # same call, so a false-positive refusal doesn't drop the content item.
        return self._client.beta.messages.create(
            model=self._model,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            **kwargs,
        )

    def _text(self, response: Any) -> str | None:
        self._record_usage(response)
        if response.stop_reason == "refusal":
            logger.warning("llm refused request", extra={"model": self._model})
            return None
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
        return None

    def _record_usage(self, response: Any) -> None:
        """Book this call's tokens against the active accounting scope.

        A refused or malformed response still consumed input tokens, so usage is recorded
        before the response is interpreted. Never raises — accounting must not break a
        campaign.
        """
        try:
            usage = getattr(response, "usage", None)
            if usage is None:
                return
            record(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                model=self._model,
            )
        except Exception as exc:  # noqa: BLE001 - accounting is never fatal
            logger.warning("usage accounting failed", extra={"error": str(exc)})

    def complete(
        self, prompt: str, *, system: str = "", max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str | None:
        try:
            response = self._create(
                max_tokens=max_tokens,
                system=system or self._anthropic.NOT_GIVEN,
                output_config={"effort": DEFAULT_EFFORT},
                messages=[{"role": "user", "content": prompt}],
            )
            return self._text(response)
        except Exception as exc:  # noqa: BLE001 - never let generation break the pipeline
            logger.error("llm completion failed", extra={"error": str(exc)})
            return None

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system: str = "",
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Any | None:
        try:
            response = self._create(
                max_tokens=max_tokens,
                system=system or self._anthropic.NOT_GIVEN,
                output_config={
                    "effort": DEFAULT_EFFORT,
                    "format": {"type": "json_schema", "schema": schema},
                },
                messages=[{"role": "user", "content": prompt}],
            )
            text = self._text(response)
            return json.loads(text) if text else None
        except Exception as exc:  # noqa: BLE001 - never let generation break the pipeline
            logger.error("llm json completion failed", extra={"error": str(exc)})
            return None


class OpenAIProvider:
    """OpenAI-backed provider, via the Responses API.

    Same contract as `AnthropicProvider`: any failure returns None so the agent falls back
    to its deterministic draft instead of failing the campaign.
    """

    name = "openai"

    def __init__(self, api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> None:
        import openai  # imported lazily so the package stays optional at runtime

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def _create(self, prompt: str, system: str, max_tokens: int, **kwargs: Any) -> Any:
        return self._client.responses.create(
            model=self._model,
            instructions=system or None,
            input=prompt,
            max_output_tokens=max_tokens,
            **kwargs,
        )

    def _text(self, response: Any) -> str | None:
        self._record_usage(response)
        text = getattr(response, "output_text", "") or ""
        return text.strip() or None

    def _record_usage(self, response: Any) -> None:
        """Book this call's tokens. Never raises — accounting must not break a campaign."""
        try:
            usage = getattr(response, "usage", None)
            if usage is None:
                return
            record(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                model=self._model,
            )
        except Exception as exc:  # noqa: BLE001 - accounting is never fatal
            logger.warning("usage accounting failed", extra={"error": str(exc)})

    def complete(
        self, prompt: str, *, system: str = "", max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str | None:
        try:
            return self._text(self._create(prompt, system, max_tokens))
        except Exception as exc:  # noqa: BLE001 - never let generation break the pipeline
            logger.error("llm completion failed", extra={"error": str(exc), "model": self._model})
            return None

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system: str = "",
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Any | None:
        try:
            response = self._create(
                prompt,
                system,
                max_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "result",
                        "schema": schema,
                        "strict": False,
                    }
                },
            )
            text = self._text(response)
            return json.loads(text) if text else None
        except Exception as exc:  # noqa: BLE001 - never let generation break the pipeline
            logger.error(
                "llm json completion failed", extra={"error": str(exc), "model": self._model}
            )
            return None


class GoogleProvider:
    """Gemini-backed provider, via the google-genai SDK.

    Same never-raise contract as the other implementations.
    """

    name = "google"

    def __init__(self, api_key: str, model: str = DEFAULT_GOOGLE_MODEL) -> None:
        from google import genai  # imported lazily so the package stays optional at runtime

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def _create(self, prompt: str, config: dict[str, Any]) -> Any:
        return self._client.models.generate_content(
            model=self._model, contents=prompt, config=config
        )

    def _config(self, system: str, max_tokens: int) -> dict[str, Any]:
        config: dict[str, Any] = {"max_output_tokens": max_tokens}
        if system:
            config["system_instruction"] = system
        return config

    def _text(self, response: Any) -> str | None:
        self._record_usage(response)
        text = getattr(response, "text", "") or ""
        return text.strip() or None

    def _record_usage(self, response: Any) -> None:
        """Book this call's tokens. Never raises — accounting must not break a campaign."""
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage is None:
                return
            record(
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                model=self._model,
            )
        except Exception as exc:  # noqa: BLE001 - accounting is never fatal
            logger.warning("usage accounting failed", extra={"error": str(exc)})

    def complete(
        self, prompt: str, *, system: str = "", max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str | None:
        try:
            return self._text(self._create(prompt, self._config(system, max_tokens)))
        except Exception as exc:  # noqa: BLE001 - never let generation break the pipeline
            logger.error("llm completion failed", extra={"error": str(exc), "model": self._model})
            return None

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system: str = "",
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Any | None:
        try:
            config = self._config(system, max_tokens)
            config["response_mime_type"] = "application/json"
            config["response_schema"] = schema
            text = self._text(self._create(prompt, config))
            return json.loads(text) if text else None
        except Exception as exc:  # noqa: BLE001 - never let generation break the pipeline
            logger.error(
                "llm json completion failed", extra={"error": str(exc), "model": self._model}
            )
            return None


# Registering a new text provider is one entry here plus one in `src.llm.catalog`.
PROVIDER_CLASSES: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,
}


@lru_cache(maxsize=len(ROLES) + 1)
def get_provider(role: str = DEFAULT_ROLE) -> LLMProvider:
    """Return the client configured for `role`, or a NullProvider when it is not usable.

    Cached per role so one client is reused across agents; call `reset_provider()` after
    changing configuration (the settings route does this on every save, and tests do it
    between cases).

    A slot pointing at a provider with no text client — voice and video, which are config
    only for now — degrades to a NullProvider like any other unconfigured slot, so one
    misconfigured slot can never break a campaign.
    """
    config = resolve_role(role)

    if not config.enabled:
        logger.info(
            "no LLM configured for role; using deterministic fallbacks",
            extra={"role": role, "provider": config.provider},
        )
        return NullProvider()

    provider_class = PROVIDER_CLASSES.get(config.provider)
    if provider_class is None:
        logger.warning(
            "no text client for provider; using deterministic fallbacks",
            extra={"role": role, "provider": config.provider},
        )
        return NullProvider()

    try:
        return provider_class(config.api_key, model=config.model)
    except Exception as exc:  # noqa: BLE001 - missing package or bad key must not crash boot
        logger.error(
            "failed to initialize provider",
            extra={"role": role, "provider": config.provider, "error": str(exc)},
        )
        return NullProvider()


def reset_provider() -> None:
    """Clear every cached client so the next `get_provider()` re-reads configuration."""
    get_provider.cache_clear()
