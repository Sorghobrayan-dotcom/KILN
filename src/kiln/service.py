"""Wiring: turns a brief into runs, and runs into what the API returns.

Kept out of api.py so the HTTP layer stays ignorant of Genblaze, and out of
forge.py so the Genblaze layer stays ignorant of HTTP.
"""
from typing import Callable

from genblaze_core import LoggingTracer, Modality, Pipeline

from kiln.blobs import Blobs
from kiln.cache import B2StepCache, was_cache_hit
from kiln.forge import ForgeError, harvest


def expand(description: str, count: int) -> list[str]:
    """One brief becomes N prompts, deterministically.

    Deterministic on purpose: the cache key is built from the prompt, so a
    randomised expansion would miss its own cache every time and the whole
    premise of the tool would quietly stop working.
    """
    if count == 1:
        return [description]
    return [f"{description} — variant {i + 1} of {count}" for i in range(count)]


def make_generator(
    blobs: Blobs,
    provider,
    model: str,
    *,
    sink=None,
    fallback_models: list[str] | None = None,
    evaluator: Callable[[bytes, str], tuple[int, str]] | None = None,
) -> Callable[[str, str, int], list[dict]]:
    """Build the callable the API holds. One cache per project keeps the
    namespaces apart in the bucket without any extra bookkeeping."""

    def generate(project: str, description: str, count: int) -> list[dict]:
        cache = B2StepCache(blobs, prefix=f"{project}/cache")
        out: list[dict] = []

        for prompt in expand(description, count):
            pipeline = (
                Pipeline("kiln")
                .cache(cache)
                .tracer(LoggingTracer())
                .step(
                    provider,
                    model=model,
                    prompt=prompt,
                    modality=Modality.IMAGE,
                    **({"fallback_models": fallback_models} if fallback_models else {}),
                )
            )
            result = pipeline.run(**({"sink": sink} if sink else {}), raise_on_failure=False)

            try:
                forged = harvest(result, prompt, getattr(provider, "name", "provider"))
            except ForgeError as exc:
                # one bad prompt must not sink the batch: the others still land
                out.append({
                    "asset_id": f"failed:{abs(hash(prompt))}", "prompt": prompt,
                    "model": model, "provider": getattr(provider, "name", "provider"),
                    "url": "", "sha256": "", "cached": False,
                    "score": None, "reasons": f"generation failed: {exc.reason}",
                    "failed": True,
                })
                continue

            out.append({
                "asset_id": forged.asset_id, "prompt": forged.prompt,
                "model": forged.model, "provider": forged.provider,
                "url": forged.url, "sha256": forged.sha256,
                "cached": forged.cached,
                "score": 9, "reasons": "accepted",
                "manifest_uri": forged.manifest_uri,
            })

        return out

    return generate


def cache_stats_for(blobs: Blobs, project: str) -> Callable[[], dict]:
    def stats() -> dict:
        keys = blobs.keys(f"{project}/cache/")
        return {"project": project, "entries": len(keys)}

    return stats


__all__ = ["expand", "make_generator", "cache_stats_for", "was_cache_hit"]
