"""One real voice line and one real sound effect, through Genblaze, into B2.

Then the same brief again: it must cost nothing, because the cache is in the
bucket. That second pass is the claim the whole submission rests on.
"""
import time

import _env

_env.load()

from genblaze_core import LoggingTracer, Modality, Pipeline  # noqa: E402
from genblaze_elevenlabs import ElevenLabsSFXProvider, ElevenLabsTTSProvider  # noqa: E402

from kiln.blobs import B2Blobs  # noqa: E402
from kiln.cache import B2StepCache  # noqa: E402
from kiln.config import settings  # noqa: E402
from kiln.forge import b2_sink, harvest  # noqa: E402

print("Credentials:")
if not _env.report("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_ENDPOINT", "ELEVENLABS_API_KEY"):
    raise SystemExit("\nFill the missing values in .env first.")

st = settings()
blobs = B2Blobs(st.b2_bucket, st.b2_key_id, st.b2_app_key, st.b2_endpoint)
cache = B2StepCache(blobs, prefix="smoke/audio-cache")
sink = b2_sink(st)

JOBS = [
    (ElevenLabsTTSProvider(api_key=st.elevenlabs_api_key), "eleven_flash_v2_5",
     "It is written. You will not pass this gate tonight."),
    (ElevenLabsSFXProvider(api_key=st.elevenlabs_api_key), "eleven_text_to_sound_v2",
     "heavy wooden gate creaking shut, stone hall reverb"),
]


def run(provider, model, prompt):
    result = (
        Pipeline("kiln-audio")
        .cache(cache)
        .tracer(LoggingTracer())
        .step(provider, model=model, prompt=prompt, modality=Modality.AUDIO)
        .run(sink=sink, timeout=180, raise_on_failure=False)
    )
    return harvest(result, prompt, provider.name)


for label in ("cold", "warm"):
    print(f"\n--- {label} pass ---")
    t0 = time.time()
    for provider, model, prompt in JOBS:
        try:
            f = run(provider, model, prompt)
            print(f"  {f.provider:16s} cached={str(f.cached):5s} sha={f.sha256[:12]}")
            print(f"      url      {f.url}")
            print(f"      manifest {f.manifest_uri}")
        except Exception as exc:
            print(f"  {provider.name:16s} FAILED: {str(exc)[:180]}")
    print(f"  elapsed {time.time() - t0:.1f}s")

print(f"\ncache: {cache.hits} hits, {cache.misses} misses")
