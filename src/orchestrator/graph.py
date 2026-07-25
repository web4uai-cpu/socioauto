"""Orchestrator: runs the campaign state through each agent in sequence.

Pipeline order (see docs/AGENTS.md):

    input-parser -> trend-research -> content-strategy -> content-creation
      -> visual -> video -> seo -> moderation -> scheduling -> publishing
      -> engagement -> analytics

Visual, video, and SEO run *before* moderation on purpose: everything they generate is
reviewed by the moderation gate along with the copy, so nothing reaches a platform
unreviewed.
"""

from __future__ import annotations

from src.agents.analytics import AnalyticsAgent
from src.agents.content_creation import ContentCreationAgent
from src.agents.content_strategy import ContentStrategyAgent
from src.agents.engagement import EngagementAgent
from src.agents.input_parser import InputParserAgent
from src.agents.moderation import ModerationAgent
from src.agents.publishing import PublishingAgent
from src.agents.scheduling import SchedulingAgent
from src.agents.seo import SEOAgent
from src.agents.trend_research import TrendResearchAgent
from src.agents.video import VideoAgent
from src.agents.visual import VisualAgent
from src.orchestrator.state import CampaignState

# Agents that generate or refine content, up to (but not including) the moderation gate.
GENERATION_AGENTS = [
    InputParserAgent(),
    TrendResearchAgent(),
    ContentStrategyAgent(),
    ContentCreationAgent(),
    VisualAgent(),
    VideoAgent(),
    SEOAgent(),
]

PIPELINE = [
    *GENERATION_AGENTS,
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
PRE_APPROVAL_PIPELINE = [*GENERATION_AGENTS, ModerationAgent()]


def run_to_moderation(state: CampaignState) -> CampaignState:
    """Run parsing → research → strategy → creation → visual → video → SEO → moderation.

    Stops before scheduling/publishing so a human can approve first.
    """
    for agent in PRE_APPROVAL_PIPELINE:
        state = agent.run(state)
    return state
