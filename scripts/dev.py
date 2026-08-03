"""Run Kiln locally.

Uses whatever the environment provides: real B2 and real providers when the
keys are there, memory and the offline sketch provider when they are not. The
app is therefore never dead on arrival. A fresh clone with an empty .env still
shows the whole journey.
"""
import _env

_env.load()

import uvicorn  # noqa: E402

from genblaze_core import KeyStrategy  # noqa: E402
from genblaze_core.storage.sink import ObjectStorageSink  # noqa: E402

from kiln.api import STATE, app, mount_static  # noqa: E402
from kiln.blobs import B2Blobs, BackendBlobs  # noqa: E402
from kiln.config import settings  # noqa: E402
from kiln.forge import b2_sink  # noqa: E402
from kiln.kinds import available, roster  # noqa: E402
from kiln.memory_backend import MemoryBackend
from kiln.rewriter import nvidia_chat  # noqa: E402
from kiln.service import Forge  # noqa: E402

st = settings()
has_b2 = bool(st.b2_key_id and st.b2_app_key and st.b2_bucket)

if has_b2:
    blobs = B2Blobs(st.b2_bucket, st.b2_key_id, st.b2_app_key, st.b2_endpoint)
    sink = b2_sink(st)
    # the sink writes manifests to B2 under an https url; strip the bucket
    # prefix to get back the key the blobs layer reads
    _root = f"{st.b2_endpoint.rstrip('/')}/{st.b2_bucket}/"
    manifest_key_from_url = lambda u: u[len(_root):] if u and u.startswith(_root) else None
    print(f"storage : Backblaze B2, bucket {st.b2_bucket}")
else:
    # No credentials: still run the real sink, so this path exercises the same
    # transfer and URL-rewriting code as production. Assets and state share one
    # backend, so /files/ can serve the gallery instead of showing dead links.
    backend = MemoryBackend(public_url_base="/files")
    blobs = BackendBlobs(backend)
    sink = ObjectStorageSink(backend, prefix="kiln",
                             key_strategy=KeyStrategy.CONTENT_ADDRESSABLE)
    manifest_key_from_url = backend.key_from_url
    print("storage : memory (no B2 keys). Assets served from /files/")

# the taste rewriter is optional: no key, no call, plain expansion
forge = Forge(blobs, st, sink=sink, chat=nvidia_chat(st.nvidia_api_key))

STATE.blobs = blobs
STATE.token = st.kiln_token
STATE.generate = forge.generate
STATE.savings = lambda: forge.savings
STATE.taste = lambda: forge.taste_summary
STATE.roster = lambda: roster(st)
STATE.manifest_key_from_url = manifest_key_from_url

print("kinds   : " + ", ".join(k.key for k in available(st)))
print(f"token   : {st.kiln_token}")

# absolute, so the server can be launched from anywhere
mount_static(str(_env.ROOT / "static"))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
