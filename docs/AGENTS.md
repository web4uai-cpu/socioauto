# Agent Specifications

Each agent below is implemented as a class in `src/agents/` conforming to the `BaseAgent`
interface (`run(state: CampaignState) -> CampaignState`). Prompts are stored alongside code in
`src/agents/<agent>/prompt.md` and loaded at runtime — this file documents the spec.

## 1. Orchestrator Agent
- **File**: `src/orchestrator/graph.py`
- **Role**: Owns the campaign state machine, decides next agent, enforces per-brand
  `auto_publish` policy, handles retries/error routing.
- **Inputs**: `CampaignState` (brand config, current stage, history)
- **Outputs**: next stage transition + side-effect log entry

## 2. Trend Research Agent
- **Role**: Discover trending topics/hashtags relevant to brand niche.
- **Tools**: platform trends APIs, news RSS, Google Trends (optional), web search
- **Prompt summary**: "Given brand niche `{niche}` and target platforms `{platforms}`, return
  the top 10 trends with a relevance score 0-1 and a one-line rationale."
- **Output schema**: `List[{topic, score, source, rationale}]`

## 3. Content Strategy Agent
- **Role**: Convert trends + brand voice guidelines into a content calendar (topic, platform,
  format, target date).
- **Prompt summary**: "Using brand voice `{voice_guidelines}` and trends `{trends}`, produce a
  7-day content calendar balancing awareness/engagement/conversion goals."
- **Output schema**: `List[{platform, topic, format, target_date, goal}]`

## 4. Content Creation Agent
- **Role**: Generate platform-specific copy + media brief for each calendar item.
- **Constraints**: respects character limits (X 280, LinkedIn 3000, etc.), brand tone,
  hashtag/style guide.
- **Output schema**: `{platform, body, hashtags[], media_brief, cta}`

## 5. Moderation Agent
- **Role**: Mandatory safety/compliance gate before scheduling.
- **Checks**: profanity/hate speech, brand policy violations, platform ToS, regulated claims
  (medical/financial), PII leakage.
- **Output schema**: `{verdict: approved|rejected|needs_human, reasons[]}`
- **Guardrail**: Publishing Agent MUST refuse content without `verdict == approved`.

## 6. Scheduling Agent
- **Role**: Pick optimal send time per platform using historical analytics + audience timezone
  data; queues job in Celery/Redis.
- **Output schema**: `{content_id, scheduled_at, queue_job_id}`

## 7. Publishing Agent
- **Role**: Calls platform API to publish; handles auth refresh, rate limits, retries with
  exponential backoff, records `published_at` + external post id.
- **Failure handling**: on 429/5xx, requeue with backoff; on 4xx (bad request), mark `failed`
  and notify Orchestrator for human review.

## 8. Engagement Agent
- **Role**: Polls/receives webhook events for comments/replies/DMs, drafts responses using brand
  voice, flags anything needing escalation (complaints, legal, PR risk) to a human queue.
- **Output schema**: `{engagement_id, draft_response, escalated: bool}`

## Analytics Agent (feedback loop)
- **Role**: Periodically pulls impressions/likes/shares/comments per published item, stores
  snapshots, and feeds aggregated performance back into the Content Strategy Agent's next cycle
  (best-performing topics/formats get prioritized).

## Orchestration Loop (pseudocode)

```python
state = CampaignState.new(brand)
state = trend_research.run(state)
state = content_strategy.run(state)
for item in state.calendar:
    state = content_creation.run(state, item)
    state = moderation.run(state, item)
    if state.verdict != "approved":
        continue  # skip publishing, queue for human review
    state = scheduling.run(state, item)
    state = publishing.run(state, item)
state = engagement.run(state)
state = analytics.run(state)
```
