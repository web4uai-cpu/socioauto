# 🔄 SocialMediaAI — Agent Workflow Specification

## Complete Workflow: User Input → Published Post

### Phase 1: INPUT (0-2 minutes)

```
User enters: "Create a campaign about AI in healthcare for doctors"
    ↓
NLP Parser extracts:
  Topic: "AI in healthcare"
  Target Audience: "doctors"
  Platforms: [instagram, twitter, linkedin] (default)
  Tone: "professional" (default)
  CTA: "Learn more" (default)
    ↓
Output: Structured CampaignRequest object
```

Implemented today as `CampaignCreateRequest` in
[src/api/schemas.py](../src/api/schemas.py), accepted by `POST /api/v1/campaigns`
([src/api/routes/campaigns.py](../src/api/routes/campaigns.py)).

### Phase 2: RESEARCH (2-5 minutes)

```
Research Agent executes:
  Web scraping for trending AI healthcare topics
  Competitor analysis on social platforms
  Keyword research (Google Trends API)
  Hashtag analysis
  Audience sentiment analysis
    ↓
Output: ResearchReport with:
  Top 10 trending topics
  20 high-value keywords
  15-20 optimized hashtags
  Competitor post analysis
  Audience pain points
```

Baseline today: [src/agents/trend_research.py](../src/agents/trend_research.py) returns
`{topic, score, source, rationale}` per trend; web scraping/Google Trends/competitor analysis
are not yet wired up (see [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) Phase 2).

### Phase 3: CONTENT GENERATION (3-7 minutes)

```
Content Agent executes in parallel:
├─ Instagram Post: 125-150 words, 15-20 hashtags
├─ Twitter Post: Under 280 chars, thread option
├─ LinkedIn Post: 150-300 words, professional tone
└─ Facebook Post: Engaging, community-focused
    ↓
Visual Agent executes:
├─ Instagram image (1080x1080 or 1080x1350)
├─ Twitter image (1200x675)
├─ LinkedIn image (1200x627)
└─ Thumbnails for all platforms
    ↓
Video Agent executes:
├─ YouTube script (60 seconds)
├─ TikTok script (30 seconds)
└─ Thumbnails for video platforms
    ↓
SEO Agent executes:
├─ Keyword optimization
├─ Hashtag strategy
├─ Lead capture form suggestions
└─ Readability & SEO scoring
    ↓
Output: Complete ContentPackage
```

Baseline today: [src/agents/content_creation.py](../src/agents/content_creation.py) drafts
per-platform copy respecting `PLATFORM_LIMITS`. Visual Agent, Video Agent, and SEO Agent are
not yet implemented — see Phase 3/5 of [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md).

### Phase 4: REVIEW & APPROVAL (User-dependent)

```
Content appears in Review Queue (Admin Panel)
    ↓
User options:
├─ APPROVE → Proceed to publishing
├─ EDIT → Modify content, then approve
├─ REJECT → Send back for regeneration
└─ AUTO-APPROVE → Skip review (trusted campaigns)
```

Implemented today: [src/agents/moderation.py](../src/agents/moderation.py) sets each item to
`APPROVED`/`REJECTED`; `POST /api/v1/campaigns/{id}/approve` is the human trigger for the next
phase. `EDIT` and `AUTO-APPROVE` (per-brand `auto_publish` flag) are not yet wired into the API.
UI: [CampaignReviewQueue.tsx](../frontend/src/components/CampaignReviewQueue.tsx).

### Phase 5: SCHEDULING & PUBLISHING (Automated)

```
Publishing Agent calculates optimal times:
  Instagram: 11 AM - 1 PM, 7 PM - 9 PM
  LinkedIn: 8 AM - 10 AM, 12 PM - 2 PM (weekdays)
  Twitter: 9 AM, 12 PM, 3 PM, 6 PM
    ↓
Queues content for each platform
    ↓
Executes posting via OAuth APIs
    ↓
Captures post IDs and URLs
    ↓
Output: PublishedPosts with tracking IDs
```

Baseline today: [src/agents/scheduling.py](../src/agents/scheduling.py) assigns a naive fixed
cadence slot; per-platform optimal-time tables above are not yet implemented. Publishing:
[src/agents/publishing.py](../src/agents/publishing.py) +
[src/platforms/http_client.py](../src/platforms/http_client.py) (retry/backoff), OAuth per
platform is a Phase 4 TODO.

### Phase 6: ANALYTICS & OPTIMIZATION (Ongoing)

```
Analytics Agent tracks:
  Engagement (likes, comments, shares)
  Reach and impressions
  Click-through rates
  Lead generation
    ↓
SEO Agent monitors:
  Organic growth
  Search rankings
  Backlink opportunities
    ↓
Generates suggestions for improvement
    ↓
Output: Performance Dashboard + Recommendations
```

Baseline today: [src/agents/analytics.py](../src/agents/analytics.py) records a published-count
snapshot; per-post engagement pulls and SEO monitoring are Phase 5 work. UI:
[AnalyticsBoard.tsx](../frontend/src/components/AnalyticsBoard.tsx).

### Phase 7: REVENUE & REPORTING (Weekly/Monthly)

```
Financial Agent calculates:
  Campaign ROI
  Cost per lead
  Revenue attribution
    ↓
Generates client reports
    ↓
Processes subscription billing
    ↓
Output: Revenue Reports + Growth Insights
```

Not yet implemented (Phase 6 of [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)). Data
model exists: `subscriptions`/`invoices` in [src/db/models.py](../src/db/models.py); UI stub:
[FinancialManagement.tsx](../frontend/src/components/FinancialManagement.tsx).

## Error Handling & Recovery

| Error Type | Recovery Strategy | Current implementation |
|---|---|---|
| Research Error | Retry with broader search terms | not yet implemented |
| Content Generation Error | Fallback to template-based generation | `ContentCreationAgent` uses a simple template today (no LLM fallback logic yet) |
| Publishing Error | Add to retry queue (exponential backoff) | `publish_post` retries via `tenacity` (3 attempts, exponential jitter); `PublishingAgent` catches `PlatformHttpError` and marks the item `FAILED` |
| API Rate Limit | Exponential backoff, queue for later | `src/security/rate_limit.py` rejects with 429 (per-user, per-tier); backoff-and-requeue on inbound 429 from platforms is a TODO in `publish_post` |
| Unknown Error | Escalate to human operator | `PublishingAgent`/`http_client.py` convert unexpected exceptions to `PlatformHttpError` and log via `src/logging_config.py`; no human escalation queue yet |

## 📊 Platform Feature Matrix

| Feature | Free | Starter | Pro | Agency | Enterprise |
|---|---|---|---|---|---|
| Posts/Month | 3 | 30 | 100 | Unlimited | Unlimited |
| Platforms | 1 | 3 | 5 | All | All |
| AI Images | ❌ | ✅ | ✅ | ✅ | ✅ |
| Video Generation | ❌ | ❌ | ✅ | ✅ | ✅ |
| SEO Tools | ❌ | ❌ | ✅ | ✅ | ✅ |
| Lead Tracking | ❌ | ❌ | ✅ | ✅ | ✅ |
| Team Collaboration | ❌ | ❌ | ❌ | ✅ | ✅ |
| White-Label | ❌ | ❌ | ❌ | ✅ | ✅ |
| API Access | ❌ | ❌ | ❌ | ✅ | ✅ |
| Custom AI Training | ❌ | ❌ | ❌ | ❌ | ✅ |
| Dedicated Support | ❌ | ❌ | ❌ | ❌ | ✅ |

See [REVENUE_MODEL.md](../REVENUE_MODEL.md) for pricing and unit economics.

## 🎯 Key Success Metrics

| Metric | Target |
|---|---|
| Time to First Post | < 5 minutes |
| Content Approval Rate | > 85% |
| Publishing Success Rate | > 99% |
| User Retention (30-day) | > 60% |
| NPS Score | > 50 |
| API Uptime | 99.9% |

## High-Level Flow

```mermaid
flowchart LR
    IN[User Input - Natural Language] --> RA[Research Agent]
    RA --> CA[Content Agent]
    CA --> VA[Visual Agent]
    CA --> VID[Video Agent]
    CA --> SEO[SEO Agent]
    VA --> RQ[Review Queue]
    VID --> RQ
    SEO --> RQ
    RQ -->|Human Approval| PUB[Publishing Agent]
    PUB --> PLATFORMS[Instagram / Twitter / LinkedIn / Facebook / TikTok / YouTube]
    PLATFORMS --> ANL[Analytics Agent]
    ANL --> FIN[Financial Agent]
```
