# Agent Specifications

Each agent below is implemented as a class in `src/agents/` conforming to the `BaseAgent`
interface (`run(state: CampaignState) -> CampaignState`). Prompts are stored alongside code in
`src/agents/<agent>/prompt.md` and loaded at runtime — this file documents the spec.

## Pipeline order

Defined in `src/orchestrator/graph.py`:

```
input-parser → trend-research → content-strategy → content-creation
  → visual → video → audio → seo → moderation → scheduling → publishing
  → engagement → analytics
```

`GENERATION_AGENTS` covers everything up to the gate; `PRE_APPROVAL_PIPELINE` is those plus
moderation, and is what campaign creation runs. Visual, video, audio, and SEO deliberately sit
**before** moderation so every generated asset is reviewed, not just the copy. Audio runs after
video so it can voice the script the Video Agent just wrote.

Every LLM-backed agent degrades to a deterministic fallback when no `LLM_API_KEY` is
configured, so the pipeline stays runnable without credentials.

## Post kinds

`PostKind` (`src/orchestrator/state.py`) decides which generation agents run for an item. The
caller sets `post_kind` on the request; blank means "decide per platform" via `resolve_kind`
(TikTok → video, everything else → image).

| kind | visual | video | audio |
|---|---|---|---|
| `text` | – | – | – |
| `image` | feed image | – | – |
| `video` | thumbnail | ✓ | voiceover |
| `audio` | cover art | – | podcast clip |
| `faceless_video` | thumbnail | ✓ (no presenter) | voiceover |

An explicit `video` request is honoured on any platform — `VIDEO_PLATFORMS` only supplies the
target runtime, falling back to `DEFAULT_TARGET_SECONDS`.

## Progress reporting

`run_campaign` and `run_to_moderation` accept an optional `on_agent(name, index, total)` hook,
used by `POST /api/v1/campaigns/start` to record per-agent progress into
`src/orchestrator/progress.py` (Redis-backed, in-memory fallback). The UI polls
`GET /api/v1/campaigns/{id}/progress`, which also returns the ordered stage list with display
labels from `AGENT_LABELS` so the client stepper cannot drift from the pipeline. A failing
progress hook is logged and swallowed — telemetry never takes a campaign down.

## 1. Orchestrator Agent
- **File**: `src/orchestrator/graph.py`
- **Role**: Owns the campaign state machine, decides next agent, enforces per-brand
  `auto_publish` policy, handles retries/error routing.
- **Inputs**: `CampaignState` (brand config, current stage, history)
- **Outputs**: next stage transition + side-effect log entry

## 1b. Input Parser Agent
- **File**: `src/agents/input_parser.py`
- **Role**: First agent in the pipeline. Turns `state.raw_input` (the user's natural-language
  request) into a structured brief so downstream agents never re-parse the raw prompt.
- **Seeds**: when the caller supplied no trends, seeds `state.trends` with the parsed topic;
  fills `voice_guidelines` tone/audience only where the caller left them unset.
- **Output schema**: `state.brief = {intent, topic, goal, target_audience, tone, key_points[],
  constraints[]}` where `intent ∈ {announce, educate, promote, engage, recruit, celebrate}`
- **Fallback**: keyword-cue intent classification + first-sentence topic extraction.
- **No-op**: leaves state untouched when `raw_input` is empty (manual posts).

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

## 4b. Visual Agent
- **File**: `src/agents/visual.py`
- **Role**: Attaches an image/thumbnail generation spec to every calendar item.
- **Scope**: always writes the brief. If `IMAGE_PROVIDER` + `IMAGE_API_KEY` are set (dashboard
  → Integrations), it also **renders** the image via `src/media/image_provider.py`, stores it
  through `MediaStorage`, appends it to `item.media`, and flips `visual["status"]` from
  `"spec"` to `"generated"`. With no provider configured it stays spec-only.
- **Failure is non-fatal**: a failing image API leaves the spec in place and the campaign
  continues — an unavailable image service must never cost the user their copy.
- **Platform logic**: native aspect ratio/size per platform (`PLATFORM_VISUAL_SPEC`) —
  Instagram 4:5, TikTok 9:16, X 16:9, LinkedIn/Facebook 1.91:1.
- **Output schema**: `item.visual = {prompt, alt_text, overlay_text, style, aspect_ratio,
  size, status, source}` — `status` is `"spec"` until a renderer runs.
- **Guardrail**: prompts must not depict real identifiable people or unprovided logos.

## 4c. Video Agent
- **File**: `src/agents/video.py`
- **Role**: Writes a short-form video script and thumbnail prompt.
- **Scope**: only runs for platforms with a native short-form surface (`VIDEO_PLATFORMS`:
  TikTok/Instagram 30s, Facebook/X 45s). LinkedIn is skipped by default. Items on other
  platforms keep `video == {}`.
- **Output schema**: `item.video = {hook, scenes[{narration, visual, seconds}],
  call_to_action, thumbnail_prompt, thumbnail_text, target_seconds, status, source}`
- **Fallback**: deterministic three-beat script whose scene durations sum to the target.

## 4d. Audio Agent
- **File**: `src/agents/audio.py`
- **Role**: Writes the voiceover script and voice spec for audio-bearing posts.
- **Scope**: runs for `audio`, `video`, and `faceless_video` kinds. For the video kinds it
  **reuses the Video Agent's per-scene narration** so the voiceover matches the script rather
  than drifting from it; for an audio-only post it writes a standalone ~60s script.
- **Spec, not sound**: no TTS provider is wired up. A provider consumes `audio["script"]` and
  `audio["voice"]` and appends the rendered file to `item.media`, contract unchanged.
- **Output schema**: `item.audio = {script, transcript, hook_line, audio_type, voice{style,
  pace, words_per_minute}, estimated_seconds, music_bed, status, source}` — `audio_type` is
  `voiceover` for video kinds, `podcast_clip` for audio-only.
- **Real logic**: `estimate_seconds()` derives runtime from word count ÷ 150 wpm. The script
  doubles as the caption transcript, which several platforms require for accessibility.

## 4e. SEO Agent
- **File**: `src/agents/seo.py`
- **Role**: Optimizes for search/discovery and lead generation. Runs last in the generation
  chain so it can see the final copy, visual, and video.
- **Also mutates**: merges its hashtags into `item.hashtags`, dedupes, and caps to the
  platform limit (`PLATFORM_HASHTAG_LIMIT`: Instagram 12, TikTok 6, LinkedIn 5, X/Facebook 3).
- **Output schema**: `item.seo = {primary_keyword, keywords[], meta_description (≤155),
  slug, lead_magnet, lead_cta, source}`
- **Guardrail**: never rewrites `item.body` — moderation must review the copy the Content
  Creation Agent produced, not an SEO rewrite of it.

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
