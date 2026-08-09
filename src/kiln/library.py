"""Per-project curation on top of Genblaze runs.

Genblaze's manifest answers "how was this asset made". It is per run, and a run
knows nothing about the run before it. The library answers the question a game
engine actually asks at build time: "which assets did a human bless, and what
shipped in v3."

State is one JSON document per project in B2. That is deliberate: the service
holds nothing, so it can be redeployed, replicated or destroyed without losing
a decision anyone made.
"""
import json
import time

from kiln.blobs import Blobs

# what a sealed version carries forward to whoever consumes the manifest
_MANIFEST_FIELDS = ("asset", "sha256", "url", "prompt", "provider", "model", "score")


class Library:
    def __init__(self, blobs: Blobs, project: str) -> None:
        self._blobs = blobs
        self._project = project

    # ---- persistence -------------------------------------------------
    @property
    def _index_key(self) -> str:
        return f"{self._project}/index.json"

    def _load(self) -> dict:
        raw = self._blobs.get(self._index_key)
        return json.loads(raw.decode("utf-8")) if raw else {"assets": {}, "version": 0}

    def _save(self, data: dict) -> None:
        self._blobs.put(
            self._index_key, json.dumps(data, indent=2).encode("utf-8"), "application/json"
        )

    # ---- writes ------------------------------------------------------
    def record(self, asset: str, **fields) -> None:
        """Register a generated asset, or update one already known.

        Re-recording is normal: a retry produces better bytes for the same
        logical asset, and the newer record wins without creating a twin.
        """
        data = self._load()
        entry = data["assets"].get(asset, {})
        entry.update(fields)
        entry["asset"] = asset
        entry.setdefault("state", "staged")
        entry.setdefault("recorded_at", time.time())
        data["assets"][asset] = entry
        self._save(data)

    def _set_state(self, asset: str, state: str) -> None:
        data = self._load()
        if asset in data["assets"]:
            data["assets"][asset]["state"] = state
            self._save(data)

    def approve(self, asset: str) -> None:
        self._set_state(asset, "approved")

    def reject(self, asset: str) -> None:
        self._set_state(asset, "rejected")

    # ---- reads -------------------------------------------------------
    def _ordered(self, data: dict) -> list[dict]:
        return sorted(data["assets"].values(), key=lambda e: e["recorded_at"])

    def staging(self) -> list[dict]:
        return [e for e in self._ordered(self._load()) if e["state"] != "published"]

    def entry(self, asset: str) -> dict | None:
        """One asset, whatever state it is in.

        Deliberately not built on staging(), which hides published assets. An
        asset that shipped is precisely the one whose provenance someone wants
        to read, and looking it up in the working list returned 404 for every
        sealed asset.
        """
        return self._load()["assets"].get(asset)

    def manifest(self, version: int) -> dict | None:
        raw = self._blobs.get(f"{self._project}/v{version}/manifest.json")
        return json.loads(raw.decode("utf-8")) if raw else None

    # ---- release -----------------------------------------------------
    def publish(self) -> dict:
        """Seal the approved assets into an immutable version.

        A version is never rewritten. Changing anything means publishing the
        next one, so a build pinned to v2 keeps building the same game.
        """
        data = self._load()
        version = data["version"] + 1

        assets = [
            {k: e.get(k) for k in _MANIFEST_FIELDS}
            for e in self._ordered(data)
            if e["state"] == "approved"
        ]
        for a in assets:
            entry = data["assets"][a["asset"]]
            entry["state"] = "published"
            entry["version"] = version

        manifest = {
            "project": self._project,
            "version": version,
            "sealed_at": time.time(),
            "assets": assets,
        }
        self._blobs.put(
            f"{self._project}/v{version}/manifest.json",
            json.dumps(manifest, indent=2).encode("utf-8"),
            "application/json",
        )
        data["version"] = version
        self._save(data)
        return manifest
