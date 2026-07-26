"""Pluggable image-generation provider used by the Visual Agent.

Mirrors `src/llm/provider.py`: selection comes from the dashboard's **image slot**
(`AI_IMAGE_PROVIDER` / `AI_IMAGE_MODEL` plus that provider's key), resolved through the
shared `src.llm.resolve.resolve_role`, which also honours the older `IMAGE_*` settings.
With nothing configured this returns a `NullImageProvider` and the Visual Agent
keeps emitting specs only — the pipeline stays runnable, and every test stays green, without
live credentials.

Implementations must never raise: a generation failure returns None so the campaign continues
with the spec rather than dying on an image.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from src.llm.resolve import resolve_role
from src.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_OPENAI_MODEL = "gpt-image-1"

# Aspect ratios the Visual Agent emits, mapped to the sizes OpenAI's image API accepts.
# Anything unrecognised falls back to a square.
_OPENAI_SIZES: dict[str, str] = {
    "1:1": "1024x1024",
    "4:5": "1024x1536",  # portrait
    "9:16": "1024x1536",  # portrait (closest supported)
    "16:9": "1536x1024",  # landscape
    "1.91:1": "1536x1024",  # landscape
}
DEFAULT_OPENAI_SIZE = "1024x1024"


@dataclass
class GeneratedImage:
    """One rendered image, as raw bytes plus the content type to store it under."""

    data: bytes
    content_type: str


class ImageProvider(Protocol):
    """Minimal surface the Visual Agent depends on. Implementations must never raise."""

    name: str

    def generate(self, prompt: str, *, aspect_ratio: str = "1:1") -> GeneratedImage | None:
        """Render an image, or return None when generation is unavailable."""


class NullImageProvider:
    """No-op provider used when no image API is configured. Visual Agent stays spec-only."""

    name = "null"

    def generate(self, prompt: str, *, aspect_ratio: str = "1:1") -> None:
        return None


class OpenAIImageProvider:
    """OpenAI image API (`gpt-image-1`).

    Chosen for prompt adherence and because it renders legible text inside images, which
    matters for the overlay text the Visual Agent specifies.
    """

    name = "openai"

    def __init__(self, api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> None:
        import openai  # imported lazily so the package stays optional at runtime

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def generate(self, prompt: str, *, aspect_ratio: str = "1:1") -> GeneratedImage | None:
        size = _OPENAI_SIZES.get(aspect_ratio, DEFAULT_OPENAI_SIZE)
        try:
            response = self._client.images.generate(
                model=self._model, prompt=prompt, size=size, n=1
            )
            payload: Any = response.data[0]
            if getattr(payload, "b64_json", None):
                return GeneratedImage(
                    data=base64.b64decode(payload.b64_json), content_type="image/png"
                )
            logger.error("image response carried no data", extra={"model": self._model})
            return None
        except Exception as exc:  # noqa: BLE001 - never let generation break the pipeline
            logger.error("image generation failed", extra={"error": str(exc)})
            return None


@lru_cache(maxsize=1)
def get_image_provider() -> ImageProvider:
    """Return the client configured for the image slot, or a NullImageProvider.

    Cached so one client is reused across items; call `reset_image_provider()` after changing
    configuration (the settings route does this on every save).
    """
    config = resolve_role("image")

    if not config.enabled:
        logger.info("no image provider configured; visuals stay spec-only")
        return NullImageProvider()

    if config.provider == "openai":
        try:
            return OpenAIImageProvider(config.api_key, model=config.model or DEFAULT_OPENAI_MODEL)
        except Exception as exc:  # noqa: BLE001 - missing package or bad key must not crash
            logger.error("failed to initialize image provider", extra={"error": str(exc)})
            return NullImageProvider()

    logger.warning(
        "no client for image provider; staying spec-only", extra={"provider": config.provider}
    )
    return NullImageProvider()


def reset_image_provider() -> None:
    """Clear the cached provider so the next call re-reads configuration."""
    get_image_provider.cache_clear()
