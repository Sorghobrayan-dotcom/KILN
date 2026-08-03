import pytest
from fastapi.testclient import TestClient

import kiln.api as api
from kiln.blobs import MemoryBlobs

AUTH = {"X-Kiln-Token": "t"}


SAVINGS = {"generations_avoided": 3, "generations_paid_for": 1, "hit_rate": 0.75}
ROSTER = [
    {"key": "voice", "label": "NPC voice line", "enabled": True, "hint": "ok"},
    {"key": "video", "label": "Establishing shot", "enabled": False, "hint": "set GMI_API_KEY"},
]


def fake_generate(project, description, count, kind):
    """Two fresh assets, then everything is a cache hit — like a warm bucket."""
    if kind == "video":
        raise KeyError("kind 'video' needs GMI_API_KEY")
    out = []
    for i in range(count):
        out.append({
            "asset_id": f"sha{i}", "prompt": f"{description} #{i}",
            "model": "eleven_flash_v2_5", "provider": "elevenlabs-tts",
            "kind": kind, "modality": "audio",
            "url": f"/files/demo/{i}.mp3", "sha256": f"sha{i}",
            "manifest_uri": "/files/kiln/manifests/run-1.json",
            "score": 9, "reasons": "on style", "cached": i >= 2,
        })
    return out


@pytest.fixture
def client():
    api.STATE.blobs = MemoryBlobs()
    api.STATE.generate = fake_generate
    api.STATE.token = "t"
    api.STATE.savings = lambda: SAVINGS
    api.STATE.roster = lambda: ROSTER
    return TestClient(api.app)


def test_health_reports_savings_and_kinds(client):
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["savings"] == SAVINGS
    assert body["kinds"] == ROSTER


def test_kinds_endpoint_says_what_is_missing(client):
    kinds = {k["key"]: k for k in client.get("/api/kinds").json()["kinds"]}
    assert kinds["voice"]["enabled"] is True
    assert kinds["video"]["enabled"] is False
    assert "GMI_API_KEY" in kinds["video"]["hint"]


def test_unconfigured_kind_is_a_400_with_the_reason(client):
    r = client.post("/api/briefs",
                    json={"project": "p", "description": "x", "count": 1, "kind": "video"},
                    headers=AUTH)
    assert r.status_code == 400
    assert "GMI_API_KEY" in r.json()["detail"]


def test_full_journey_brief_to_sealed_manifest(client):
    r = client.post("/api/briefs",
                    json={"project": "providence", "description": "npc line",
                          "count": 3, "kind": "voice"},
                    headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["served_from_cache"] == 1
    assert "1 came from B2" in body["summary"]
    assert body["savings"] == SAVINGS

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


def test_provenance_returns_the_library_entry_and_the_genblaze_manifest(client):
    import json

    api.STATE.manifest_key_from_url = lambda u: u.removeprefix("/files/") if u else None
    api.STATE.blobs.put(
        "kiln/manifests/run-1.json",
        json.dumps({"canonical_hash": "abc123", "schema_version": "1.0",
                    "run": {"run_id": "run-1", "steps": [{"provider": "elevenlabs-tts"}]}}).encode(),
        "application/json",
    )
    client.post("/api/briefs",
                json={"project": "p", "description": "x", "count": 1, "kind": "voice"},
                headers=AUTH)

    body = client.get("/api/projects/p/assets/sha0/provenance").json()
    assert body["asset"]["prompt"] == "x #0"
    assert body["manifest"]["canonical_hash"] == "abc123"
    assert body["manifest_note"] is None


def test_provenance_says_why_a_manifest_is_missing_instead_of_pretending(client):
    api.STATE.manifest_key_from_url = lambda u: u.removeprefix("/files/") if u else None
    client.post("/api/briefs",
                json={"project": "p", "description": "x", "count": 1, "kind": "voice"},
                headers=AUTH)

    body = client.get("/api/projects/p/assets/sha0/provenance").json()
    assert body["manifest"] is None
    assert "not readable" in body["manifest_note"] or "predates" in body["manifest_note"]


def test_provenance_on_an_unknown_asset_is_404(client):
    assert client.get("/api/projects/p/assets/nope/provenance").status_code == 404


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
