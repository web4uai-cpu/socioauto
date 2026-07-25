"""Orchestrator: runs the campaign state through each agent in sequence.

Pipeline order (see docs/AGENTS.md):

    input-parser -> trend-research -> content-strategy -> content-creation
      -> visual -> video -> audio -> seo -> moderation -> scheduling -> publishing
      -> engagement -> analytics

Visual, video, audio, and SEO run *before* moderation on purpose: everything they generate is
reviewed by the moderation gate along with the copy, so nothing reaches a platform
unreviewed. Audio runs after video so it can voice the script the Video Agent just wrote.
"""

from __future__ import annotations

from collections.abc import Callable

from src.agents.analytics import AnalyticsAgent
from src.agents.audio import AudioAgent
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
from src.llm import usage
from src.logging_config import get_logger
from src.orchestrator.state import CampaignState

logger = get_logger(__name__)

# Called as each agent finishes: (agent_name, completed_count, total).
ProgressHook = Callable[[str, int, int], None]

# Human-readable stage names for the progress UI, keyed by agent name.
AGENT_LABELS: dict[str, str] = {
    "input-parser": "Understanding your request",
    "trend-research": "Researching trends",
    "content-strategy": "Planning content",
    "content-creation": "Writing copy",
    "visual": "Designing visuals",
    "video": "Scripting video",
    "audio": "Writing voiceover",
    "seo": "Optimising for search",
    "moderation": "Safety review",
    "scheduling": "Scheduling",
    "publishing": "Publishing",
    "engagement": "Monitoring engagement",
    "analytics": "Recording analytics",
}

# Agents that generate or refine content, up to (but not including) the moderation gate.
GENERATION_AGENTS = [
    InputParserAgent(),
    TrendResearchAgent(),
    ContentStrategyAgent(),
    ContentCreationAgent(),
    VisualAgent(),
    VideoAgent(),
    AudioAgent(),
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


def _run(agents: list, state: CampaignState, on_agent: ProgressHook | None) -> CampaignState:
    """Run `agents` in order, reporting completion after each.

    Opens a fresh LLM accounting scope so `state.usage` reflects only this run's tokens.

    A failing progress hook is logged and ignored — progress reporting must never take a
    campaign down with it.
    """
    usage.start()
    total = len(agents)
    for index, agent in enumerate(agents, start=1):
        state = agent.run(state)
        if on_agent is None:
            continue
        try:
            on_agent(agent.name, index, total)
        except Exception as exc:  # noqa: BLE001 - telemetry must not break generation
            logger.warning("progress hook failed", extra={"agent": agent.name, "error": str(exc)})
    # Accumulate, so a regenerated campaign reports what it cost in total rather than only
    # what the latest re-draft cost.
    state.usage = usage.merge(state.usage, usage.snapshot())
    return state


def run_campaign(state: CampaignState, on_agent: ProgressHook | None = None) -> CampaignState:
    return _run(PIPELINE, state, on_agent)


# Agents run at campaign-creation time, up to (and including) the moderation gate. Scheduling
# and publishing are deferred to an explicit human approval step.
PRE_APPROVAL_PIPELINE = [*GENERATION_AGENTS, ModerationAgent()]

# Re-drafting an existing calendar after a reviewer rejects it. Deliberately excludes
# input-parser/research/strategy: those *append* calendar items, so re-running them would
# duplicate the campaign rather than redo it.
REGENERATION_PIPELINE = [
    ContentCreationAgent(),
    VisualAgent(),
    VideoAgent(),
    AudioAgent(),
    SEOAgent(),
    ModerationAgent(),
]


def regenerate(state: CampaignState, on_agent: ProgressHook | None = None) -> CampaignState:
    """Re-draft the existing calendar items, then re-moderate.

    Callers must clear the fields they want rebuilt (`body`, `visual`, `video`, `audio`,
    `seo`) first — every generation agent skips items that already have output.
    """
    return _run(REGENERATION_PIPELINE, state, on_agent)


def run_to_moderation(state: CampaignState, on_agent: ProgressHook | None = None) -> CampaignState:
    """Run parsing → research → strategy → creation → visual → video → audio → SEO → moderation.

    Stops before scheduling/publishing so a human can approve first.

    Args:
        state: Campaign state to run through the pipeline.
        on_agent: Optional hook called as each agent completes, for progress reporting.
    """
    return _run(PRE_APPROVAL_PIPELINE, state, on_agent)
