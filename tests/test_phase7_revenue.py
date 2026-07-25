"""Phase 7: token accounting, revenue rollups, and honestly-absent metrics."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.finance.reports import TIER_MONTHLY_USD, build_revenue_report
from src.llm import usage
from src.llm.usage import Usage, estimate_cost

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_scope():
    usage.start()
    yield


def _sub(tier="pro", status="active") -> dict:
    return {"id": "s1", "tier": tier, "status": status, "current_period_end": None}


def _inv(amount=100.0, status="paid", days_ago=1) -> dict:
    return {
        "id": "i1",
        "amount_due": amount,
        "currency": "usd",
        "status": status,
        "issued_at": datetime.now(UTC) - timedelta(days=days_ago),
    }


def _report(subs=None, invs=None, usages=None) -> dict:
    return build_revenue_report(
        subscriptions=subs or [],
        invoices=invs or [],
        campaign_usage=usages or [],
    )


# --- Token accounting ---------------------------------------------------------------------


def test_usage_accumulates_across_calls():
    usage.record(100, 50)
    usage.record(20, 10)
    snap = usage.snapshot()

    assert snap["calls"] == 2
    assert snap["input_tokens"] == 120
    assert snap["output_tokens"] == 60
    assert snap["total_tokens"] == 180


def test_cost_is_none_without_configured_rates(monkeypatch):
    """A zero would read as 'this was free'; unknown must stay unknown."""
    monkeypatch.delenv("LLM_COST_PER_MTOK_INPUT", raising=False)
    monkeypatch.delenv("LLM_COST_PER_MTOK_OUTPUT", raising=False)
    assert estimate_cost(Usage(input_tokens=1_000_000, output_tokens=1_000_000)) is None


def test_cost_uses_configured_rates(monkeypatch):
    monkeypatch.setenv("LLM_COST_PER_MTOK_INPUT", "3")
    monkeypatch.setenv("LLM_COST_PER_MTOK_OUTPUT", "15")
    cost = estimate_cost(Usage(input_tokens=1_000_000, output_tokens=1_000_000))
    assert cost == 18.0


def test_malformed_rate_is_ignored(monkeypatch):
    monkeypatch.setenv("LLM_COST_PER_MTOK_INPUT", "not-a-number")
    monkeypatch.delenv("LLM_COST_PER_MTOK_OUTPUT", raising=False)
    assert estimate_cost(Usage(input_tokens=1_000_000)) is None


def test_recording_outside_a_scope_does_not_raise():
    usage._current.set(None)
    usage.record(10, 10)  # must be a no-op, not an error


def test_merge_sums_counters_and_costs():
    merged = usage.merge(
        {
            "input_tokens": 10,
            "output_tokens": 5,
            "calls": 1,
            "total_tokens": 15,
            "estimated_cost_usd": 0.5,
        },
        {
            "input_tokens": 20,
            "output_tokens": 5,
            "calls": 1,
            "total_tokens": 25,
            "estimated_cost_usd": 0.25,
        },
    )
    assert merged["total_tokens"] == 40
    assert merged["calls"] == 2
    assert merged["estimated_cost_usd"] == 0.75


def test_merge_keeps_cost_none_when_neither_side_is_priced():
    merged = usage.merge({"total_tokens": 5}, {"total_tokens": 5})
    assert merged["estimated_cost_usd"] is None
    assert merged["total_tokens"] == 10


def test_pipeline_records_usage_into_state():
    from src.orchestrator.graph import run_campaign
    from src.orchestrator.state import CampaignState

    state = run_campaign(CampaignState(brand_name="Acme", platforms=["x"], raw_input="Hi"))
    # No LLM configured, so no tokens were spent — and that is recorded, not left blank.
    assert state.usage["total_tokens"] == 0
    assert state.usage["estimated_cost_usd"] is None


# --- Revenue rollups -----------------------------------------------------------------------


def test_mrr_and_arr_from_active_subscriptions():
    report = _report(subs=[_sub("pro"), _sub("starter")])
    revenue = report["revenue"]

    expected = TIER_MONTHLY_USD["pro"] + TIER_MONTHLY_USD["starter"]
    assert revenue["mrr"] == expected
    assert revenue["arr"] == round(expected * 12, 2)
    assert revenue["paying_accounts"] == 2


def test_canceled_subscriptions_do_not_count_as_revenue():
    assert _report(subs=[_sub("pro", "canceled")])["revenue"]["mrr"] == 0.0


def test_trialing_counts_toward_mrr():
    assert _report(subs=[_sub("pro", "trialing")])["revenue"]["mrr"] == TIER_MONTHLY_USD["pro"]


def test_enterprise_is_counted_but_not_priced():
    """Enterprise is contract-priced — assuming a number would fabricate revenue."""
    report = _report(subs=[_sub("enterprise")])
    assert report["revenue"]["mrr"] == 0.0
    assert report["revenue"]["enterprise_accounts_excluded"] == 1
    assert report["revenue"]["paying_accounts"] == 1


def test_invoice_rollup_splits_by_status():
    report = _report(invs=[_inv(100, "paid"), _inv(50, "open"), _inv(25, "uncollectible")])
    assert report["invoices"]["collected"] == 100.0
    assert report["invoices"]["outstanding"] == 50.0
    assert report["invoices"]["uncollectible"] == 25.0


# --- Generation cost -----------------------------------------------------------------------


def test_generation_cost_reports_tokens_without_a_price():
    report = _report(usages=[{"total_tokens": 5000, "estimated_cost_usd": None}])
    cost = report["generation_cost"]

    assert cost["total_tokens"] == 5000
    assert cost["estimated_cost_usd"] is None
    assert cost["priced"] is False


def test_generation_cost_sums_priced_campaigns():
    report = _report(
        usages=[
            {"total_tokens": 1000, "estimated_cost_usd": 0.01},
            {"total_tokens": 2000, "estimated_cost_usd": 0.02},
        ]
    )
    assert report["generation_cost"]["estimated_cost_usd"] == 0.03
    assert report["generation_cost"]["priced"] is True


# --- Honestly-absent metrics ----------------------------------------------------------------


def test_roi_cpl_and_attribution_are_reported_unavailable_with_reasons():
    """These need data the system does not collect; estimating them would be fabrication."""
    report = _report(subs=[_sub()], invs=[_inv()])
    unavailable = {u["metric"]: u for u in report["unavailable"]}

    assert set(unavailable) == {"campaign_roi", "cost_per_lead", "revenue_attribution"}
    for entry in unavailable.values():
        assert entry["reason"]
        assert entry["needs"]


def test_no_roi_number_appears_anywhere_in_the_report():
    report = _report(subs=[_sub()], invs=[_inv()], usages=[{"total_tokens": 1}])
    assert "roi" not in report["revenue"]
    assert "cost_per_lead" not in report["generation_cost"]


def test_growth_insights_mention_churn_and_past_due():
    report = _report(subs=[_sub(), _sub(status="canceled"), _sub(status="past_due")])
    joined = " ".join(report["growth_insights"]).lower()
    assert "churn" in joined
    assert "past due" in joined


def test_empty_account_says_so_rather_than_showing_zeros_as_insight():
    assert "No billing activity yet" in _report()["growth_insights"][0]


# --- Endpoint ---------------------------------------------------------------------------------


def test_revenue_report_endpoint_requires_auth():
    assert client.get("/api/v1/admin/revenue-report").status_code == 401


def test_revenue_report_endpoint_returns_the_report():
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "revenue-report@brand.com", "password": "password123"},
    )
    token = (
        resp.json()["access_token"]
        if resp.status_code == 201
        else client.post(
            "/api/v1/auth/token",
            data={"username": "revenue-report@brand.com", "password": "password123"},
        ).json()["access_token"]
    )
    body = client.get(
        "/api/v1/admin/revenue-report", headers={"Authorization": f"Bearer {token}"}
    ).json()

    assert "revenue" in body
    assert "generation_cost" in body
    assert len(body["unavailable"]) == 3
