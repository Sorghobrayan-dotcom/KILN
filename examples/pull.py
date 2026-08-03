"""Pull a sealed Kiln version into a build.

    python examples/pull.py <MANIFEST_URL> --into <DIR>

This file is the consumer side of Kiln, and it is deliberately standalone:
standard library only, no Kiln import, no pip install. Copy it into a build
repository and it works. That is the point. The library lives in Kiln, but the
assets belong to whatever consumes them: a game build, a podcast episode, a
site generator.

Every asset is downloaded into memory, hashed, and compared against the sha256
the manifest promised **before** anything touches disk. One tampered or
truncated byte and the asset is refused, existing files stay intact, and the
exit code is non-zero. This is a build tool, and a build tool has to fail
loudly rather than approximately succeed.

A `kiln-pull.json` record is written next to the assets: which manifest, which
version, when, which files. Provenance travels with the assets instead of
staying behind in the bucket.
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


def verify(data: bytes, sha256: str) -> bool:
    return hashlib.sha256(data).hexdigest() == sha256


def _extension(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    if "." in name:
        return "." + name.rsplit(".", 1)[-1]
    return ".bin"


@dataclass
class Report:
    pulled: list = field(default_factory=list)
    refused: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.refused


def pull(manifest: dict, fetch, dest: Path, source: str = "") -> Report:
    """Download every asset in `manifest` into `dest`, verifying each hash.

    `fetch` is a callable url -> bytes, injected so the logic is testable
    without a network; the CLI wires urllib onto it.
    """
    assets = manifest.get("assets") or []
    if not assets:
        raise ValueError(f"manifest has no assets (project={manifest.get('project')!r})")

    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    report = Report()

    for asset in assets:
        sha = asset.get("sha256", "")
        url = asset.get("url", "")
        if not url or not sha:
            report.refused.append(sha or asset.get("asset", "<unknown>"))
            continue

        data = fetch(url)
        if not verify(data, sha):
            report.refused.append(sha)
            continue

        filename = f"{sha}{_extension(url)}"
        (dest / filename).write_bytes(data)
        report.pulled.append(filename)

    record = {
        "project": manifest.get("project"),
        "version": manifest.get("version"),
        "source": source,
        "pulled_at": time.time(),
        "files": report.pulled,
        "refused": report.refused,
    }
    (dest / "kiln-pull.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return report


def _http_fetch(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:  # noqa: S310, build tool, url is the user's own
        return response.read()


def _load_manifest(location: str) -> dict:
    if location.startswith(("http://", "https://")):
        return json.loads(_http_fetch(location).decode("utf-8"))
    return json.loads(Path(location).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull a sealed Kiln version into a build.")
    parser.add_argument("manifest", help="URL or path of a sealed manifest.json")
    parser.add_argument("--into", required=True, help="target directory for the assets")
    args = parser.parse_args()

    manifest = _load_manifest(args.manifest)
    report = pull(manifest, _http_fetch, Path(args.into), source=args.manifest)

    print(f"{manifest.get('project')} v{manifest.get('version')}: "
          f"{len(report.pulled)} pulled, {len(report.refused)} refused")
    for sha in report.refused:
        print(f"  REFUSED {sha} (hash mismatch or missing url)", file=sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
