import pytest

from kiln.kinds import KINDS, available, resolve, roster


class FakeSettings:
    """Only the credential fields kinds.py reads."""

    def __init__(self, **keys):
        self.elevenlabs_api_key = keys.get("elevenlabs", "")
        self.gmi_api_key = keys.get("gmi", "")


# kinds that need no credential at all, so an empty .env still demonstrates Kiln
FREE = {"sketch", "art"}


def test_keyless_kinds_are_always_available_so_a_fresh_clone_still_runs():
    assert {k.key for k in available(FakeSettings())} == FREE


def test_elevenlabs_key_unlocks_voice_and_sfx():
    keys = {k.key for k in available(FakeSettings(elevenlabs="sk_x"))}
    assert keys == FREE | {"voice", "sfx"}


def test_gmi_key_unlocks_video_and_image():
    keys = {k.key for k in available(FakeSettings(gmi="gmi_x"))}
    assert keys == FREE | {"video", "image"}


def test_art_is_a_real_generator_not_a_placeholder():
    """'art' goes to Pollinations, which is free but is still an AI service.
    'sketch' draws locally, and must never be sold as generation."""
    art = next(k for k in KINDS if k.key == "art")
    assert art.needs == ""
    assert "pollinations" in art.hint


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
