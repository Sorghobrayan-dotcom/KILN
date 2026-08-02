"""The one place Kiln talks to Genblaze.

Everything above this file is Kiln's own logic — curation, approval,
versioning — and is tested without a network. Everything below is Genblaze's:
the Pipeline, the canonical manifest, the B2 sink, and our durable
:class:`~kiln.cache.B2StepCache` plugged in through ``Pipeline.cache()``.

Kiln does not reimplement provenance. Genblaze already hashes every asset and
writes a manifest per run; Kiln's job starts one level up, where a run is over
and someone has to decide which of those assets ships.
"""
import re
from dataclasses import dataclass

from kiln.cache import B2StepCache, was_cache_hit
from kiln.config import Settings

# https://s3.eu-central-003.backblazeb2.com -> eu-central-003
_REGION = re.compile(r"^https?://s3\.([a-z0-9-]+)\.backblazeb2\.com/?$")


def region_of(endpoint: str) -> str | None:
    m = _REGION.match(endpoint.strip())
    return m.group(1) if m else None


class ForgeError(RuntimeError):
    """A run finished without producing an asset.

    Carries the provider's own reason and the run id, because "generation
    failed" alone sends you reading logs, while "NVIDIA submit failed
    (transport): read timed out, run c14a3915" sends you to the right place.
    """

    def __init__(self, reason: str, run_id: str | None = None, model: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.run_id = run_id
        self.model = model


@dataclass(frozen=True)
class Forged:
    """What Kiln keeps from a Genblaze run, flattened for the library."""

    asset_id: str
    url: str
    sha256: str
    prompt: str
    provider: str
    model: str
    manifest_uri: str | None
    cached: bool


def b2_sink(st: Settings):
    """Assets and manifests land in B2 under a content-addressable layout, so
    identical bytes occupy one key no matter how many runs produced them."""
    from genblaze_core import KeyStrategy, ObjectStorageSink
    from genblaze_s3 import S3StorageBackend

    backend = S3StorageBackend.for_backblaze(
        st.b2_bucket,
        region=region_of(st.b2_endpoint),
        key_id=st.b2_key_id,
        app_key=st.b2_app_key,
    )
    return ObjectStorageSink(
        backend, prefix="kiln", key_strategy=KeyStrategy.CONTENT_ADDRESSABLE
    )


def build_pipeline(provider, st: Settings, prompt: str, cache: B2StepCache, name: str = "kiln"):
    """One image step, with the durable cache and a fallback chain attached."""
    from genblaze_core import LoggingTracer, Modality, Pipeline

    return (
        Pipeline(name)
        .cache(cache)
        .tracer(LoggingTracer())
        .step(
            provider,
            model=st.image_model,
            prompt=prompt,
            modality=Modality.IMAGE,
            fallback_models=st.fallback_models,
        )
    )


def harvest(result, prompt: str, provider_name: str) -> Forged:
    """Turn a finished Genblaze run into a Forged, or explain why it isn't one.

    Split out from :func:`forge` so the failure paths are testable without a
    provider: a run can fail, or succeed and still carry no asset, and both
    used to surface as an IndexError three frames away from the cause.
    """
    run = result.run
    run_id = getattr(run, "run_id", None)

    if not run.steps:
        raise ForgeError("the run produced no steps at all", run_id)

    step = run.steps[0]
    if not step.assets:
        reason = getattr(step, "error", None) or f"step ended {getattr(step, 'status', 'unknown')} with no asset"
        raise ForgeError(str(reason), run_id, getattr(step, "model", None))

    asset = step.assets[0]
    return Forged(
        asset_id=asset.sha256 or asset.url,
        url=asset.url,
        sha256=asset.sha256 or "",
        prompt=prompt,
        provider=provider_name,
        model=step.model,
        manifest_uri=getattr(result.manifest, "manifest_uri", None),
        cached=was_cache_hit(step),
    )


def forge(provider, st: Settings, prompt: str, cache: B2StepCache, sink, timeout: int = 300) -> Forged:
    result = build_pipeline(provider, st, prompt, cache).run(
        sink=sink, timeout=timeout, raise_on_failure=False
    )
    return harvest(result, prompt, getattr(provider, "name", type(provider).__name__))
