"""Orchestrator: runs the campaign state through each agent in sequence."""

from __future__ import annotations

from src.agents.analytics import AnalyticsAgent
from src.agents.content_creation import ContentCreationAgent
from src.agents.content_strategy import ContentStrategyAgent
from src.agents.engagement import EngagementAgent
from src.agents.moderation import ModerationAgent
from src.agents.publishing import PublishingAgent
from src.agents.scheduling import SchedulingAgent
from src.agents.trend_research import TrendResearchAgent
from src.orchestrator.state import CampaignState

PIPELINE = [
    TrendResearchAgent(),
    ContentStrategyAgent(),
    ContentCreationAgent(),
    ModerationAgent(),
    SchedulingAgent(),
    PublishingAgent(),
    EngagementAgent(),
    AnalyticsAgent(),
]


def run_campaign(state: CampaignState) -> CampaignState:
    for agent in PIPELINE:
        state = agent.run(state)
    return state


# Agents run at campaign-creation time, up to (and including) the moderation gate. Scheduling
# and publishing are deferred to an explicit human approval step.
PRE_APPROVAL_PIPELINE = [
    TrendResearchAgent(),
    ContentStrategyAgent(),
    ContentCreationAgent(),
    ModerationAgent(),
]


def run_to_moderation(state: CampaignState) -> CampaignState:
    """Run research → strategy → creation → moderation (no scheduling/publishing)."""
    for agent in PRE_APPROVAL_PIPELINE:
        state = agent.run(state)
    return state
