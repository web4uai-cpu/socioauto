"""Image provider selection and the Visual Agent's rendering path."""

import pytest

from src.agents.visual import VisualAgent
from src.media import image_provider
from src.media.image_provider import (
    GeneratedImage,
    NullImageProvider,
    OpenAIImageProvider,
    get_image_provider,
    reset_image_provider,
)
from src.orchestrator.state import CampaignState, ContentItem, PostKind

# A one-pixel PNG, so the storage layer gets real bytes with a real content type.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001"
)


@pytest.fixture(autouse=True)
def _clean_provider_cache():
    reset_image_provider()
    yield
    reset_image_provider()


class _StubImages:
    """Stands in for a configured provider."""

    name = "stub"

    def __init__(self, result=None):
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def generate(self, prompt: str, *, aspect_ratio: str = "1:1"):
        self.calls.append((prompt, aspect_ratio))
        return self.result


def _state(kind=PostKind.IMAGE, platform="instagram") -> CampaignState:
    state = CampaignState(brand_name="Acme", platforms=[platform])
    state.calendar = [ContentItem(platform=platform, topic="Launch day", kind=kind)]
    return state


# --- Provider selection ---------------------------------------------------------------


def test_defaults_to_null_provider_without_a_key(monkeypatch):
    monkeypatch.delenv("IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    assert isinstance(get_image_provider(), NullImageProvider)


def test_null_provider_returns_none():
    assert NullImageProvider().generate("anything") is None


def test_unsupported_provider_falls_back_to_null(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "midjourney")
    monkeypatch.setenv("IMAGE_API_KEY", "k")
    assert isinstance(get_image_provider(), NullImageProvider)


def test_key_without_provider_stays_null(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "none")
    monkeypatch.setenv("IMAGE_API_KEY", "k")
    assert isinstance(get_image_provider(), NullImageProvider)


def test_bad_openai_init_degrades_instead_of_crashing(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("IMAGE_API_KEY", "k")
    monkeypatch.setattr(
        image_provider, "OpenAIImageProvider", lambda *a, **k: (_ for _ in ()).throw(RuntimeError())
    )
    assert isinstance(get_image_provider(), NullImageProvider)


def test_openai_generation_error_returns_none():
    """A failing image API must not raise into the pipeline."""
    provider = OpenAIImageProvider.__new__(OpenAIImageProvider)
    provider._model = "gpt-image-1"

    class _Boom:
        class images:
            @staticmethod
            def generate(**kwargs):
                raise RuntimeError("rate limited")

    provider._client = _Boom()
    assert provider.generate("a cat") is None


# --- Visual Agent rendering path -------------------------------------------------------


def test_visual_agent_stays_spec_only_without_a_provider(monkeypatch):
    monkeypatch.setattr("src.agents.visual.get_image_provider", lambda: NullImageProvider())
    state = VisualAgent().run(_state())
    item = state.calendar[0]

    assert item.visual["status"] == "spec"
    assert item.media == []


def test_visual_agent_renders_and_attaches_media(monkeypatch):
    stub = _StubImages(GeneratedImage(data=_PNG, content_type="image/png"))
    monkeypatch.setattr("src.agents.visual.get_image_provider", lambda: stub)

    state = VisualAgent().run(_state())
    item = state.calendar[0]

    assert item.visual["status"] == "generated"
    assert item.visual["media_id"]
    assert len(item.media) == 1
    assert item.media[0]["kind"] == "image"
    assert item.media[0]["url"].startswith("/media/")


def test_render_uses_the_platform_aspect_ratio(monkeypatch):
    stub = _StubImages(GeneratedImage(data=_PNG, content_type="image/png"))
    monkeypatch.setattr("src.agents.visual.get_image_provider", lambda: stub)

    VisualAgent().run(_state(platform="instagram"))
    assert stub.calls[0][1] == "4:5"  # Instagram's native feed ratio


def test_failed_render_keeps_the_spec_and_the_campaign(monkeypatch):
    monkeypatch.setattr("src.agents.visual.get_image_provider", lambda: _StubImages(None))

    state = VisualAgent().run(_state())
    item = state.calendar[0]

    assert item.visual["status"] == "spec"
    assert item.visual["prompt"]
    assert item.media == []


def test_text_posts_never_call_the_image_provider(monkeypatch):
    stub = _StubImages(GeneratedImage(data=_PNG, content_type="image/png"))
    monkeypatch.setattr("src.agents.visual.get_image_provider", lambda: stub)

    VisualAgent().run(_state(kind=PostKind.TEXT))
    assert stub.calls == []
