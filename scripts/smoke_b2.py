"""Prove the B2 credentials work: put, get, list, and a real B2StepCache roundtrip."""
import time

import _env

_env.load()

from genblaze_core import Modality  # noqa: E402
from genblaze_core.models.step import Step  # noqa: E402

from kiln.blobs import B2Blobs  # noqa: E402
from kiln.cache import B2StepCache  # noqa: E402
from kiln.config import settings  # noqa: E402

print("Credentials:")
if not _env.report("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_ENDPOINT"):
    raise SystemExit("\nFill the missing values in .env first.")

st = settings()
print(f"\nBucket   : {st.b2_bucket}")
print(f"Endpoint : {st.b2_endpoint}")

blobs = B2Blobs(st.b2_bucket, st.b2_key_id, st.b2_app_key, st.b2_endpoint)

key = f"smoke/{int(time.time())}.txt"
blobs.put(key, b"kiln was here", "text/plain")
assert blobs.get(key) == b"kiln was here", "read-back mismatch"
assert key in blobs.keys("smoke/"), "listing did not include the key"
print(f"\nB2 put/get/list  OK  -> {key}")

# the component the whole submission rests on, against the real bucket
cache = B2StepCache(blobs, prefix="smoke/cache")
step = Step(provider="nvidia", model="flux.1-schnell", prompt="a plumb line", modality=Modality.IMAGE)
assert cache.get(step) is None, "expected a cold miss"
cache.put(step, step)
hit = cache.get(step)
assert hit is not None and hit.prompt == "a plumb line", "cache did not round-trip"
print("B2StepCache      OK  -> miss, put, hit (durable, survives any redeploy)")
