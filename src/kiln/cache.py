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

from genblaze_core.models.step import Step
from genblaze_core.pipeline.cache import step_cache_key

from kiln.blobs import Blobs

logger = logging.getLogger(__name__)


class B2StepCache:
    """Duck-compatible with ``genblaze_core.pipeline.cache.StepCache``."""

    def __init__(self, blobs: Blobs, prefix: str = "cache") -> None:
        self._blobs = blobs
        self._prefix = prefix.rstrip("/")
        self._corruption_count = 0

    @property
    def corruption_count(self) -> int:
        """Entries that were present but unreadable. A climbing count means a
        Step schema change stranded old entries, not that B2 is failing."""
        return self._corruption_count

    def _key(self, step: Step, tenant_id: str | None) -> str:
        return f"{self._prefix}/{step_cache_key(step, tenant_id)}.json"

    def get(self, step: Step, tenant_id: str | None = None) -> Step | None:
        raw = self._blobs.get(self._key(step, tenant_id))
        if raw is None:
            return None
        try:
            return Step.model_validate(json.loads(raw.decode("utf-8")))
        except Exception as exc:
            # a corrupt entry must read as a miss, never as an outage
            self._corruption_count += 1
            logger.warning("Cache entry unreadable (treating as miss): %s", exc)
            return None

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
