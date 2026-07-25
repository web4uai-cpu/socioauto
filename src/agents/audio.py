"""Audio Agent: writes voiceover scripts and voice specs for audio-bearing posts.

Runs for `audio`, `video`, and `faceless_video` kinds. For the video kinds it reuses the
narration the Video Agent already wrote, so the voiceover matches the script rather than
drifting from it; for an audio-only post it derives a standalone script from the copy.

Like the Visual and Video agents this produces a *spec*, not a sound file — no TTS provider is
wired up yet. When one is added it consumes `audio["script"]` plus `audio["voice"]` and appends
the rendered file to `item.media`, leaving this agent's contract unchanged.
"""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.llm.provider import get_provider
from src.orchestrator.state import AUDIO_KINDS, CampaignState, ContentItem, PostKind

# Average narration pace. Used to estimate runtime from the script's word count.
WORDS_PER_MINUTE = 150
# Podcast-style clips run longer than a social voiceover.
AUDIO_ONLY_TARGET_SECONDS = 60

AUDIO_SCHEMA = {
    "type": "object",
    "properties": {
        "script": {"type": "string"},
        "voice_style": {"type": "string"},
        "pace": {"type": "string", "enum": ["slow", "conversational", "energetic"]},
        "music_bed": {"type": "string"},
        "hook_line": {"type": "string"},
    },
    "required": ["script", "voice_style", "pace", "music_bed", "hook_line"],
    "additionalProperties": False,
}

SYSTEM = (
    "You write voiceover scripts for brand audio. Write for the ear, not the page: short "
    "sentences, natural spoken rhythm, no bullet points or emoji. Open with a line that earns "
    "the next few seconds. Never invent statistics, testimonials, or claims about real people. "
    "Describe the music bed generically — never name a copyrighted track or artist."
)

_PACE_LABEL = "conversational"


def estimate_seconds(script: str) -> int:
    """Estimate spoken runtime in whole seconds from a script's word count."""
    words = len(script.split())
    return max(1, round(words / WORDS_PER_MINUTE * 60))


class AudioAgent(BaseAgent):
    """Attach a voiceover script + voice spec to every audio-bearing content item."""

    name = "audio"

    def run(self, state: CampaignState) -> CampaignState:
        """Populate `item.audio` for items whose kind carries audio.

        Args:
            state: Campaign state with drafted content (and video scripts, if any).

        Returns:
            The same state with audio specs attached where applicable.
        """
        provider = get_provider()
        produced = 0
        for item in state.calendar:
            if item.audio or item.kind not in AUDIO_KINDS:
                continue
            spec = self._write_with_llm(provider, state, item) or self._fallback(item)

            script = spec.get("script", "")
            spec["audio_type"] = "podcast_clip" if item.kind == PostKind.AUDIO else "voiceover"
            spec["estimated_seconds"] = estimate_seconds(script)
            # The script doubles as the caption transcript, which several platforms require
            # for audio/video accessibility.
            spec["transcript"] = script
            spec["status"] = "spec"  # becomes "rendered" once a TTS provider runs it
            item.audio = spec
            produced += 1

        state.note(f"[{self.name}] produced audio for {produced} items")
        return state

    def _narration_from_video(self, item: ContentItem) -> str:
        """Stitch the Video Agent's per-scene narration into one continuous script."""
        scenes = item.video.get("scenes") or []
        lines = [str(scene.get("narration", "")).strip() for scene in scenes]
        return " ".join(line for line in lines if line)

    def _write_with_llm(self, provider, state: CampaignState, item: ContentItem) -> dict | None:
        existing = self._narration_from_video(item)
        if existing:
            instruction = (
                "Turn this video narration into a clean voiceover script. Keep the meaning and "
                f"roughly the same length.\n\nNarration: {existing}"
            )
        else:
            target = AUDIO_ONLY_TARGET_SECONDS
            instruction = (
                f"Write a standalone audio script of about {target} seconds "
                f"({round(target / 60 * WORDS_PER_MINUTE)} words) on this topic."
            )
        prompt = (
            f"Brand: {state.brand_name}\n"
            f"Brand voice: {state.voice_guidelines or 'professional and friendly'}\n"
            f"Platform: {item.platform}\n"
            f"Post kind: {item.kind.value}\n"
            f"Topic: {item.topic}\n"
            f"Companion caption: {item.body}\n\n"
            f"{instruction}"
        )
        result = provider.complete_json(prompt, AUDIO_SCHEMA, system=SYSTEM)
        if not result or not result.get("script"):
            return None
        result["voice"] = {
            "style": result.pop("voice_style", "warm and clear"),
            "pace": result.pop("pace", _PACE_LABEL),
            "words_per_minute": WORDS_PER_MINUTE,
        }
        result["source"] = provider.name
        return result

    def _fallback(self, item: ContentItem) -> dict:
        """Deterministic script, used when no LLM is configured.

        Prefers the video narration so the voiceover stays in sync with the scenes.
        """
        script = self._narration_from_video(item) or " ".join(
            part for part in (item.topic, item.body, item.cta) if part
        )
        return {
            "script": script,
            "hook_line": item.topic,
            "voice": {
                "style": "warm and clear",
                "pace": _PACE_LABEL,
                "words_per_minute": WORDS_PER_MINUTE,
            },
            "music_bed": "soft neutral background bed, low volume under the voice",
            "source": "fallback",
        }
