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
from kiln.library import Library
from kiln.rewriter import TasteRewriter, plain_expand
from kiln.taste import Taste


#: kept as a name because tests and callers know it; the logic now lives in
#: rewriter, which owns both the plain and the taste-informed expansion
expand = plain_expand


class Forge:
    """Holds the providers, the cache and the sink for a deployment.

    Providers are built once and reused: each construction opens an HTTP client,
    and rebuilding one per brief would leak connections under any real traffic.
    """

    def __init__(self, blobs: Blobs, settings: Settings, sink=None, chat=None) -> None:
        self._blobs = blobs
        self._settings = settings
        self._sink = sink
        self._providers: dict[str, object] = {}
        self._caches: dict[str, B2StepCache] = {}
        self._rewriter = TasteRewriter(blobs, chat=chat)
        self._last_taste = Taste([], [])

    def provider_for(self, kind: Kind):
        if kind.key not in self._providers:
            self._providers[kind.key] = kind.build(self._settings)
        return self._providers[kind.key]

    def cache_for(self, project: str) -> B2StepCache:
        """One cache namespace per project. Two games never collide, and the
        bucket stays readable to anyone browsing it."""
        if project not in self._caches:
            self._caches[project] = B2StepCache(self._blobs, prefix=f"{project}/cache")
        return self._caches[project]

    @property
    def taste_summary(self) -> str:
        """What the last brief was informed by, for the interface to show."""
        return self._last_taste.summary

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

        # what this project has kept before shapes what it asks for next
        taste = Taste.from_entries(Library(self._blobs, project).staging(), kind=kind.key)
        self._last_taste = taste
        prompts = self._rewriter.prompts(project, kind.key, description, count, taste)

        for prompt in prompts:
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
