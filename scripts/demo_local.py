"""The whole of Kiln, end to end, with no key and no network.

Runs a real Genblaze Pipeline through the local provider, twice, against the
B2StepCache. The second run must not draw anything: that is the claim the
submission is built on, and here it is checked rather than asserted.
"""
import time

import _env

_env.load()

from genblaze_core import KeyStrategy, LoggingTracer, Modality, Pipeline  # noqa: E402
from genblaze_core.storage.sink import ObjectStorageSink  # noqa: E402

from kiln.blobs import MemoryBlobs  # noqa: E402
from kiln.cache import B2StepCache  # noqa: E402
from kiln.forge import harvest  # noqa: E402
from kiln.library import Library  # noqa: E402
from kiln.local_provider import LocalImageProvider  # noqa: E402
from kiln.memory_backend import MemoryBackend  # noqa: E402

PROMPTS = [
    "NPC portrait: Martha, keeper of the house, monochrome engraving",
    "NPC portrait: Elijah, the one who waits, monochrome engraving",
    "NPC portrait: the stranger at the gate, monochrome engraving",
]

blobs = MemoryBlobs()
backend = MemoryBackend()
cache = B2StepCache(blobs, prefix="providence/cache")
library = Library(blobs, "providence")
provider = LocalImageProvider()
sink = ObjectStorageSink(backend, prefix="providence", key_strategy=KeyStrategy.CONTENT_ADDRESSABLE)


def run(prompt: str):
    result = (
        Pipeline("kiln")
        .cache(cache)
        .tracer(LoggingTracer())
        .step(provider, model="kiln-local-1", prompt=prompt, modality=Modality.IMAGE)
        .run(sink=sink, raise_on_failure=False)
    )
    return harvest(result, prompt, provider.name)


print("=== pass 1: cold ===")
t0 = time.time()
for p in PROMPTS:
    f = run(p)
    library.record(f.asset_id, prompt=f.prompt, model=f.model, provider=f.provider,
                   url=f.url, sha256=f.sha256, score=8, reasons="local demo")
    print(f"  drawn   {f.asset_id[:12]}  cached={f.cached}")
cold = time.time() - t0

print("\n=== pass 2: same briefs, the cache should answer ===")
t0 = time.time()
hits = 0
for p in PROMPTS:
    f = run(p)
    hits += bool(f.cached)
    print(f"  served  {f.asset_id[:12]}  cached={f.cached}")
warm = time.time() - t0

print("\n=== curation ===")
staged = library.staging()
print(f"  staged        : {len(staged)}")
library.approve(staged[0]["asset"])
library.approve(staged[1]["asset"])
library.reject(staged[2]["asset"])
manifest = library.publish()
print(f"  approved      : 2, rejected: 1")
print(f"  published v{manifest['version']} with {len(manifest['assets'])} asset(s)")
print(f"  manifest key  : providence/v{manifest['version']}/manifest.json")

print("\n=== verdict ===")
print(f"  cold pass : {cold:.2f}s")
print(f"  warm pass : {warm:.2f}s   cache hits: {hits}/{len(PROMPTS)}")
print(f"  blobs in store: {len(blobs.keys())}")
assert hits == len(PROMPTS), f"expected every step cached, got {hits}"
assert len(manifest["assets"]) == 2, "only approved assets may ship"
print("\n  OK. Full pipeline, zero network, zero cost.")
