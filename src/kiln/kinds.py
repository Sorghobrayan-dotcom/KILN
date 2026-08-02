"""What kinds of asset this deployment can actually make.

A game needs more than one sort of thing: lines an NPC speaks, the sound of a
gate closing, a portrait, a establishing shot. Genblaze already spans those
modalities behind one Pipeline; Kiln's job is to know which of them the current
keys can reach, and to say so plainly instead of failing at run time.

A kind is enabled when its credential is present. Nothing here calls out to a
provider — that would make start-up depend on somebody else's uptime — so a
kind being offered means "configured", not "guaranteed". The forge reports the
difference honestly when a run fails.
"""
from dataclasses import dataclass
from typing import Callable

from genblaze_core import Modality

from kiln.config import Settings


@dataclass(frozen=True)
class Kind:
    key: str
    label: str
    modality: Modality
    model: str
    build: Callable[[Settings], object]
    needs: str
    hint: str


def _elevenlabs_tts(st: Settings):
    from genblaze_elevenlabs import ElevenLabsTTSProvider

    return ElevenLabsTTSProvider(api_key=st.elevenlabs_api_key)


def _elevenlabs_sfx(st: Settings):
    from genblaze_elevenlabs import ElevenLabsSFXProvider

    return ElevenLabsSFXProvider(api_key=st.elevenlabs_api_key)


def _gmi_video(st: Settings):
    from genblaze_gmicloud import GMICloudVideoProvider

    return GMICloudVideoProvider(api_key=st.gmi_api_key)


def _gmi_image(st: Settings):
    from genblaze_gmicloud import GMICloudImageProvider

    return GMICloudImageProvider(api_key=st.gmi_api_key)


def _pollinations(st: Settings):
    from kiln.pollinations import PollinationsImageProvider

    return PollinationsImageProvider()


def _local_image(st: Settings):
    from kiln.local_provider import LocalImageProvider

    return LocalImageProvider()


KINDS: tuple[Kind, ...] = (
    Kind("voice", "NPC voice line", Modality.AUDIO, "eleven_flash_v2_5",
         _elevenlabs_tts, "elevenlabs_api_key", "elevenlabs.io — free tier"),
    Kind("sfx", "Sound effect", Modality.AUDIO, "eleven_text_to_sound_v2",
         _elevenlabs_sfx, "elevenlabs_api_key", "elevenlabs.io — free tier"),
    Kind("art", "Concept art", Modality.IMAGE, "sana",
         _pollinations, "", "pollinations.ai — free, no credential"),
    Kind("video", "Establishing shot", Modality.VIDEO, "Veo3-Fast",
         _gmi_video, "gmi_api_key", "gmicloud.ai — hackathon credits"),
    Kind("image", "Concept art (GMI)", Modality.IMAGE, "reve-remix-20250915",
         _gmi_image, "gmi_api_key", "gmicloud.ai — hackathon credits"),
    Kind("sketch", "Offline sketch", Modality.IMAGE, "kiln-local-1",
         _local_image, "", "always available, no key, no network"),
)

BY_KEY = {k.key: k for k in KINDS}


def available(st: Settings) -> list[Kind]:
    """Kinds whose credential is configured. 'sketch' needs none, so the app is
    never dead on arrival — a fresh clone can still be driven end to end."""
    return [k for k in KINDS if not k.needs or getattr(st, k.needs, "")]


def roster(st: Settings) -> list[dict]:
    """What /health and the UI show: every kind, and why it is or isn't usable."""
    enabled = {k.key for k in available(st)}
    return [
        {
            "key": k.key,
            "label": k.label,
            "modality": str(k.modality),
            "model": k.model,
            "enabled": k.key in enabled,
            "hint": k.hint if k.key in enabled else f"set {k.needs.upper()} — {k.hint}",
        }
        for k in KINDS
    ]


def resolve(st: Settings, key: str) -> Kind:
    kind = BY_KEY.get(key)
    if kind is None:
        raise KeyError(f"unknown kind {key!r}: expected one of {sorted(BY_KEY)}")
    if kind.needs and not getattr(st, kind.needs, ""):
        raise KeyError(f"kind {key!r} needs {kind.needs.upper()} — {kind.hint}")
    return kind
