"""Entry point for Vercel.

Vercel runs ASGI applications directly, so there is no server to start here. It
looks for a module under `api/` and serves whatever `app` it exports.

Importing `kiln.main` is what wires everything: it reads the environment, picks
B2 or memory, builds the forge and mounts the static files. Nothing contacts a
provider or a bucket during that import, which matters more on a serverless
platform than anywhere else, because it runs on every cold start.

If that wiring fails, this module still exports an app. A deployment whose
runtime logs are three clicks away should be able to say what went wrong over
HTTP, rather than returning an opaque 500 to every request including the one
that would have explained it.
"""
import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

try:
    import kiln.main  # noqa: F401  (its import performs the wiring)
    from kiln.api import app
except Exception:  # pragma: no cover - only ever runs on a broken deploy
    _TRACE = traceback.format_exc()
    print(_TRACE, file=sys.stderr, flush=True)

    from fastapi import FastAPI

    app = FastAPI(title="Kiln (failed to start)")

    @app.get("/{path:path}")
    def _explain(path: str):
        return {
            "ok": False,
            "error": "Kiln could not be wired at import time",
            "traceback": _TRACE.splitlines()[-12:],
            "cwd": os.getcwd(),
            "root": _ROOT,
            "root_contents": sorted(os.listdir(_ROOT))[:40],
            "src_on_path": os.path.isdir(os.path.join(_ROOT, "src")),
            "static_present": os.path.isdir(os.path.join(_ROOT, "static")),
        }

__all__ = ["app"]
