import pytest
from fastapi.testclient import TestClient

import kiln.api as api
from kiln.blobs import MemoryBlobs

AUTH = {"X-Kiln-Token": "t"}


def fake_generate(project, description, count):
    """Two fresh assets, then everything is a cache hit — like a warm bucket."""
    out = []
    for i in range(count):
        out.append({
            "asset_id": f"sha{i}", "prompt": f"{description} #{i}",
            "model": "kiln-local-1", "provider": "kiln-local",
            "url": f"/files/demo/{i}.png", "sha256": f"sha{i}",
            "score": 9, "reasons": "on style", "cached": i >= 2,
        })
    return out


@pytest.fixture
def client():
    api.STATE.blobs = MemoryBlobs()
    api.STATE.generate = fake_generate
    api.STATE.token = "t"
    api.STATE.cache_stats = lambda: {"hits": 3, "misses": 1}
    return TestClient(api.app)


def test_health_reports_cache_stats(client):
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["cache"] == {"hits": 3, "misses": 1}


def test_full_journey_brief_to_sealed_manifest(client):
    r = client.post("/api/briefs",
                    json={"project": "providence", "description": "npc portrait", "count": 3},
                    headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["served_from_cache"] == 1
    assert "1 served from B2" in body["summary"]

    staged = client.get("/api/projects/providence/staging").json()["assets"]
    assert len(staged) == 3

    client.post("/api/projects/providence/assets/sha0/approve", headers=AUTH)
    client.post("/api/projects/providence/assets/sha1/approve", headers=AUTH)
    client.post("/api/projects/providence/assets/sha2/reject", headers=AUTH)

    manifest = client.post("/api/projects/providence/publish", headers=AUTH).json()
    assert manifest["version"] == 1
    assert [a["asset"] for a in manifest["assets"]] == ["sha0", "sha1"]

    fetched = client.get("/api/projects/providence/versions/1/manifest").json()
    assert fetched == manifest


def test_mutations_need_the_token(client):
    assert client.post("/api/briefs",
                       json={"project": "p", "description": "x", "count": 1}).status_code == 401
    assert client.post("/api/projects/p/assets/a/approve").status_code == 401
    assert client.post("/api/projects/p/publish").status_code == 401


def test_reads_are_open_so_judges_can_look_without_a_key(client):
    assert client.get("/api/projects/providence/staging").status_code == 200
    assert client.get("/health").status_code == 200


def test_missing_version_is_404_not_a_crash(client):
    assert client.get("/api/projects/providence/versions/9/manifest").status_code == 404


def test_files_are_served_from_the_bucket(client):
    api.STATE.blobs.put("demo/0.png", b"\x89PNG-bytes", "image/png")
    r = client.get("/files/demo/0.png")
    assert r.status_code == 200
    assert r.content == b"\x89PNG-bytes"
    assert r.headers["content-type"] == "image/png"
    assert client.get("/files/demo/nope.png").status_code == 404


def test_brief_rejects_a_silly_count(client):
    r = client.post("/api/briefs",
                    json={"project": "p", "description": "x", "count": 99}, headers=AUTH)
    assert r.status_code == 422
