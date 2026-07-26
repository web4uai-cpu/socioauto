"""Curated catalog of AI providers and models, split by the job each one is good at.

The admin dashboard shows one **slot per workload** — analysis, research, writing, voice,
video, image — and each slot offers only the models that are actually strong at that job,
with one marked as the recommended default. That way an operator picks "the best research
model" rather than having to know which model id is current.

This module is pure data plus lookups: no I/O, no SDK imports. Resolution of what a slot is
currently set to lives in `src.llm.resolve`; the clients themselves live in
`src.llm.provider` and `src.media.image_provider`.

Adding a newly released model is a one-line edit here. Operators are never blocked waiting
for that edit: every model field also accepts a custom id (`allow_custom` in
`src.runtime_config`).
"""

from __future__ import annotations

from dataclasses import dataclass

# Slots an admin configures. Order is the order the dashboard renders them in.
ROLES: tuple[str, ...] = ("analysis", "research", "writing", "voice", "video", "image")

# Provider id -> human label, and provider id -> the setting holding its API key.
# One key per provider, shared by every slot pointing at that provider.
PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI",
    "google": "Google",
    "elevenlabs": "ElevenLabs",
    "runway": "Runway",
}
PROVIDER_KEY_SETTINGS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
    "runway": "RUNWAY_API_KEY",
}


@dataclass(frozen=True)
class ModelOption:
    """One selectable model within a provider, for one role."""

    id: str
    label: str
    recommended: bool = False


@dataclass(frozen=True)
class RoleSpec:
    """One workload slot: which providers can serve it, and with which models."""

    role: str
    label: str
    help_text: str
    # False while no client exists for this kind of generation yet. The slot is still saved
    # and handed to the agents, but the dashboard says so plainly instead of implying that
    # picking a model makes it happen.
    connected: bool
    default_provider: str
    providers: dict[str, tuple[ModelOption, ...]]

    def models(self, provider: str) -> tuple[ModelOption, ...]:
        return self.providers.get(provider, ())

    def recommended_model(self, provider: str) -> str:
        """The default model id for `provider`, or "" when the provider does not serve this role."""
        options = self.models(provider)
        for option in options:
            if option.recommended:
                return option.id
        return options[0].id if options else ""


# Frontier text models, repeated per role because the recommendation differs by job.
_CLAUDE_OPUS = ModelOption("claude-opus-5", "Claude Opus 5", recommended=True)
_CLAUDE_SONNET = ModelOption("claude-sonnet-5", "Claude Sonnet 5")
_CLAUDE_FABLE = ModelOption("claude-fable-5", "Claude Fable 5")
_CLAUDE_HAIKU = ModelOption("claude-haiku-4-5-20251001", "Claude Haiku 4.5")
_GPT5 = ModelOption("gpt-5", "GPT-5", recommended=True)
_GEMINI_PRO = ModelOption("gemini-3-pro", "Gemini 3 Pro", recommended=True)


ROLE_SPECS: tuple[RoleSpec, ...] = (
    RoleSpec(
        role="analysis",
        label="Analysis",
        help_text=(
            "Reasoning-heavy work: content strategy planning and SEO analysis. Favour the "
            "strongest reasoning model you have access to."
        ),
        connected=True,
        default_provider="anthropic",
        providers={
            "anthropic": (_CLAUDE_OPUS, _CLAUDE_SONNET),
            "openai": (_GPT5,),
            "google": (_GEMINI_PRO,),
        },
    ),
    RoleSpec(
        role="research",
        label="Research",
        help_text=(
            "Trend discovery and source synthesis, where breadth of world knowledge and "
            "resistance to inventing sources matter most."
        ),
        connected=True,
        default_provider="anthropic",
        providers={
            "anthropic": (_CLAUDE_OPUS, _CLAUDE_SONNET),
            "openai": (_GPT5,),
            "google": (_GEMINI_PRO,),
        },
    ),
    RoleSpec(
        role="writing",
        label="Writing & prompts",
        help_text=(
            "Post copy, engagement replies, brief parsing, and the prompts handed to the "
            "image/voice/video tools. Favour a model with the best prose voice."
        ),
        connected=True,
        default_provider="anthropic",
        providers={
            "anthropic": (_CLAUDE_OPUS, _CLAUDE_FABLE, _CLAUDE_SONNET, _CLAUDE_HAIKU),
            "openai": (_GPT5,),
            "google": (_GEMINI_PRO,),
        },
    ),
    RoleSpec(
        role="voice",
        label="Voice generation",
        help_text=(
            "Narration for video and audio posts. Saved and passed to the Audio Agent, but "
            "no speech is synthesised yet — the agent still emits a voice spec."
        ),
        connected=False,
        default_provider="elevenlabs",
        providers={
            "elevenlabs": (ModelOption("eleven-v3", "Eleven v3", recommended=True),),
            "openai": (ModelOption("gpt-4o-mini-tts", "GPT-4o mini TTS", recommended=True),),
        },
    ),
    RoleSpec(
        role="video",
        label="Video generation",
        help_text=(
            "Short-form video for Reels/Shorts/TikTok. Saved and passed to the Video Agent, "
            "but no footage is rendered yet — the agent still emits a shot spec."
        ),
        connected=False,
        default_provider="google",
        providers={
            "google": (ModelOption("veo-3", "Veo 3", recommended=True),),
            "runway": (ModelOption("gen-4", "Runway Gen-4", recommended=True),),
            "openai": (ModelOption("sora-2", "Sora 2", recommended=True),),
        },
    ),
    RoleSpec(
        role="image",
        label="Image generation",
        help_text=(
            "Rendered stills for the Visual Agent. Leave the provider at 'none' to keep "
            "image briefs only."
        ),
        connected=True,
        default_provider="openai",
        providers={
            "openai": (ModelOption("gpt-image-1", "GPT Image 1", recommended=True),),
        },
    ),
)

ROLE_SPECS_BY_NAME: dict[str, RoleSpec] = {spec.role: spec for spec in ROLE_SPECS}


def role_spec(role: str) -> RoleSpec:
    """Look up a role, raising a clear error for a typo'd slot name."""
    try:
        return ROLE_SPECS_BY_NAME[role]
    except KeyError:  # pragma: no cover - programmer error, not a runtime condition
        raise KeyError(f"unknown AI role {role!r}; expected one of {', '.join(ROLES)}") from None


def provider_setting_key(role: str) -> str:
    """Name of the setting holding the provider chosen for `role`."""
    return f"AI_{role.upper()}_PROVIDER"


def model_setting_key(role: str) -> str:
    """Name of the setting holding the model chosen for `role`."""
    return f"AI_{role.upper()}_MODEL"


def key_setting_for(provider: str) -> str:
    """Name of the setting holding `provider`'s API key ("" for unknown providers)."""
    return PROVIDER_KEY_SETTINGS.get(provider, "")
