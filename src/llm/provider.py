"""Pluggable LLM provider used by every agent that generates text.

Selection is driven by `LLM_PROVIDER` / `LLM_API_KEY`, resolved through
`src.runtime_config` so keys entered in the admin dashboard win over the environment.
When no provider is configured the module returns a `NullProvider`, so the whole pipeline
stays runnable — and every test stays green — without live credentials. Agents treat a
`None` result as "fall back to the deterministic draft" rather than failing the campaign.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Protocol

from src.llm.usage import record
from src.logging_config import get_logger
from src.runtime_config import get_setting

logger = get_logger(__name__)

# Latest and most capable Claude model; adaptive thinking is on by default on this model,
# so max_tokens must leave headroom for thinking *and* the response text.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
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


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    """Return the configured provider, or a NullProvider when no LLM is set up.

    Cached so a single client is reused across agents; call `reset_provider()` after
    changing the environment (tests do this).
    """
    provider = get_setting("LLM_PROVIDER").lower()
    api_key = get_setting("LLM_API_KEY")
    model = get_setting("LLM_MODEL") or DEFAULT_ANTHROPIC_MODEL

    if not api_key or provider in ("", "none", "null"):
        logger.info("no LLM configured; agents will use deterministic fallbacks")
        return NullProvider()

    if provider == "anthropic":
        try:
            return AnthropicProvider(api_key, model=model)
        except Exception as exc:  # noqa: BLE001 - missing package or bad key must not crash boot
            logger.error("failed to initialize anthropic provider", extra={"error": str(exc)})
            return NullProvider()

    logger.warning(
        "unsupported LLM_PROVIDER; using deterministic fallbacks", extra={"provider": provider}
    )
    return NullProvider()


def reset_provider() -> None:
    """Clear the cached provider so the next `get_provider()` re-reads the environment."""
    get_provider.cache_clear()
