"""Run Kiln locally with no keys at all.

Uses the offline provider and in-memory storage, so the whole product — brief,
cache, staging, approval, sealed version, manifest — is exercisable by anyone
who clones the repository.
"""
import _env

_env.load()

import uvicorn  # noqa: E402

from kiln.api import STATE, app, mount_static  # noqa: E402
from kiln.blobs import MemoryBlobs  # noqa: E402
from kiln.local_provider import LocalImageProvider, render  # noqa: E402
from kiln.service import cache_stats_for, make_generator  # noqa: E402

blobs = MemoryBlobs()
provider = LocalImageProvider()

STATE.blobs = blobs
STATE.token = "kiln-demo-2026"
STATE.generate = make_generator(blobs, provider, "kiln-local-1")
STATE.cache_stats = cache_stats_for(blobs, "providence")


# the offline provider writes file:// urls; serve those bytes through /files so
# the browser can show them without a bucket
_original = STATE.generate


def generate(project: str, description: str, count: int) -> list[dict]:
    results = _original(project, description, count)
    for r in results:
        if r["url"].startswith("file://") and r["sha256"]:
            key = f"{project}/staging/{r['sha256']}.png"
            if blobs.get(key) is None:
                blobs.put(key, render(r["prompt"]), "image/png")
            r["url"] = f"/files/{key}"
    return results


STATE.generate = generate

# absolute, so the server can be launched from anywhere
mount_static(str(_env.ROOT / "static"))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
