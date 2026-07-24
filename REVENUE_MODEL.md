# 💰 SocialMediaAI — Revenue Model

## Subscription Tiers

| Tier | Price/Month | Features |
|------|-------------|----------|
| **Free** | $0 | 3 posts/month, 1 platform, basic templates |
| **Starter** | $49 | 30 posts/month, 3 platforms, AI images, basic analytics |
| **Pro** | $149 | 100 posts/month, 5 platforms, video generation, SEO tools, lead tracking |
| **Agency** | $499 | Unlimited posts, all platforms, white-label, team collaboration, API access |
| **Enterprise** | Custom | Dedicated infrastructure, custom AI training, SLA, priority support |

## Revenue Streams

1. **Subscription Revenue** (MRR)
   - Monthly/annual recurring subscriptions
   - Predictable cash flow
   - Target: $500K MRR by Year 2

2. **Usage-Based Revenue**
   - Extra posts beyond plan limits
   - Premium AI models (GPT-4o vs GPT-3.5)
   - Additional storage & bandwidth
   - Custom integrations

3. **Agency Revenue**
   - White-label licensing
   - Multi-client management
   - Revenue share on client campaigns (10-20%)

4. **Ad Management Revenue**
   - Meta Ads, Google Ads management fee (15-20% of ad spend)
   - Performance-based bonuses
   - Campaign setup fees

5. **Enterprise Services**
   - Custom development
   - Dedicated AI model training
   - On-premise deployment
   - Consulting & strategy

## Unit Economics

- CAC: $150
- ARPU: $120/month
- Gross Margin: 75%
- LTV: $2,160 (18 months avg)
- LTV:CAC Ratio: 14.4:1
- Monthly Churn Target: <5%

## Financial Projections (3-Year)

| Metric | Year 1 | Year 2 | Year 3 |
|--------|--------|--------|--------|
| Users | 5,000 | 25,000 | 100,000 |
| MRR | $50K | $500K | $2.5M |
| ARR | $600K | $6M | $30M |
| Gross Margin | 70% | 75% | 80% |

## Enforcement Hooks (Implementation Notes)

Tier limits above must be enforced server-side, not just marketed:

- `brands.tier` + `plan_limits` table (posts/month, platforms allowed, feature flags) drive a
  quota check in the API layer before `Content Strategy`/`Scheduling` agents run for a brand.
- `POST /campaigns/run` should reject (402/403) once a brand exceeds its monthly post quota,
  pointing to an upgrade path rather than silently degrading.
- Usage-based line items (extra posts, premium model calls, storage) should be metered per
  brand per billing cycle and reconciled with the Stripe subscription (see Phase 6 in
  [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)).
- White-label / Agency revenue share requires a `client_accounts` relationship under an
  `agency_brand_id` plus per-client billing rollups — not yet modeled in
  [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md); add when Phase 6/7 work starts.
