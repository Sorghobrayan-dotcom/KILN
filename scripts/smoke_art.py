"""Real Pollinations image generation, through Genblaze, into B2 — no credential.

Twice, to show the cache answering the second time.
"""
import time

import _env

_env.load()

from genblaze_core import LoggingTracer, Modality, Pipeline  # noqa: E402

from kiln.blobs import B2Blobs  # noqa: E402
from kiln.cache import B2StepCache  # noqa: E402
from kiln.config import settings  # noqa: E402
from kiln.forge import b2_sink, harvest  # noqa: E402
from kiln.pollinations import PollinationsImageProvider  # noqa: E402

PROMPT = "a monochrome engraving of a plumb line, high contrast woodcut, game asset"

st = settings()
blobs = B2Blobs(st.b2_bucket, st.b2_key_id, st.b2_app_key, st.b2_endpoint)
cache = B2StepCache(blobs, prefix="smoke/art-cache")
provider = PollinationsImageProvider()
sink = b2_sink(st)


def run():
    result = (
        Pipeline("kiln-art")
        .cache(cache)
        .tracer(LoggingTracer())
        .step(provider, model="sana", prompt=PROMPT, modality=Modality.IMAGE)
        .run(sink=sink, timeout=240, raise_on_failure=False)
    )
    return harvest(result, PROMPT, provider.name)


for label in ("cold", "warm"):
    t0 = time.time()
    f = run()
    print(f"{label:5s}  cached={str(f.cached):5s}  {time.time() - t0:5.1f}s  sha={f.sha256[:16]}")
    print(f"       {f.url}")

print(f"\ncache: {cache.hits} hits, {cache.misses} misses")
