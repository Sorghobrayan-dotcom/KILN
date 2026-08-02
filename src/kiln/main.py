"""Production entrypoint.

Wires whatever the environment provides and starts serving. Deliberately does
not contact a provider or a bucket at import time: a container that phones home
before it binds is a container whose cold start depends on somebody else's
uptime, and judges click a link before they read a README.
"""
import os
from pathlib import Path

import uvicorn

from kiln.api import STATE, app, mount_static
from kiln.blobs import B2Blobs, BackendBlobs
from kiln.config import settings
from kiln.forge import b2_sink
from kiln.kinds import available, roster
from kiln.memory_backend import MemoryBackend
from kiln.rewriter import nvidia_chat
from kiln.service import Forge

ROOT = Path(__file__).resolve().parent.parent.parent


def build() -> None:
    st = settings()
    has_b2 = bool(st.b2_key_id and st.b2_app_key and st.b2_bucket)

    if has_b2:
        blobs = B2Blobs(st.b2_bucket, st.b2_key_id, st.b2_app_key, st.b2_endpoint)
        sink = b2_sink(st)
        root = f"{st.b2_endpoint.rstrip('/')}/{st.b2_bucket}/"

        def manifest_key_from_url(url: str) -> str | None:
            return url[len(root):] if url and url.startswith(root) else None

        print(f"storage : Backblaze B2 — {st.b2_bucket}", flush=True)
    else:
        from genblaze_core import KeyStrategy
        from genblaze_core.storage.sink import ObjectStorageSink

        backend = MemoryBackend(public_url_base="/files")
        blobs = BackendBlobs(backend)
        sink = ObjectStorageSink(backend, prefix="kiln",
                                 key_strategy=KeyStrategy.CONTENT_ADDRESSABLE)
        manifest_key_from_url = backend.key_from_url
        print("storage : memory (no B2 credentials) — state resets on restart", flush=True)

    # the taste rewriter is optional: no key, no call, plain expansion
    forge = Forge(blobs, st, sink=sink, chat=nvidia_chat(st.nvidia_api_key))

    STATE.blobs = blobs
    STATE.token = st.kiln_token
    STATE.generate = forge.generate
    STATE.savings = lambda: forge.savings
    STATE.taste = lambda: forge.taste_summary
    STATE.roster = lambda: roster(st)
    STATE.manifest_key_from_url = manifest_key_from_url

    print("kinds   : " + ", ".join(k.key for k in available(st)), flush=True)
    mount_static(str(ROOT / "static"))


build()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
        log_level="warning",
    )
