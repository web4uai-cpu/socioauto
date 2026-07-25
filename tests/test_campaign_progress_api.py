"""Background campaign start, the progress endpoint, and post_kind over the API."""

from fastapi.testclient import TestClient

from src.api.main import app
from src.orchestrator import progress

client = TestClient(app)
_PASSWORD = "password123"


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


def test_progress_store_falls_back_to_memory_without_redis():
    progress.reset()
    progress.set_progress("c1", {"status": "running", "percent": 42})
    assert progress.get_progress("c1") == {"status": "running", "percent": 42}
    assert progress.get_progress("missing") is None


def test_start_returns_immediately_then_reports_complete():
    """TestClient runs background tasks on response close, so by the time we poll it's done."""
    headers = _auth("progress-start@brand.com")
    resp = client.post(
        "/api/v1/campaigns/start",
        json={"prompt": "Announce our AI assistant", "platforms": ["x"]},
        headers=headers,
    )
    assert resp.status_code == 202
    campaign_id = resp.json()["campaign_id"]
    assert resp.json()["status"] == "generating"

    prog = client.get(f"/api/v1/campaigns/{campaign_id}/progress", headers=headers)
    assert prog.status_code == 200
    body = prog.json()
    assert body["status"] == "complete"
    assert body["percent"] == 100
    assert body["completed"] == [s["name"] for s in body["stages"]]

    # The campaign itself finished generating and is awaiting review.
    detail = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers)
    assert detail.json()["status"] in ("pending_review", "needs_revision")


def test_progress_lists_ordered_stages_with_labels():
    headers = _auth("progress-stages@brand.com")
    resp = client.post(
        "/api/v1/campaigns/start",
        json={"prompt": "Announce a thing", "platforms": ["x"]},
        headers=headers,
    )
    campaign_id = resp.json()["campaign_id"]
    body = client.get(f"/api/v1/campaigns/{campaign_id}/progress", headers=headers).json()

    names = [s["name"] for s in body["stages"]]
    assert names[0] == "input-parser"
    assert names[-1] == "moderation"
    assert "audio" in names
    assert all(s["label"] for s in body["stages"])


def test_progress_requires_ownership():
    owner = _auth("progress-owner@brand.com")
    other = _auth("progress-other@brand.com")
    campaign_id = client.post(
        "/api/v1/campaigns/start",
        json={"prompt": "Mine", "platforms": ["x"]},
        headers=owner,
    ).json()["campaign_id"]

    assert client.get(f"/api/v1/campaigns/{campaign_id}/progress", headers=other).status_code == 404


def test_progress_requires_auth():
    assert client.get("/api/v1/campaigns/whatever/progress").status_code == 401


def test_campaign_api_accepts_post_kind_and_returns_it():
    headers = _auth("kind-api@brand.com")
    resp = client.post(
        "/api/v1/campaigns",
        json={"prompt": "Announce our assistant", "platforms": ["tiktok"], "post_kind": "audio"},
        headers=headers,
    )
    assert resp.status_code == 201
    item = resp.json()["calendar"][0]
    assert item["kind"] == "audio"
    assert item["audio"]["script"]
    assert item["video"] == {}


def test_manual_post_accepts_post_kind():
    headers = _auth("kind-manual@brand.com")
    resp = client.post(
        "/api/v1/campaigns/manual",
        json={"platforms": ["x"], "body": "Listen to our update", "post_kind": "audio"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["calendar"][0]["kind"] == "audio"


def test_invalid_post_kind_is_rejected():
    headers = _auth("kind-bad@brand.com")
    resp = client.post(
        "/api/v1/campaigns",
        json={"prompt": "x", "platforms": ["x"], "post_kind": "hologram"},
        headers=headers,
    )
    assert resp.status_code == 422
