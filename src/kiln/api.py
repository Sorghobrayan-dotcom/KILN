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

    def __call__(self, project: str, description: str, count: int) -> list[dict]: ...


class _State:
    """Wired once at start-up by main, or by tests with fakes."""

    blobs: Blobs
    generate: Generator
    token: str = "dev"
    cache_stats: Callable[[], dict] | None = None


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


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "cache": STATE.cache_stats() if STATE.cache_stats else None}


@app.post("/api/briefs")
def create_brief(brief: BriefIn, x_kiln_token: str | None = Header(default=None)):
    _auth(x_kiln_token)
    results = STATE.generate(brief.project, brief.description, brief.count)

    library = _library(brief.project)
    for r in results:
        library.record(
            r["asset_id"],
            prompt=r["prompt"], model=r["model"], provider=r["provider"],
            url=r["url"], sha256=r["sha256"],
            score=r.get("score"), reasons=r.get("reasons"),
        )

    served = sum(1 for r in results if r.get("cached"))
    return {
        "results": results,
        "served_from_cache": served,
        # the sentence the whole demo turns on
        "summary": f"{len(results)} asset(s) — {served} served from B2, "
                   f"{len(results) - served} generated.",
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


def mount_static(directory: str = "static") -> None:
    """Mounted last, so /api and /files always win over the catch-all."""
    app.mount("/", StaticFiles(directory=directory, html=True), name="static")
