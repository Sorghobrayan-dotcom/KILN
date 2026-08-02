"""HTTP surface over the library and the forge.

The service holds no state: every read and write goes to B2 through the blobs
seam, so this process can be killed, replicated or redeployed without losing a
single approval. That is not an architectural flourish — it is what lets the
step cache stay warm across deploys, which is the point of the project.
"""
from typing import Any, Callable, Protocol

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from kiln.blobs import Blobs
from kiln.library import Library


class Generator(Protocol):
    """Produces assets for a brief. The API never learns which provider ran."""

    def __call__(self, project: str, description: str, count: int, kind: str) -> list[dict]: ...


class _State:
    """Wired once at start-up by main, or by tests with fakes."""

    blobs: Blobs
    generate: Generator
    token: str = "dev"
    savings: Callable[[], dict] | None = None
    roster: Callable[[], list[dict]] | None = None
    #: turns a Genblaze manifest URL back into a bucket key, so the provenance
    #: view can read the manifest the sink wrote
    manifest_key_from_url: Callable[[str], str | None] | None = None


STATE = _State()
app = FastAPI(title="Kiln", description="Assets with a memory.")


def _auth(token: str | None) -> None:
    if token != STATE.token:
        raise HTTPException(status_code=401, detail="bad or missing X-Kiln-Token")


def _library(project: str) -> Library:
    return Library(STATE.blobs, project)


class BriefIn(BaseModel):
    project: str = Field(min_length=1)
    description: str = Field(min_length=1)
    count: int = Field(default=4, ge=1, le=12)
    kind: str = Field(default="sketch", min_length=1)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "savings": STATE.savings() if STATE.savings else None,
        "kinds": STATE.roster() if STATE.roster else [],
    }


@app.get("/api/kinds")
def kinds() -> dict[str, Any]:
    """What this deployment can make, and what each missing one would need."""
    return {"kinds": STATE.roster() if STATE.roster else []}


@app.post("/api/briefs")
def create_brief(brief: BriefIn, x_kiln_token: str | None = Header(default=None)):
    _auth(x_kiln_token)
    try:
        results = STATE.generate(brief.project, brief.description, brief.count, brief.kind)
    except KeyError as exc:
        # an unconfigured kind is the operator's problem, not a server fault
        raise HTTPException(status_code=400, detail=str(exc).strip("'")) from exc

    library = _library(brief.project)
    for r in results:
        library.record(
            r["asset_id"],
            prompt=r["prompt"], model=r["model"], provider=r["provider"],
            url=r["url"], sha256=r["sha256"],
            kind=r.get("kind"), modality=r.get("modality"),
            manifest_uri=r.get("manifest_uri"),
            score=r.get("score"), reasons=r.get("reasons"),
        )

    served = sum(1 for r in results if r.get("cached"))
    failed = sum(1 for r in results if r.get("failed"))
    summary = (f"{len(results)} asset(s) — {served} served from B2, "
               f"{len(results) - served - failed} generated")
    if failed:
        summary += f", {failed} failed"

    return {
        "results": results,
        "served_from_cache": served,
        "failed": failed,
        "savings": STATE.savings() if STATE.savings else None,
        # the sentence the whole demo turns on
        "summary": summary + ".",
    }


@app.get("/api/projects/{project}/staging")
def staging(project: str):
    return {"assets": _library(project).staging()}


@app.post("/api/projects/{project}/assets/{asset}/approve")
def approve(project: str, asset: str, x_kiln_token: str | None = Header(default=None)):
    _auth(x_kiln_token)
    _library(project).approve(asset)
    return {"ok": True, "asset": asset, "state": "approved"}


@app.post("/api/projects/{project}/assets/{asset}/reject")
def reject(project: str, asset: str, x_kiln_token: str | None = Header(default=None)):
    _auth(x_kiln_token)
    _library(project).reject(asset)
    return {"ok": True, "asset": asset, "state": "rejected"}


@app.post("/api/projects/{project}/publish")
def publish(project: str, x_kiln_token: str | None = Header(default=None)):
    _auth(x_kiln_token)
    return _library(project).publish()


@app.get("/api/projects/{project}/assets/{asset}/provenance")
def provenance(project: str, asset: str):
    """The library entry, plus the Genblaze manifest that backs it.

    Kiln's index says who approved an asset and what version it shipped in.
    Genblaze's manifest says how it was made: provider, model, prompt, params,
    timestamps, and a canonical hash over all of it. Neither is the whole
    answer, so this hands back both, and says plainly when the manifest cannot
    be read rather than pretending there is nothing to show.
    """
    import json

    entry = next(
        (a for a in _library(project).staging() if a["asset"] == asset),
        None,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no asset {asset} in {project}")

    manifest: dict | None = None
    note: str | None = None
    uri = entry.get("manifest_uri")

    if not uri:
        note = "this run predates manifest capture"
    elif STATE.manifest_key_from_url is None:
        note = "no storage backend configured to resolve the manifest"
    else:
        key = STATE.manifest_key_from_url(uri)
        raw = STATE.blobs.get(key) if key else None
        if raw is None:
            note = f"manifest not readable at {uri}"
        else:
            try:
                manifest = json.loads(raw.decode("utf-8"))
            except ValueError:
                note = "manifest is present but not valid JSON"

    return {"asset": entry, "manifest": manifest, "manifest_note": note}


@app.get("/api/projects/{project}/versions/{version}/manifest")
def manifest(project: str, version: int):
    found = _library(project).manifest(version)
    if found is None:
        raise HTTPException(status_code=404, detail=f"no version {version} in {project}")
    return found


@app.get("/files/{path:path}")
def files(path: str):
    """Serve a blob straight out of B2, so the UI never needs a credential."""
    import mimetypes

    data = STATE.blobs.get(path)
    if data is None:
        raise HTTPException(status_code=404, detail=path)
    return Response(
        content=data, media_type=mimetypes.guess_type(path)[0] or "application/octet-stream"
    )


class _RevalidatingStatic(StaticFiles):
    """Static files that must be revalidated, not served blind from cache.

    A redeploy changes app.js while index.html keeps its name, so a browser
    holding the old script pairs new markup with stale code and the page
    misbehaves in ways nobody can reproduce. ``no-cache`` does not disable
    caching — it requires a conditional request, so an unchanged file still
    comes back 304 and costs nothing.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def mount_static(directory: str = "static") -> None:
    """Mounted last, so /api and /files always win over the catch-all."""
    app.mount("/", _RevalidatingStatic(directory=directory, html=True), name="static")
