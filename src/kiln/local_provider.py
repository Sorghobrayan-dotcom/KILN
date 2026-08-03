"""A Genblaze provider that generates offline, for free, and identically every time.

Three reasons this exists, and none of them is a mock:

1. A judge can clone the repository and run the whole pipeline, cache and
   staging and approval and sealed version and manifest, without an API key.
2. Kiln's own tests exercise the real Genblaze machinery rather than a stand-in
   for it: a real Pipeline, a real Step, a real manifest.
3. Every hosted image tier we tried on 2026-08-02 was gated (NVIDIA answered 504
   after 303s; Google returned 429 with ``limit: 0`` on all six of its image
   models). A pipeline whose demo depends on somebody else's free tier is a
   pipeline that cannot be demonstrated.

What it draws is deterministic art derived from the prompt's hash: bands and a
disc whose colours and geometry come from the text. It is not pretending to be a
diffusion model; it is a generator whose output is reproducible, which is
exactly what a provenance system should be tested against.
"""
import hashlib
import io
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any

from genblaze_core.models.asset import Asset
from genblaze_core.models.step import Step
from genblaze_core.providers import SyncProvider
from genblaze_core.runnable.config import RunnableConfig

_SIZE = 512


def render(prompt: str, size: int = _SIZE) -> bytes:
    """Deterministic PNG for a prompt. Same text in, same bytes out, forever."""
    from PIL import Image, ImageDraw

    seed = hashlib.sha256(prompt.encode("utf-8")).digest()
    img = Image.new("RGB", (size, size), (seed[0] // 3, seed[1] // 3, seed[2] // 3))
    draw = ImageDraw.Draw(img)

    # horizontal bands: one per byte, so the whole hash is visible at a glance
    band = size / 16
    for i in range(16):
        c = seed[i + 3]
        draw.rectangle(
            [0, i * band, size, (i + 1) * band],
            fill=(c, (c * 3) % 256, (c * 7) % 256),
        )

    # a disc whose position and size also come from the hash
    r = size // 6 + seed[20] % (size // 6)
    cx = size // 4 + seed[21] % (size // 2)
    cy = size // 4 + seed[22] % (size // 2)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(seed[23], seed[24], seed[25]))

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class LocalImageProvider(SyncProvider):
    """Genblaze provider drawing locally. No network, no key, no cost."""

    name = "kiln-local"

    def __init__(self, output_dir: str | Path | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # None means the system temp dir: Genblaze's sink will only upload
        # files from temp or from a declared output_dir.
        self._output_dir = Path(output_dir) if output_dir else None
        if self._output_dir:
            self._output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        data = render(step.prompt or "")
        digest = hashlib.sha256(data).hexdigest()
        ext = mimetypes.guess_extension("image/png") or ".png"

        if self._output_dir:
            path = self._output_dir / f"{digest}{ext}"
        else:
            handle, name = tempfile.mkstemp(suffix=ext)
            os.close(handle)
            path = Path(name)
        path.write_bytes(data)

        # the hash is set here because we hold the bytes: a run without a sink
        # would otherwise carry no content identity at all
        step.assets.append(
            Asset(
                url=path.resolve().as_uri(),
                media_type="image/png",
                sha256=digest,
                size_bytes=len(data),
            )
        )
        return step
