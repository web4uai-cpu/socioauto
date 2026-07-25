"""Video Agent: writes short-form video scripts and thumbnail prompts.

Only runs for platforms where video is a native format. Like the Visual Agent it produces a
script and a thumbnail *spec* rather than rendering a file; a future render step consumes
`item.video["script"]` and `thumbnail_prompt` and appends the output to `item.media`.
"""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import VIDEO_KINDS, CampaignState, ContentItem, PostKind

# Target runtime in seconds per platform's native short-form surface.
VIDEO_PLATFORMS: dict[str, int] = {
    "tiktok": 30,
    "instagram": 30,  # Reels
    "facebook": 45,
    "x": 45,
}
# Used when the caller asks for video on a platform without a tuned short-form runtime
# (LinkedIn, say) — an explicit request is honoured rather than silently dropped.
DEFAULT_TARGET_SECONDS = 45

VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "hook": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "visual": {"type": "string"},
                    "seconds": {"type": "number"},
                },
                "required": ["narration", "visual", "seconds"],
                "additionalProperties": False,
            },
        },
        "call_to_action": {"type": "string"},
        "thumbnail_prompt": {"type": "string"},
        "thumbnail_text": {"type": "string"},
    },
    "required": ["hook", "scenes", "call_to_action", "thumbnail_prompt", "thumbnail_text"],
    "additionalProperties": False,
}

SYSTEM = (
    "You write short-form video scripts for brand social accounts. The first line must be a "
    "hook that earns the next three seconds. Keep narration spoken-word natural. Never invent "
    "statistics, testimonials, or claims about real people. Thumbnail text must be under 5 words."
)


class VideoAgent(BaseAgent):
    """Attach a video script + thumbnail spec to items on video-capable platforms."""

    name = "video"

    def run(self, state: CampaignState) -> CampaignState:
        """Populate `item.video` for each video-capable calendar item.

        Args:
            state: Campaign state with a drafted calendar.

        Returns:
            The same state with video scripts attached where applicable.
        """
        provider = get_provider()
        scripted = 0
        for item in state.calendar:
            # Kind decides this, not platform: the user asked for a video, so honour it even
            # on a platform we would not have defaulted to video for.
            if item.video or item.kind not in VIDEO_KINDS:
                continue
            target = VIDEO_PLATFORMS.get(item.platform, DEFAULT_TARGET_SECONDS)
            faceless = item.kind == PostKind.FACELESS_VIDEO
            script = self._script_with_llm(
                provider, state, item, target, faceless
            ) or self._fallback(item, target, faceless)
            script["target_seconds"] = target
            script["faceless"] = faceless
            script["status"] = "script"  # becomes "rendered" once a video pipeline runs it
            item.video = script
            scripted += 1
        state.note(f"[{self.name}] scripted {scripted} video items")
        return state

    def _script_with_llm(
        self, provider, state: CampaignState, item: ContentItem, target: int, faceless: bool
    ) -> dict | None:
        style = (
            "This is a FACELESS video: no on-camera presenter and no talking-head shots. "
            "Every scene visual must be b-roll, screen recording, motion graphics, or stock "
            "footage carried by voiceover."
            if faceless
            else "A presenter may appear on camera."
        )
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Brand voice: {state.voice_guidelines or 'professional and friendly'}\n"
            f"Platform: {item.platform} (short-form video)\n"
            f"Target runtime: about {target} seconds\n"
            f"Topic: {item.topic}\n"
            f"Companion caption: {item.body}\n\n"
            f"{style}\n\n"
            "Write the video script as 3-5 scenes whose seconds sum to roughly the target "
            "runtime, plus a thumbnail prompt."
        )
        result = provider.complete_json(prompt, VIDEO_SCHEMA, system=SYSTEM)
        if not result or not result.get("scenes"):
            return None
        result["source"] = provider.name
        return result

    def _fallback(self, item: ContentItem, target: int, faceless: bool) -> dict:
        """Deterministic three-beat script, used when no LLM is configured."""
        third = round(target / 3)
        opening_visual = (
            "Motion-graphic title card over b-roll"
            if faceless
            else "Talking head, direct to camera"
        )
        return {
            "hook": f"Here's what changed: {item.topic}",
            "scenes": [
                {
                    "narration": f"Here's what changed: {item.topic}",
                    "visual": opening_visual,
                    "seconds": third,
                },
                {
                    "narration": item.body or item.topic,
                    "visual": "Screen recording or product B-roll",
                    "seconds": third,
                },
                {
                    "narration": item.cta or "Follow for more.",
                    "visual": "Brand end card",
                    "seconds": target - 2 * third,
                },
            ],
            "call_to_action": item.cta or "Follow for more.",
            "thumbnail_prompt": (
                f"Bold short-form video thumbnail about {item.topic}. High contrast, "
                "expressive subject, space for a short text overlay."
            ),
            "thumbnail_text": "",
            "source": "fallback",
        }
