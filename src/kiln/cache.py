"""A Genblaze StepCache that lives in Backblaze B2.

Genblaze ships a disk-backed StepCache. On any container platform that cache
dies with the container, and two workers never share it, so the same prompt
gets paid for again after every redeploy and on every replica. Kiln implements
the same contract against B2: durable, shared, and indifferent to how many
times the service restarts.

Nothing here reimplements Genblaze. The cache key comes from Genblaze's own
``step_cache_key``, so a Kiln cache and a disk cache agree on what "the same
step" means; only the medium changes.
"""
import json
import logging
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from genblaze_core.models.step import Step
from genblaze_core.pipeline.cache import step_cache_key

from kiln.blobs import Blobs

logger = logging.getLogger(__name__)

#: Stamped into ``Step.metadata`` when this cache served the step.
HIT_MARKER = "kiln_cache_hit"


def was_cache_hit(step: Step) -> bool:
    return bool((step.metadata or {}).get(HIT_MARKER))


def _is_unreadable(step: Step) -> bool:
    """True if any asset's bytes can no longer be fetched.

    A durable asset carries an http(s) URL written by the sink, and is fine. A
    file:// URL means the upload never happened — usually because the transfer
    failed after the step was already cached — so the bytes sit in a temp
    directory that the next process will not find.

    The test is whether the file is still *there*, not whether the URL is local:
    a deployment with no sink at all keeps its assets on disk quite legitimately,
    and refusing those would disable the cache for the whole offline path.
    """
    for asset in step.assets or []:
        url = asset.url or ""
        if not url.startswith("file://"):
            continue
        path = Path(url2pathname(urlparse(url).path))
        if not path.exists():
            return True
    return False


class B2StepCache:
    """Duck-compatible with ``genblaze_core.pipeline.cache.StepCache``."""

    def __init__(self, blobs: Blobs, prefix: str = "cache") -> None:
        self._blobs = blobs
        self._prefix = prefix.rstrip("/")
        self._corruption_count = 0
        self._hits = 0
        self._misses = 0
        self._stale = 0

    @property
    def corruption_count(self) -> int:
        """Entries that were present but unreadable. A climbing count means a
        Step schema change stranded old entries, not that B2 is failing."""
        return self._corruption_count

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def stale(self) -> int:
        """Entries discarded for pointing at a local path — a failed upload."""
        return self._stale

    def _key(self, step: Step, tenant_id: str | None) -> str:
        return f"{self._prefix}/{step_cache_key(step, tenant_id)}.json"

    def get(self, step: Step, tenant_id: str | None = None) -> Step | None:
        raw = self._blobs.get(self._key(step, tenant_id))
        if raw is None:
            self._misses += 1
            return None
        try:
            hit = Step.model_validate(json.loads(raw.decode("utf-8")))
        except Exception as exc:
            # a corrupt entry must read as a miss, never as an outage
            self._corruption_count += 1
            logger.warning("Cache entry unreadable (treating as miss): %s", exc)
            return None

        if _is_unreadable(hit):
            # A step is cached before its assets are transferred, so a run whose
            # upload failed leaves an entry pointing at a temp file that is gone
            # by the next process. Replaying it breaks that prompt forever, so
            # treat it as a miss and let the run happen again.
            self._stale += 1
            logger.warning("Cache entry points at a file that no longer exists; regenerating")
            return None

        # Genblaze returns a cached Step verbatim: no flag, no tracer event, so a
        # hit is invisible to whoever called run(). Kiln stamps it here, because
        # "this cost nothing" is a thing the user is entitled to be told.
        self._hits += 1
        hit.metadata = {**(hit.metadata or {}), HIT_MARKER: True}
        return hit

    def put(self, step: Step, result: Step, tenant_id: str | None = None) -> None:
        self._blobs.put(
            self._key(step, tenant_id),
            result.model_dump_json().encode("utf-8"),
            "application/json",
        )

    def clear(self) -> None:
        raise NotImplementedError(
            "Kiln never clears the cache: an asset you already paid for stays paid for."
        )
