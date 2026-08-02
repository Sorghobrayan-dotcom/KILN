"""One real generation through Genblaze + NVIDIA + B2, then the same brief again.

The second run is the point of the whole submission: it must cost zero provider
calls, because the cache lives in B2 rather than on a disk that dies with the
container.
"""
import time

import _env

_env.load()

from kiln.blobs import B2Blobs  # noqa: E402
from kiln.cache import B2StepCache  # noqa: E402
from kiln.config import settings  # noqa: E402
from kiln.forge import b2_sink, forge, image_provider, region_of  # noqa: E402

PROMPT = (
    "A monochrome engraving of a plumb line hanging dead vertical, "
    "high-contrast woodcut style, stark white on black, game asset"
)

print("Credentials:")
if not _env.report("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_ENDPOINT", "NVIDIA_API_KEY"):
    raise SystemExit("\nFill the missing values in .env first.")

st = settings()
print(f"\nRegion   : {region_of(st.b2_endpoint)}")
print(f"Model    : {st.image_model}")
print(f"Fallbacks: {st.fallback_models}")

blobs = B2Blobs(st.b2_bucket, st.b2_key_id, st.b2_app_key, st.b2_endpoint)
cache = B2StepCache(blobs, prefix="smoke/forge-cache")
provider = image_provider(st)
sink = b2_sink(st)

print("\n--- run 1: cold, expect a real provider call ---")
t0 = time.time()
first = forge(provider, st, PROMPT, cache, sink)
d1 = time.time() - t0
print(f"  model       : {first.model}")
print(f"  sha256      : {first.sha256[:16]}...")
print(f"  url         : {first.url}")
print(f"  manifest    : {first.manifest_uri}")
print(f"  cached      : {first.cached}")
print(f"  elapsed     : {d1:.1f}s")

print("\n--- run 2: same brief, expect the B2 cache to serve it ---")
t0 = time.time()
second = forge(provider, st, PROMPT, cache, sink)
d2 = time.time() - t0
print(f"  sha256      : {second.sha256[:16]}...")
print(f"  cached      : {second.cached}")
print(f"  elapsed     : {d2:.1f}s")

print("\n--- verdict ---")
same = first.sha256 == second.sha256
print(f"  identical asset : {same}")
print(f"  speedup         : {d1 / d2:.0f}x faster" if d2 > 0 else "  instant")
if not same:
    print("  WARNING: the second run produced different bytes — cache did not hit.")
