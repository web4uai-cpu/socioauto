"""Phase 4 review actions: EDIT, REJECT/regenerate, and AUTO-APPROVE.

The security-critical property here is that **no review action can bypass moderation**.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
_PASSWORD = "password123"
_BANNED = "This fund offers guaranteed returns every month"


def _auth(email: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": _PASSWORD})
    if resp.status_code == 201:
        token = resp.json()["access_token"]
    else:
        login = client.post(
            "/api/v1/auth/token", data={"username": email, "password": _PASSWORD}
        )
        token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _campaign(headers, **overrides) -> dict:
    payload = {"platforms": ["x"], "body": "We shipped scheduling.", **overrides}
    resp = client.post("/api/v1/campaigns/manual", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


# --- EDIT ------------------------------------------------------------------------------


def test_edit_updates_the_item():
    headers = _auth("edit-basic@brand.com")
    campaign = _campaign(headers)

    resp = client.patch(
        f"/api/v1/campaigns/{campaign['id']}/items/0",
        json={"body": "We shipped multi-platform scheduling.", "cta": "Book a demo"},
        headers=headers,
    )
    assert resp.status_code == 200
    item = resp.json()["calendar"][0]
    assert item["body"] == "We shipped multi-platform scheduling."
    assert item["status"] == "approved"


def test_edit_only_changes_supplied_fields():
    headers = _auth("edit-partial@brand.com")
    campaign = _campaign(headers, hashtags=["launch"])

    resp = client.patch(
        f"/api/v1/campaigns/{campaign['id']}/items/0",
        json={"cta": "Sign up"},
        headers=headers,
    )
    item = resp.json()["calendar"][0]
    assert item["body"] == "We shipped scheduling."  # untouched
    assert "launch" in item["hashtags"]


def test_edit_cannot_smuggle_banned_content_past_moderation():
    """The whole point of the gate: an edit re-opens it rather than inheriting approval."""
    headers = _auth("edit-bypass@brand.com")
    campaign = _campaign(headers)
    assert campaign["calendar"][0]["status"] == "approved"

    resp = client.patch(
        f"/api/v1/campaigns/{campaign['id']}/items/0",
        json={"body": _BANNED},
        headers=headers,
    )
    assert resp.status_code == 200
    item = resp.json()["calendar"][0]
    assert item["status"] == "rejected"
    assert item["moderation_reasons"]
    assert resp.json()["status"] == "needs_revision"

    # And it must still refuse to publish.
    published = client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=headers
    ).json()
    assert published["calendar"][0]["status"] != "published"
    assert published["calendar"][0]["external_post_id"] is None


def test_edit_clears_stale_seo_scores():
    headers = _auth("edit-stale@brand.com")
    campaign = _campaign(headers)

    resp = client.patch(
        f"/api/v1/campaigns/{campaign['id']}/items/0",
        json={"body": "Totally different copy now."},
        headers=headers,
    )
    # Scores were computed for the old copy, so they must not survive unchanged.
    assert resp.json()["calendar"][0]["seo"] == {}


def test_cannot_edit_a_published_post():
    headers = _auth("edit-published@brand.com")
    campaign = _campaign(headers)
    client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=headers)

    resp = client.patch(
        f"/api/v1/campaigns/{campaign['id']}/items/0",
        json={"body": "too late"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_edit_requires_ownership():
    owner = _auth("edit-owner@brand.com")
    other = _auth("edit-other@brand.com")
    campaign = _campaign(owner)

    resp = client.patch(
        f"/api/v1/campaigns/{campaign['id']}/items/0", json={"body": "mine"}, headers=other
    )
    assert resp.status_code == 404


def test_edit_rejects_out_of_range_item():
    headers = _auth("edit-range@brand.com")
    campaign = _campaign(headers)
    resp = client.patch(
        f"/api/v1/campaigns/{campaign['id']}/items/99", json={"body": "x"}, headers=headers
    )
    assert resp.status_code == 404


# --- REJECT / regenerate ----------------------------------------------------------------


def test_regenerate_redrafts_and_remoderates():
    headers = _auth("regen-basic@brand.com")
    campaign = _campaign(headers)

    resp = client.post(
        f"/api/v1/campaigns/{campaign['id']}/regenerate",
        json={"feedback": "Too dry — make it warmer."},
        headers=headers,
    )
    assert resp.status_code == 200
    item = resp.json()["calendar"][0]
    assert item["body"], "regeneration must produce copy"
    assert item["status"] in ("approved", "rejected")


def test_regenerate_does_not_duplicate_calendar_items():
    """Re-running research/strategy would append items; regeneration must not."""
    headers = _auth("regen-dupes@brand.com")
    campaign = _campaign(headers, platforms=["x", "linkedin"])
    before = len(campaign["calendar"])

    resp = client.post(
        f"/api/v1/campaigns/{campaign['id']}/regenerate", json={}, headers=headers
    )
    assert len(resp.json()["calendar"]) == before


def test_regenerate_can_target_one_item():
    headers = _auth("regen-single@brand.com")
    campaign = _campaign(headers, platforms=["x", "linkedin"])

    resp = client.post(
        f"/api/v1/campaigns/{campaign['id']}/regenerate",
        json={"item_index": 0},
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["calendar"]) == 2


def test_regenerate_refuses_when_everything_is_published():
    headers = _auth("regen-published@brand.com")
    campaign = _campaign(headers)
    client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=headers)

    resp = client.post(
        f"/api/v1/campaigns/{campaign['id']}/regenerate", json={}, headers=headers
    )
    assert resp.status_code == 409


def test_regenerate_requires_ownership():
    owner = _auth("regen-owner@brand.com")
    other = _auth("regen-other@brand.com")
    campaign = _campaign(owner)

    resp = client.post(
        f"/api/v1/campaigns/{campaign['id']}/regenerate", json={}, headers=other
    )
    assert resp.status_code == 404


# --- AUTO-APPROVE ------------------------------------------------------------------------


def test_auto_publish_skips_the_review_queue():
    headers = _auth("auto-on@brand.com")
    resp = client.post(
        "/api/v1/campaigns",
        json={"prompt": "Announce our scheduler", "platforms": ["x"], "auto_publish": True},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "published"
    assert body["calendar"][0]["status"] == "published"
    assert body["calendar"][0]["external_post_id"]


def test_auto_publish_defaults_off():
    headers = _auth("auto-off@brand.com")
    resp = client.post(
        "/api/v1/campaigns",
        json={"prompt": "Announce our scheduler", "platforms": ["x"]},
        headers=headers,
    )
    assert resp.json()["status"] == "pending_review"
    assert resp.json()["calendar"][0]["status"] == "approved"


def test_auto_publish_still_obeys_the_moderation_gate():
    """Auto-approve skips *human* review only — moderation is never bypassed."""
    headers = _auth("auto-banned@brand.com")
    resp = client.post(
        "/api/v1/campaigns/manual",
        json={"platforms": ["x"], "body": _BANNED, "post_kind": "text"},
        headers=headers,
    )
    campaign = resp.json()
    assert campaign["calendar"][0]["status"] == "rejected"

    # Even the auto-publish path cannot push it out.
    approved = client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=headers
    ).json()
    assert approved["calendar"][0]["status"] != "published"
