"""A Genblaze provider for Pollinations, which generates images free and
without a credential.

Written because every hosted image tier we tried on 2026-08-02 was shut:
NVIDIA's gateway answered 504 after 303 seconds on a valid request, and Google
returned 429 with ``limit: 0`` on all six of its image models. Pollinations
answers in about four seconds and asks for nothing.

It is also the point at which Kiln stops merely *calling* Genblaze and starts
*extending* it: ``SyncProvider`` is a public contract, and a provider the SDK
does not ship is fifty lines rather than a fork.

The seed is derived from the prompt rather than left to the service. That is
what makes the provider honest inside a provenance system. The same prompt
returns the same picture, so a cache hit and a fresh run cannot be told apart
in the output any more than in the manifest.
"""
import hashlib
import os
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.asset import Asset
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.models.step import Step
from genblaze_core.providers import SyncProvider
from genblaze_core.runnable.config import RunnableConfig

BASE_URL = "https://image.pollinations.ai/prompt/"

#: Pollinations accepts arbitrary sizes, but multiples of 64 avoid resampling.
DEFAULT_SIZE = 1024


def seed_for(prompt: str) -> int:
    """A stable 31-bit seed for a prompt, so the same brief redraws the same art."""
    return int.from_bytes(hashlib.sha256(prompt.encode("utf-8")).digest()[:4], "big") & 0x7FFFFFFF


def build_url(prompt: str, model: str, width: int, height: int, seed: int | None = None) -> str:
    query = urllib.parse.urlencode({
        "width": width,
        "height": height,
        "seed": seed_for(prompt) if seed is None else seed,
        "model": model,
        "nologo": "true",
        "safe": "true",
    })
    return f"{BASE_URL}{urllib.parse.quote(prompt, safe='')}?{query}"


class PollinationsImageProvider(SyncProvider):
    """Free, keyless image generation behind Genblaze's provider contract."""

    name = "pollinations"

    def __init__(
        self,
        output_dir: str | Path | None = None,
        *,
        timeout: float = 180.0,
        client: httpx.Client | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # None means "use the system temp dir". Genblaze's sink refuses to
        # upload a file from anywhere else, which is a path-traversal guard
        # worth respecting rather than working around.
        self._output_dir = Path(output_dir) if output_dir else None
        if self._output_dir:
            self._output_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = timeout
        self._client = client

    def _write(self, data: bytes, suffix: str) -> Path:
        if self._output_dir:
            path = self._output_dir / f"{hashlib.sha256(data).hexdigest()}{suffix}"
            path.write_bytes(data)
            return path
        handle, name = tempfile.mkstemp(suffix=suffix)
        os.close(handle)
        path = Path(name)
        path.write_bytes(data)
        return path

    def _fetch(self, url: str) -> tuple[bytes, str]:
        client = self._client or httpx.Client(timeout=self._timeout, follow_redirects=True)
        try:
            response = client.get(url)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Pollinations unreachable: {exc}",
                error_code=ProviderErrorCode.SERVER_ERROR,
            ) from exc
        finally:
            if self._client is None:
                client.close()

        if response.status_code != 200:
            raise ProviderError(
                f"Pollinations returned {response.status_code}: {response.text[:200]}",
                error_code=ProviderErrorCode.SERVER_ERROR,
            )

        media_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
        if not media_type.startswith("image/"):
            # a text body here means an error page dressed as a 200
            raise ProviderError(
                f"Pollinations returned {media_type}, not an image",
                error_code=ProviderErrorCode.SERVER_ERROR,
            )
        return response.content, media_type

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        params = step.params or {}
        url = build_url(
            step.prompt or "",
            model=step.model or "flux",
            width=int(params.get("width", DEFAULT_SIZE)),
            height=int(params.get("height", DEFAULT_SIZE)),
            seed=step.seed,
        )

        data, media_type = self._fetch(url)
        path = self._write(data, ".png" if media_type == "image/png" else ".jpg")

        step.assets.append(
            Asset(
                url=path.resolve().as_uri(),
                media_type=media_type,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
            )
        )
        return step
