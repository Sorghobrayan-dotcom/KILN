import pytest

from kiln.kinds import KINDS, available, resolve, roster


class FakeSettings:
    """Only the credential fields kinds.py reads."""

    def __init__(self, **keys):
        self.elevenlabs_api_key = keys.get("elevenlabs", "")
        self.gmi_api_key = keys.get("gmi", "")


def test_sketch_is_always_available_so_a_fresh_clone_still_runs():
    keys = {k.key for k in available(FakeSettings())}
    assert keys == {"sketch"}


def test_elevenlabs_key_unlocks_voice_and_sfx():
    keys = {k.key for k in available(FakeSettings(elevenlabs="sk_x"))}
    assert keys == {"sketch", "voice", "sfx"}


def test_gmi_key_unlocks_video_and_image():
    keys = {k.key for k in available(FakeSettings(gmi="gmi_x"))}
    assert keys == {"sketch", "video", "image"}


def test_every_kind_available_with_both_keys():
    st = FakeSettings(elevenlabs="sk_x", gmi="gmi_x")
    assert len(available(st)) == len(KINDS)


def test_roster_explains_what_is_missing():
    rows = {r["key"]: r for r in roster(FakeSettings())}
    assert rows["video"]["enabled"] is False
    assert "GMI_API_KEY" in rows["video"]["hint"]
    assert rows["sketch"]["enabled"] is True


def test_resolve_refuses_an_unconfigured_kind_by_name():
    with pytest.raises(KeyError, match="GMI_API_KEY"):
        resolve(FakeSettings(), "video")


def test_resolve_refuses_an_unknown_kind():
    with pytest.raises(KeyError, match="unknown kind"):
        resolve(FakeSettings(), "hologram")


def test_resolve_returns_the_kind_when_configured():
    kind = resolve(FakeSettings(elevenlabs="sk_x"), "voice")
    assert kind.model == "eleven_flash_v2_5"
    assert str(kind.modality) == "audio"
