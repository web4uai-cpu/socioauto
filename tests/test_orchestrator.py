from src.orchestrator.graph import run_campaign
from src.orchestrator.state import CampaignState, ContentStatus


def test_campaign_pipeline_publishes_approved_content():
    state = CampaignState(
        brand_name="Test Brand",
        platforms=["x"],
        trends=[{"topic": "testing rocks", "score": 0.5, "source": "unit-test"}],
    )
    result = run_campaign(state)
    assert len(result.calendar) == 1
    assert result.calendar[0].status == ContentStatus.PUBLISHED
    assert result.calendar[0].external_post_id is not None


def test_moderation_blocks_banned_content():
    from src.agents.moderation import ModerationAgent
    from src.orchestrator.state import ContentItem

    state = CampaignState(brand_name="Test Brand", platforms=["x"])
    item = ContentItem(platform="x", topic="t", body="we offer guaranteed returns")
    item.status = ContentStatus.PENDING_MODERATION
    state.calendar.append(item)
    ModerationAgent().run(state)
    assert item.status == ContentStatus.REJECTED
