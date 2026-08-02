"""Run Kiln locally.

Uses whatever the environment provides: real B2 and real providers when the
keys are there, memory and the offline sketch provider when they are not. The
app is therefore never dead on arrival — a fresh clone with an empty .env still
demonstrates the whole journey.
"""
import _env

_env.load()

import uvicorn  # noqa: E402

from kiln.api import STATE, app, mount_static  # noqa: E402
from kiln.blobs import B2Blobs, MemoryBlobs  # noqa: E402
from kiln.config import settings  # noqa: E402
from kiln.forge import b2_sink  # noqa: E402
from kiln.kinds import available, roster  # noqa: E402
from kiln.service import Forge  # noqa: E402

st = settings()
has_b2 = bool(st.b2_key_id and st.b2_app_key and st.b2_bucket)

if has_b2:
    blobs = B2Blobs(st.b2_bucket, st.b2_key_id, st.b2_app_key, st.b2_endpoint)
    sink = b2_sink(st)
    print(f"storage : Backblaze B2 — {st.b2_bucket}")
else:
    blobs, sink = MemoryBlobs(), None
    print("storage : memory (no B2 keys found)")

forge = Forge(blobs, st, sink=sink)

STATE.blobs = blobs
STATE.token = st.kiln_token
STATE.generate = forge.generate
STATE.savings = lambda: forge.savings
STATE.roster = lambda: roster(st)

print("kinds   : " + ", ".join(k.key for k in available(st)))
print(f"token   : {st.kiln_token}")

# absolute, so the server can be launched from anywhere
mount_static(str(_env.ROOT / "static"))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
