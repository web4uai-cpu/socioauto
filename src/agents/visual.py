"""Visual Agent: writes an image/thumbnail brief and renders it when a provider is configured.

The brief (generation prompt, alt text, aspect ratio, overlay text) is always produced. If an
image provider is set up (`IMAGE_PROVIDER` + `IMAGE_API_KEY`), the brief is rendered and the
file is appended to `item.media` with `visual["status"] == "generated"`; otherwise the item
keeps `status == "spec"` and the pipeline continues unchanged.
"""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.logging_config import get_logger
from src.media.image_provider import get_image_provider
from src.orchestrator.state import VISUAL_KINDS, CampaignState, ContentItem, PostKind
from src.storage import MediaValidationError, media_storage

logger = get_logger(__name__)

# What the image is *for*, which differs by post kind — a feed image, a video thumbnail, or
# cover art for an audio-only post.
VISUAL_PURPOSE: dict[PostKind, str] = {
    PostKind.IMAGE: "feed image",
    PostKind.VIDEO: "video thumbnail",
    PostKind.FACELESS_VIDEO: "video thumbnail",
    PostKind.AUDIO: "audio cover art",
}

# Native aspect ratio each platform renders a feed image at, and the pixel size to request.
PLATFORM_VISUAL_SPEC: dict[str, tuple[str, str]] = {
    "instagram": ("4:5", "1080x1350"),
    "tiktok": ("9:16", "1080x1920"),
    "x": ("16:9", "1200x675"),
    "linkedin": ("1.91:1", "1200x627"),
    "facebook": ("1.91:1", "1200x630"),
}
DEFAULT_SPEC = ("1:1", "1080x1080")

VISUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string"},
        "alt_text": {"type": "string"},
        "overlay_text": {"type": "string"},
        "style": {"type": "string"},
    },
    "required": ["prompt", "alt_text", "overlay_text", "style"],
    "additionalProperties": False,
}

SYSTEM = (
    "You write image-generation briefs for brand social posts. Describe only the visual: "
    "subject, composition, lighting, and style. Never depict real identifiable people, "
    "logos you were not given, or text claims. Keep overlay text under 8 words. Alt text "
    "must describe the image factually for a screen-reader user."
)


class VisualAgent(BaseAgent):
    """Attach an image/thumbnail generation spec to every content item."""

    name = "visual"

    def run(self, state: CampaignState) -> CampaignState:
        """Populate `item.visual` for each calendar item.

        Args:
            state: Campaign state with a drafted calendar.

        Returns:
            The same state with visual specs attached.
        """
        provider = get_provider()
        images = get_image_provider()
        specced = 0
        rendered = 0
        for item in state.calendar:
            # A text-only post has no visual; an item may also carry a spec from upstream.
            if item.visual or item.kind not in VISUAL_KINDS:
                continue
            ratio, size = PLATFORM_VISUAL_SPEC.get(item.platform, DEFAULT_SPEC)
            spec = self._brief_with_llm(provider, state, item) or self._fallback(item)
            spec["aspect_ratio"] = ratio
            spec["size"] = size
            spec["purpose"] = VISUAL_PURPOSE[item.kind]
            spec["status"] = "spec"
            item.visual = spec
            specced += 1
            if self._render(images, item):
                rendered += 1

        note = f"[{self.name}] specced visuals for {specced} items"
        state.note(f"{note} ({rendered} rendered)" if rendered else note)
        return state

    def _render(self, images, item: ContentItem) -> bool:
        """Generate the actual image when a provider is configured.

        Failure is non-fatal: the item keeps its spec and the campaign continues, because an
        unavailable image API must not cost the user their copy.
        """
        generated = images.generate(item.visual["prompt"], aspect_ratio=item.visual["aspect_ratio"])
        if generated is None:
            return False
        try:
            record = media_storage.save(
                filename=f"{item.platform}-visual.png",
                content_type=generated.content_type,
                data=generated.data,
            )
        except MediaValidationError as exc:
            logger.warning("generated image rejected by storage", extra={"error": str(exc)})
            return False
        item.media.append(
            {
                "id": record.id,
                "url": record.url,
                "content_type": record.content_type,
                "kind": record.kind,
            }
        )
        item.visual["status"] = "generated"
        item.visual["media_id"] = record.id
        return True

    def _brief_with_llm(self, provider, state: CampaignState, item: ContentItem) -> dict | None:
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Brand voice: {state.voice_guidelines or 'professional and friendly'}\n"
            f"Platform: {item.platform}\n"
            f"Image purpose: {VISUAL_PURPOSE[item.kind]}\n"
            f"Post topic: {item.topic}\n"
            f"Post body: {item.body}\n"
            f"Existing media brief: {item.media_brief or 'none'}\n\n"
            "Write the image generation brief for this post."
        )
        result = provider.complete_json(prompt, VISUAL_SCHEMA, system=SYSTEM)
        if not result or not result.get("prompt"):
            return None
        result["source"] = provider.name
        return result

    def _fallback(self, item: ContentItem) -> dict:
        """Deterministic spec derived from the copy, used when no LLM is configured."""
        subject = item.media_brief or item.topic
        return {
            "prompt": (
                f"Clean, modern brand social image for {item.platform}. Subject: {subject}. "
                "Bright even lighting, generous negative space for text overlay, no text."
            ),
            "alt_text": f"Illustration representing {subject}",
            "overlay_text": "",
            "style": "modern brand photography",
            "source": "fallback",
        }
