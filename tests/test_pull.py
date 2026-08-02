"""examples/pull.py is deliberately standalone (stdlib only, no kiln import),
so these tests load it by path rather than as a package member."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "kiln_pull", Path(__file__).parent.parent / "examples" / "pull.py"
)
pull_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pull_mod)


GOOD = b"these are the asset bytes"
GOOD_SHA = hashlib.sha256(GOOD).hexdigest()


def manifest(**overrides):
    base = {
        "project": "providence",
        "version": 1,
        "sealed_at": 1754000000.0,
        "assets": [
            {"asset": GOOD_SHA, "sha256": GOOD_SHA,
             "url": f"https://bucket/kiln/assets/{GOOD_SHA}.mp3",
             "prompt": "gate line", "provider": "elevenlabs-tts",
             "model": "eleven_flash_v2_5", "score": 9},
        ],
    }
    base.update(overrides)
    return base


def test_verify_accepts_matching_bytes_and_refuses_others():
    assert pull_mod.verify(GOOD, GOOD_SHA)
    assert not pull_mod.verify(b"tampered", GOOD_SHA)


def test_pull_writes_the_asset_under_its_sha_and_extension(tmp_path):
    report = pull_mod.pull(manifest(), lambda url: GOOD, tmp_path)
    assert report.pulled == [f"{GOOD_SHA}.mp3"]
    assert report.refused == []
    assert (tmp_path / f"{GOOD_SHA}.mp3").read_bytes() == GOOD


def test_a_sha_mismatch_is_refused_and_nothing_is_written(tmp_path):
    report = pull_mod.pull(manifest(), lambda url: b"corrupted in transit", tmp_path)
    assert report.pulled == []
    assert report.refused == [GOOD_SHA]
    assert not any(p.name.endswith(".mp3") for p in tmp_path.iterdir())


def test_a_mismatch_never_overwrites_an_existing_good_file(tmp_path):
    target = tmp_path / f"{GOOD_SHA}.mp3"
    target.write_bytes(GOOD)
    pull_mod.pull(manifest(), lambda url: b"corrupted", tmp_path)
    assert target.read_bytes() == GOOD


def test_an_asset_without_a_url_is_refused_not_skipped_silently(tmp_path):
    m = manifest()
    m["assets"][0]["url"] = ""
    report = pull_mod.pull(m, lambda url: GOOD, tmp_path)
    assert report.refused == [GOOD_SHA]


def test_the_pull_record_travels_with_the_assets(tmp_path):
    pull_mod.pull(manifest(), lambda url: GOOD, tmp_path, source="https://bucket/v1/manifest.json")
    record = json.loads((tmp_path / "kiln-pull.json").read_text())
    assert record["project"] == "providence"
    assert record["version"] == 1
    assert record["source"] == "https://bucket/v1/manifest.json"
    assert record["files"] == [f"{GOOD_SHA}.mp3"]
    assert "pulled_at" in record


def test_a_manifest_without_assets_is_an_error():
    with pytest.raises(ValueError, match="no assets"):
        pull_mod.pull(manifest(assets=[]), lambda url: GOOD, Path("."))


def test_extension_falls_back_to_bin_when_the_url_has_none(tmp_path):
    m = manifest()
    m["assets"][0]["url"] = "https://bucket/kiln/assets/opaque"
    report = pull_mod.pull(m, lambda url: GOOD, tmp_path)
    assert report.pulled == [f"{GOOD_SHA}.bin"]
