# SocialMediaAI — Agent Workflow Specification

Version: 1.0
Date: 2026-07-20
Status: Production Workflow

> **Implementation note (2026-07-25):** This document describes the target end-to-end workflow.
> Implemented today: LLM-backed trend research, content strategy, content creation, and engagement
> replies (`src/llm/provider.py`, Claude, with deterministic fallbacks when no key is configured);
> the moderation gate; the Celery scheduling engine and due-post publisher; real platform publishing
> over OAuth2; inbound webhook ingestion feeding the Engagement Agent; Stripe Checkout plus
> webhook-driven subscription/invoice sync; a content-calendar view and an Integrations panel in the
> admin dashboard.
>
> Not yet implemented: the Visual, Video, SEO, and Financial agents; predictive analytics
> (`PredictiveAnalyticsEngine`); revenue/MRR forecasting (`RevenueTracker`); competitor/keyword
> research tooling (SerpAPI, Brandwatch, Google Trends); and the auto-approve / bulk-review and
> version-history features of the review queue. Phase timings below are aspirational targets, not
> measured figures.

## Complete Workflow: User Input to Published Post

### Phase 1: INPUT (0-2 minutes)

```
User enters: "Create a campaign about AI in healthcare for doctors"
    |
    v
NLP Parser extracts:
  - Topic: "AI in healthcare"
  - Target Audience: "doctors"
  - Platforms: [instagram, twitter, linkedin] (default)
  - Tone: "professional" (default)
  - CTA: "Learn more" (default)
    |
    v
Output: Structured CampaignRequest object
```

**Input Validation Rules:**
- Prompt must be at least 10 characters
- Platforms must be from supported list
- Tone must be one of: professional, casual, witty, inspirational, formal
- Schedule must be in the future (if provided)
- User must have sufficient credits for requested platforms

### Phase 2: RESEARCH (2-5 minutes)

```
Research Agent executes:
  1. Web scraping for trending AI healthcare topics
  2. Competitor analysis on social platforms
  3. Keyword research (Google Trends API)
  4. Hashtag analysis
  5. Audience sentiment analysis
    |
    v
Output: ResearchReport with:
  - Top 10 trending topics
  - 20 high-value keywords
  - 15-20 optimized hashtags
  - Competitor post analysis
  - Audience pain points
  - Content gaps and opportunities
```

**Research Agent Tools:**

| Tool | API | Purpose | Rate Limit |
|---|---|---|---|
| Web Search | SerpAPI | Trend research | 1000 req/day |
| Social Listening | Brandwatch | Competitor analysis | 500 req/day |
| Trend Analysis | Google Trends | Keyword trends | 100 req/day |
| Sentiment Analysis | VADER/TextBlob | Audience mood | Unlimited |

**Research Output Schema:**

```python
class ResearchReport(BaseModel):
    topic: str
    summary: str
    trends: List[Trend]  # 5-10 items
    competitor_posts: List[CompetitorPost]  # Top 10
    keywords: List[Keyword]  # 20 items with volume
    hashtags: List[Hashtag]  # 15-20 items with stats
    audience_insights: AudienceInsights
    content_gaps: List[str]  # 3-5 underserved angles
    sources: List[Source]
    generated_at: datetime
```

### Phase 3: CONTENT GENERATION (3-7 minutes)

```
Content Agent executes in parallel:
  |
  ├── Instagram Post: 125-150 words, 15-20 hashtags
  ├── Twitter Post: Under 280 chars, thread option
  ├── LinkedIn Post: 150-300 words, professional tone
  ├── Facebook Post: Engaging, community-focused
  ├── TikTok Script: 30-60 seconds, hook-driven
  └── YouTube Script: 60 seconds, structured format
  |
  v
Visual Agent executes:
  ├── Instagram image (1080x1080 or 1080x1350)
  ├── Twitter image (1200x675)
  ├── LinkedIn image (1200x627)
  ├── Facebook image (1200x630)
  ├── TikTok thumbnail (1080x1920)
  └── YouTube thumbnail (1280x720)
  |
  v
Video Agent executes:
  ├── YouTube script (60 seconds, 5-part structure)
  ├── TikTok script (30 seconds, hook-focused)
  ├── Instagram Reels script (30 seconds)
  └── Thumbnails for all video content
  |
  v
SEO Agent executes:
  ├── Keyword optimization
  ├── Hashtag strategy refinement
  ├── Lead capture form suggestions
  ├── Backlink opportunities
  └── Readability & SEO scoring
  |
  v
Output: Complete ContentPackage
```

**Content Generation Parallelism:**

> **Aspirational.** The snippet below is the target design, not current behaviour:
> `src/orchestrator/graph.py` runs agents sequentially in-process and LangGraph is not a
> dependency. Visual/video/audio/SEO already no-op cheaply for items whose `PostKind` does
> not need them, so the sequential pass is not the bottleneck it looks like here.

```python
# LangGraph parallel execution
async def generate_content_parallel(state: CampaignState):
    # Start all agents simultaneously
    tasks = [
        content_agent.generate(state),      # Text content
        visual_agent.generate(state),         # Images
        video_agent.generate(state),          # Video scripts
        seo_agent.optimize(state)             # SEO optimization
    ]

    # Wait for all to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge results
    state.content_data = results[0]
    state.visual_assets = results[1]
    state.video_assets = results[2]
    state.seo_data = results[3]

    return state
```

**Platform-Specific Content Formats:**

| Platform | Format | Length | Hashtags | CTA |
|---|---|---|---|---|
| Instagram | Caption + Image | 125-150 words | 15-20 | Required |
| Twitter/X | Tweet/Thread | 280 chars | 2-3 | Required |
| LinkedIn | Article-style | 150-300 words | 3-5 | Required |
| Facebook | Community post | 100-200 words | 5-10 | Optional |
| TikTok | Script + Caption | 30-60 sec | 5-10 | Required |
| YouTube | Script + Metadata | 60 sec | 15 tags | Required |

### Phase 4: REVIEW & APPROVAL (User-dependent)

```
Content appears in Review Queue (Admin Panel)
    |
    v
User options:
  ├─ APPROVE → Proceed to publishing
  ├─ EDIT → Modify content, then approve
  ├─ REJECT → Send back for regeneration with feedback
  └─ AUTO-APPROVE → Skip review (trusted campaigns)
```

**Review Queue Features:**
- Side-by-side platform preview
- Inline editing for text content
- Image regeneration with custom prompts
- Video script revision
- Approval comments/feedback
- Version history tracking
- Bulk approve/reject actions

**Approval States:**

```python
class ApprovalStatus(str, Enum):
    PENDING = "pending"      # Awaiting user review
    APPROVED = "approved"    # Ready for publishing
    REJECTED = "rejected"    # Send back for regeneration
    NEEDS_REVISION = "needs_revision"  # Minor edits needed
    AUTO_APPROVED = "auto_approved"  # Trusted user/campaign
```

### Phase 5: SCHEDULING & PUBLISHING (Automated)

```
Publishing Agent calculates optimal times:
  - Instagram: 11 AM - 1 PM, 7 PM - 9 PM (user timezone)
  - LinkedIn: 8 AM - 10 AM, 12 PM - 2 PM (weekdays only)
  - Twitter: 9 AM, 12 PM, 3 PM, 6 PM
  - Facebook: 1 PM - 3 PM, 7 PM - 9 PM
  - TikTok: 7 PM - 11 PM
  - YouTube: 2 PM - 4 PM, 8 PM - 10 PM
    |
    v
Queues content for each platform
    |
    v
Executes posting via OAuth APIs
    |
    v
Captures post IDs and URLs
    |
    v
Output: PublishedPosts with tracking IDs
```

**Optimal Timing Algorithm:**

```python
class OptimalTimingEngine:
    def calculate_best_time(
        self, 
        platform: str, 
        audience_data: dict,
        historical_data: list
    ) -> datetime:

        # 1. Get historical engagement by hour
        hourly_engagement = self.analyze_historical(historical_data)

        # 2. Adjust for audience timezone
        user_timezone = audience_data.get('timezone', 'UTC')

        # 3. Apply platform-specific rules
        platform_rules = {
            'instagram': [(11, 13), (19, 21)],
            'linkedin': [(8, 10), (12, 14)],
            'twitter': [(9, 9), (12, 12), (15, 15), (18, 18)],
            'facebook': [(13, 15), (19, 21)],
            'tiktok': [(19, 23)],
            'youtube': [(14, 16), (20, 22)]
        }

        # 4. Find intersection of high engagement + platform rules
        best_slots = self.find_optimal_slots(
            hourly_engagement, 
            platform_rules[platform],
            user_timezone
        )

        # 5. Return next available slot
        return best_slots[0]
```

**Publishing Retry Logic:**

```python
class PublishingPipeline:
    MAX_RETRIES = 3
    RETRY_DELAYS = [60, 300, 900]  # 1 min, 5 min, 15 min

    async def publish_with_retry(self, post: Post, platform: str):
        for attempt in range(self.MAX_RETRIES):
            try:
                result = await self.publish(post, platform)
                return result
            except APIRateLimitError:
                # Wait for rate limit reset
                await asyncio.sleep(3600)
            except TemporaryAPIError:
                # Exponential backoff
                delay = self.RETRY_DELAYS[attempt]
                await asyncio.sleep(delay)
            except PermanentAPIError:
                # Log and notify user
                await self.notify_user_of_failure(post, platform)
                break
```

### Phase 6: ANALYTICS & OPTIMIZATION (Ongoing)

```
Analytics Agent tracks:
  - Engagement (likes, comments, shares, saves)
  - Reach and impressions
  - Click-through rates
  - Lead generation (form fills, link clicks)
    |
    v
SEO Agent monitors:
  - Organic growth (followers, subscribers)
  - Search rankings for keywords
  - Hashtag performance
  - Backlink acquisition
    |
    v
Generates suggestions for improvement:
  - Content type recommendations
  - Posting time optimization
  - Hashtag refinements
  - Audience targeting adjustments
    |
    v
Output: Performance Dashboard + Recommendations
```

**Key Metrics Tracked:**

| Metric | Formula | Good | Excellent |
|---|---|---|---|
| Engagement Rate | (L+C+S)/Reach x 100 | >3% | >6% |
| Click-Through Rate | Clicks/Impressions x 100 | >1% | >3% |
| Lead Conversion Rate | Leads/Clicks x 100 | >5% | >10% |
| Cost Per Lead | Ad Spend/Leads | <$50 | <$20 |
| Share of Voice | Your Mentions/Total x 100 | >15% | >30% |
| Follower Growth Rate | (New-Lost)/Total x 100 | >2%/mo | >5%/mo |

**Predictive Analytics:**

```python
class PredictiveAnalyticsEngine:
    def predict_performance(self, content: ContentPackage) -> Prediction:
        # Extract features
        features = {
            'word_count': len(content.caption.split()),
            'hashtag_count': len(content.hashtags),
            'image_quality': content.image.score,
            'sentiment': content.sentiment_score,
            'topic_trendiness': content.research.trend_score,
            'posting_hour': content.scheduled_time.hour,
            'day_of_week': content.scheduled_time.weekday()
        }

        # Load trained model
        model = self.load_model('performance_predictor_v2.pkl')

        # Predict
        prediction = model.predict(features)

        return Prediction(
            estimated_engagement=prediction.engagement,
            estimated_reach=prediction.reach,
            estimated_ctr=prediction.ctr,
            confidence=prediction.confidence,
            suggestions=self.generate_suggestions(features, prediction)
        )
```

### Phase 7: REVENUE & REPORTING (Weekly/Monthly)

```
Financial Agent calculates:
  - Campaign ROI (revenue attributed / cost)
  - Cost per lead (total spend / leads generated)
  - Revenue attribution (which posts drove sales)
    |
    v
Generates client reports:
  - Weekly performance summary
  - Monthly growth report
  - Quarterly strategy review
    |
    v
Processes subscription billing:
  - Monthly recurring charges
  - Usage overage billing
  - Invoice generation and delivery
    |
    v
Output: Revenue Reports + Growth Insights
```

**Revenue Tracking:**

```python
class RevenueTracker:
    def calculate_mrr(self) -> float:
        subscriptions = self.get_active_subscriptions()
        return sum(
            sub.plan.monthly_price 
            for sub in subscriptions 
            if sub.status == 'active'
        )

    def calculate_ltv(self, user_id: UUID) -> float:
        user = self.get_user(user_id)
        avg_monthly = user.total_spent / user.subscription_months
        churn_rate = self.get_churn_rate()
        return avg_monthly / churn_rate

    def forecast_revenue(self, months: int) -> Forecast:
        current_mrr = self.calculate_mrr()
        growth_rate = self.get_growth_rate()
        churn_rate = self.get_churn_rate()

        forecast = []
        for month in range(1, months + 1):
            projected = current_mrr * (1 + growth_rate) ** month
            projected *= (1 - churn_rate) ** month
            forecast.append(projected)

        return Forecast(forecast=forecast)
```

## Error Handling & Recovery

| Error Type | Recovery Strategy | Fallback |
|---|---|---|
| Research Error | Retry with broader search terms | Use cached trending data |
| Content Generation Error | Fallback to template-based generation | Use previous successful campaign |
| Image Generation Error | Retry with simplified prompt | Use stock image from library |
| Publishing Error | Add to retry queue (exponential backoff) | Notify user for manual posting |
| API Rate Limit | Exponential backoff, queue for later | Spread across multiple API keys |
| Authentication Error | Refresh OAuth token | Notify user to reconnect account |
| Unknown Error | Escalate to human operator | Log for post-mortem analysis |

## Workflow State Diagram

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ parse_input │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   research  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │generate_    │
                    │  content    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ generate│  │ generate│  │optimize_│
        │ visuals │  │  video  │  │   seo   │
        └────┬────┘  └────┬────┘  └────┬────┘
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │await_approval│
                   └──────┬──────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
              ▼           ▼           ▼
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │approved │ │rejected │ │ pending │
        │   →     │ │   →     │ │   →     │
        │ publish │ │generate_│ │  END    │
        │         │ │ content │ │ (wait)  │
        └────┬────┘ └─────────┘ └─────────┘
               │
               ▼
        ┌─────────────┐
        │   publish   │
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐
        │track_analytics│
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐
        │    END      │
        └─────────────┘
```

## Timing Estimates

| Phase | Min Time | Max Time | Avg Time |
|---|---|---|---|
| Input Parsing | 1 sec | 5 sec | 2 sec |
| Research | 2 min | 5 min | 3 min |
| Content Generation | 3 min | 7 min | 5 min |
| Visual Generation | 2 min | 4 min | 3 min |
| Video Generation | 3 min | 5 min | 4 min |
| SEO Optimization | 1 min | 2 min | 1.5 min |
| Review & Approval | 1 min | 1 day | 10 min |
| Publishing | 10 sec | 2 min | 1 min |
| Analytics Setup | 5 sec | 10 sec | 5 sec |
| **Total (Auto)** | **~12 min** | **~20 min** | **~15 min** |
| **Total (With Review)** | **~15 min** | **~1 day** | **~30 min** |

<p align="center">
  <strong>SocialMediaAI Agent Workflow</strong><br>
  <em>From natural language to published content in under 15 minutes</em>
</p>
