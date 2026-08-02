"""A genblaze_core StorageBackend backed by in-memory bytes.

Lets the full pipeline (Genblaze + ObjectStorageSink + B2StepCache) run without
B2 credentials, so the cache-hit demo and tests exercise real Genblaze transfer
logic instead of a mock.
"""
import threading
import urllib.parse
from typing import Any

from genblaze_core.storage.base import StorageBackend
from genblaze_core.storage.types import ListPage, ObjectMetadata


class MemoryBackend(StorageBackend):
    """Thread-safe in-memory StorageBackend for offline demos and tests."""

    def __init__(self, *, public_url_base: str | None = "memory://localhost") -> None:
        self._store: dict[str, bytes] = {}
        self._lock = threading.Lock()
        self._public_url_base = public_url_base.rstrip("/") if public_url_base else None

    def put(self, key: str, data: bytes | Any, *,
            content_type: str | None = None,
            metadata: dict | None = None,
            extra_args: dict | None = None) -> str:
        import io

        if hasattr(data, "read"):
            data = data.read()
        with self._lock:
            self._store[key] = data
        return key

    def get(self, key: str = None, **kwargs: Any) -> bytes:
        with self._lock:
            if key not in self._store:
                from genblaze_core.exceptions import StorageError
                raise StorageError(f"key not found: {key}")
            return self._store[key]

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._store

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def get_url(self, key: str, *, expires_in: int = 3600, **kwargs: Any) -> str:
        if self._public_url_base:
            return f"{self._public_url_base}/{urllib.parse.quote(key, safe='/')}"
        return self.get_durable_url(key)

    def get_durable_url(self, key: str) -> str:
        if self._public_url_base:
            return f"{self._public_url_base}/{urllib.parse.quote(key, safe='/')}"
        return f"memory://localhost/{key}"

    def key_from_url(self, url: str) -> str | None:
        if self._public_url_base and url.startswith(self._public_url_base + "/"):
            path = url[len(self._public_url_base) + 1:]
            return urllib.parse.unquote(path)
        if url.startswith("memory://localhost/"):
            path = url[len("memory://localhost/"):]
            return urllib.parse.unquote(path)
        return None

    def list(self, prefix: str = "", *, max_keys: int = 1000,
             continuation_token: str | None = None) -> ListPage:
        import hashlib
        from datetime import datetime, timezone

        from genblaze_core.storage.types import FileEntry

        with self._lock:
            keys = sorted(k for k in self._store if k.startswith(prefix))
            start = int(continuation_token) if continuation_token else 0
            page = keys[start:start + max_keys]
            # last_modified and etag are required by FileEntry; the etag is an
            # md5 hexdigest to match what an S3-compatible store would return.
            now = datetime.now(timezone.utc)
            entries = [
                FileEntry(
                    key=k,
                    size=len(self._store[k]),
                    last_modified=now,
                    etag=hashlib.md5(self._store[k]).hexdigest(),
                )
                for k in page
            ]
        next_token = str(start + max_keys) if start + max_keys < len(keys) else None
        return ListPage(entries=tuple(entries), next_token=next_token)

    def close(self) -> None:
        pass
