"""Media upload endpoint and manual (user-authored) post creation."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_PASSWORD = "password123"


def _auth(email: str) -> str:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": _PASSWORD})
    if resp.status_code == 201:
        return resp.json()["access_token"]
    login = client.post("/api/v1/auth/token", data={"username": email, "password": _PASSWORD})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_upload_media_rejects_unsupported_content_type():
    token = _auth("media-bad-type@brand.com")
    resp = client.post(
        "/api/v1/media/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_media_rejects_oversized_file(monkeypatch):
    from src.storage import local as storage_local

    monkeypatch.setattr(storage_local.media_storage, "max_upload_bytes", 10)
    token = _auth("media-oversize@brand.com")
    resp = client.post(
        "/api/v1/media/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("clip.mp4", b"x" * 100, "video/mp4")},
    )
    assert resp.status_code == 400


def test_upload_media_succeeds_and_returns_url():
    token = _auth("media-ok@brand.com")
    resp = client.post(
        "/api/v1/media/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("clip.mp3", b"fake-audio-bytes", "audio/mpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "audio"
    assert body["url"].startswith("/media/")


def test_manual_post_requires_auth():
    resp = client.post("/api/v1/campaigns/manual", json={"platforms": ["x"], "body": "hello"})
    assert resp.status_code == 401


def test_manual_post_is_gated_by_moderation_before_publish():
    token = _auth("manual-post@brand.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/v1/campaigns/manual",
        json={"platforms": ["x"], "body": "Check out our new product launch"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    campaign = create_resp.json()
    assert campaign["calendar"][0]["status"] == "approved"

    approve_resp = client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=headers
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["calendar"][0]["status"] == "published"


def test_manual_post_rejected_by_moderation_cannot_publish():
    token = _auth("manual-rejected@brand.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/v1/campaigns/manual",
        json={"platforms": ["x"], "body": "This offers guaranteed returns overnight"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    campaign = create_resp.json()
    assert campaign["calendar"][0]["status"] == "rejected"
    assert campaign["calendar"][0]["moderation_reasons"]

    approve_resp = client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=headers
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["calendar"][0]["status"] != "published"


def test_manual_post_carries_media_reference():
    token = _auth("manual-media@brand.com")
    headers = {"Authorization": f"Bearer {token}"}

    upload_resp = client.post(
        "/api/v1/media/upload",
        headers=headers,
        files={"file": ("clip.mp4", b"fake-video-bytes", "video/mp4")},
    )
    media_ref = upload_resp.json()

    create_resp = client.post(
        "/api/v1/campaigns/manual",
        json={"platforms": ["instagram"], "body": "Behind the scenes", "media": [media_ref]},
        headers=headers,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["calendar"][0]["media"] == [media_ref]
