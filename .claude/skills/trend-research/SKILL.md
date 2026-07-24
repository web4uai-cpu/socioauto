---
name: trend-research
description: Discover trending topics and hashtags relevant to a brand niche across social platforms. Use when populating the Trend Research Agent or refreshing trend data before content strategy runs.
---

# Trend Research Skill

1. Read brand niche + target platforms from `CampaignState.brand`.
2. Query available trend sources (platform trends API, news RSS, web search tool) — never fabricate trends.
3. Score each candidate trend 0-1 for relevance to the brand niche.
4. Return `List[{topic, score, source, rationale}]`, sorted by score desc, top 10.
5. Write results to `trends` table / `CampaignState.trends` and hand off to `content-strategy`.
