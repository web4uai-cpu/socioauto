"""Revenue reporting: MRR/ARR, invoice rollups, generation cost, and growth insights.

Everything here is computed from data the system actually holds — Stripe-fed subscriptions and
invoices, plus the LLM tokens we spent generating content.

**Three metrics the spec asks for are deliberately absent**, reported as `unavailable` with the
reason rather than estimated:

- **Campaign ROI** needs revenue attributed to a campaign. Nothing links a payment back to the
  post that earned it — there is no UTM tagging, no conversion events, no attribution window.
- **Cost per lead** needs a lead count. No lead capture or conversion tracking exists.
- **Revenue attribution** is the missing mechanism underneath both.

The *cost* half of ROI is real and is reported (`generation_cost`): it is measured token spend,
not an estimate. Publishing a plausible ROI derived from invented revenue would be the single
most damaging thing this module could do, so it does not.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

# List price per tier, used to derive MRR from active subscriptions. These mirror
# REVENUE_MODEL.md; actual collected amounts come from invoices, not from this table.
TIER_MONTHLY_USD: dict[str, float] = {
    "free": 0.0,
    "starter": 49.0,
    "pro": 149.0,
    "agency": 499.0,
    "enterprise": 0.0,  # negotiated per contract — never assume a number
}
_REVENUE_STATUSES = {"active", "trialing"}
_RECENT_WINDOW_DAYS = 30


def _unavailable(metric: str, reason: str, needs: str) -> dict[str, Any]:
    return {"metric": metric, "reason": reason, "needs": needs}


def _mrr(subscriptions: list[dict[str, Any]]) -> dict[str, Any]:
    """Monthly recurring revenue from subscriptions in a revenue-generating state."""
    billable = [s for s in subscriptions if s.get("status") in _REVENUE_STATUSES]
    by_tier = Counter(s.get("tier", "free") for s in billable)

    known = sum(TIER_MONTHLY_USD.get(tier, 0.0) * n for tier, n in by_tier.items())
    # Enterprise is contract-priced, so it contributes to the count but not the figure.
    enterprise = by_tier.get("enterprise", 0)
    return {
        "mrr": round(known, 2),
        "arr": round(known * 12, 2),
        "by_tier": dict(by_tier),
        "paying_accounts": sum(n for tier, n in by_tier.items() if tier != "free"),
        "enterprise_accounts_excluded": enterprise,
    }


def _invoices(invoices: list[dict[str, Any]]) -> dict[str, Any]:
    def total(status: str) -> float:
        return round(
            sum(float(i.get("amount_due", 0)) for i in invoices if i.get("status") == status), 2
        )

    return {
        "collected": total("paid"),
        "outstanding": total("open"),
        "uncollectible": total("uncollectible"),
        "invoice_count": len(invoices),
    }


def _growth(subscriptions: list[dict[str, Any]], invoices: list[dict[str, Any]]) -> list[str]:
    """Plain-language observations, only where the data supports them."""
    insights: list[str] = []
    cutoff = datetime.now(UTC) - timedelta(days=_RECENT_WINDOW_DAYS)

    canceled = sum(1 for s in subscriptions if s.get("status") == "canceled")
    active = sum(1 for s in subscriptions if s.get("status") in _REVENUE_STATUSES)
    if active or canceled:
        total = active + canceled
        churn = canceled / total if total else 0
        insights.append(
            f"{active} active vs {canceled} canceled subscriptions "
            f"({churn:.0%} of all-time signups have churned)."
        )

    past_due = sum(1 for s in subscriptions if s.get("status") == "past_due")
    if past_due:
        insights.append(
            f"{past_due} subscription(s) past due — recovering these is the cheapest revenue "
            "available."
        )

    def _issued(inv: dict[str, Any]) -> datetime | None:
        issued = inv.get("issued_at")
        if isinstance(issued, datetime):
            return issued if issued.tzinfo else issued.replace(tzinfo=UTC)
        return None

    recent = [i for i in invoices if (d := _issued(i)) and d >= cutoff]
    if recent:
        billed = round(sum(float(i.get("amount_due", 0)) for i in recent), 2)
        insights.append(f"${billed} invoiced in the last {_RECENT_WINDOW_DAYS} days.")

    if not insights:
        insights.append("No billing activity yet — connect Stripe and add a subscription.")
    return insights


def build_revenue_report(
    *,
    subscriptions: list[dict[str, Any]],
    invoices: list[dict[str, Any]],
    campaign_usage: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the revenue report.

    Args:
        subscriptions: normalized subscription rows.
        invoices: normalized invoice rows.
        campaign_usage: each campaign's `state.usage` snapshot.
    """
    tokens = sum(int(u.get("total_tokens", 0) or 0) for u in campaign_usage)
    priced = [u["estimated_cost_usd"] for u in campaign_usage if u.get("estimated_cost_usd")]
    generation_cost = round(sum(priced), 4) if priced else None

    return {
        "revenue": _mrr(subscriptions),
        "invoices": _invoices(invoices),
        "generation_cost": {
            "total_tokens": tokens,
            "campaigns_measured": len([u for u in campaign_usage if u.get("total_tokens")]),
            # None, not 0 — an unpriced run is unknown-cost, not free.
            "estimated_cost_usd": generation_cost,
            "priced": generation_cost is not None,
            "note": (
                "Exact token counts; dollar figure requires LLM_COST_PER_MTOK_INPUT/OUTPUT "
                "to be configured."
            ),
        },
        "growth_insights": _growth(subscriptions, invoices),
        "unavailable": [
            _unavailable(
                "campaign_roi",
                "No revenue is attributed to campaigns, so return cannot be divided by cost.",
                "Conversion tracking: UTM-tagged links, a conversion webhook, and an "
                "attribution window.",
            ),
            _unavailable(
                "cost_per_lead",
                "No leads are captured or counted anywhere in the system.",
                "Lead capture (form or CRM integration) writing lead events per campaign.",
            ),
            _unavailable(
                "revenue_attribution",
                "Payments cannot be traced back to the post or campaign that drove them.",
                "The same conversion tracking as campaign_roi.",
            ),
        ],
    }
