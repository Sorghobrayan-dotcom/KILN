"""Wiring: turns a brief into runs, and runs into what the API returns.

Kept out of api.py so the HTTP layer stays ignorant of Genblaze, and out of
forge.py so the Genblaze layer stays ignorant of HTTP.
"""
from typing import Callable

from genblaze_core import LoggingTracer, Pipeline

from kiln.blobs import Blobs
from kiln.cache import B2StepCache
from kiln.config import Settings
from kiln.forge import ForgeError, harvest
from kiln.kinds import Kind, resolve


def expand(description: str, count: int) -> list[str]:
    """One brief becomes N prompts, deterministically.

    Deterministic on purpose: the cache key is built from the prompt, so a
    randomised expansion would miss its own cache every time and the whole
    premise of the tool would quietly stop working.
    """
    if count == 1:
        return [description]
    return [f"{description} — variant {i + 1} of {count}" for i in range(count)]


class Forge:
    """Holds the providers, the cache and the sink for a deployment.

    Providers are built once and reused: each construction opens an HTTP client,
    and rebuilding one per brief would leak connections under any real traffic.
    """

    def __init__(self, blobs: Blobs, settings: Settings, sink=None) -> None:
        self._blobs = blobs
        self._settings = settings
        self._sink = sink
        self._providers: dict[str, object] = {}
        self._caches: dict[str, B2StepCache] = {}

    def provider_for(self, kind: Kind):
        if kind.key not in self._providers:
            self._providers[kind.key] = kind.build(self._settings)
        return self._providers[kind.key]

    def cache_for(self, project: str) -> B2StepCache:
        """One cache namespace per project, so two games never collide — and so
        the bucket stays readable to a human browsing it."""
        if project not in self._caches:
            self._caches[project] = B2StepCache(self._blobs, prefix=f"{project}/cache")
        return self._caches[project]

    @property
    def savings(self) -> dict:
        """Generations the cache avoided, across every project this process saw."""
        hits = sum(c.hits for c in self._caches.values())
        misses = sum(c.misses for c in self._caches.values())
        return {
            "generations_avoided": hits,
            "generations_paid_for": misses,
            "hit_rate": round(hits / (hits + misses), 3) if hits + misses else 0.0,
        }

    def generate(self, project: str, description: str, count: int, kind_key: str) -> list[dict]:
        kind = resolve(self._settings, kind_key)
        provider = self.provider_for(kind)
        cache = self.cache_for(project)
        provider_name = getattr(provider, "name", type(provider).__name__)
        out: list[dict] = []

        for prompt in expand(description, count):
            pipeline = (
                Pipeline("kiln")
                .cache(cache)
                .tracer(LoggingTracer())
                .step(provider, model=kind.model, prompt=prompt, modality=kind.modality)
            )
            result = pipeline.run(
                **({"sink": self._sink} if self._sink else {}), raise_on_failure=False
            )

            try:
                forged = harvest(result, prompt, provider_name)
            except ForgeError as exc:
                # one bad prompt must not sink the batch: the others still land
                out.append({
                    "asset_id": f"failed:{kind.key}:{abs(hash(prompt))}",
                    "prompt": prompt, "model": kind.model, "provider": provider_name,
                    "kind": kind.key, "modality": str(kind.modality),
                    "url": "", "sha256": "", "cached": False,
                    "score": None, "reasons": f"generation failed: {exc.reason}",
                    "failed": True,
                })
                continue

            out.append({
                "asset_id": forged.asset_id, "prompt": forged.prompt,
                "model": forged.model, "provider": forged.provider,
                "kind": kind.key, "modality": str(kind.modality),
                "url": forged.url, "sha256": forged.sha256,
                "cached": forged.cached,
                "manifest_uri": forged.manifest_uri,
                "score": None, "reasons": None,
            })

        return out
