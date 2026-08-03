"""Entry point for Vercel.

Vercel serves whatever ASGI `app` this module exports, so there is no server to
start. Importing `kiln.main` performs the wiring: it reads the environment,
picks B2 or memory, builds the forge and mounts the static files. Nothing
contacts a provider or a bucket during that import, which matters more on a
serverless platform than anywhere else because it runs on every cold start.

Two layers of fallback, because a deployment that cannot explain itself costs
more time than the bug it is hiding:

1. If the wiring raises, export a FastAPI app that returns the traceback.
2. If even *that* fails — fastapi missing, dependencies not installed at all —
   export a hand-written ASGI callable that needs nothing but the standard
   library. An earlier deploy returned FUNCTION_INVOCATION_FAILED for every
   request precisely because the fallback itself imported fastapi.
"""
import json
import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))


def _diagnosis(trace: str) -> dict:
    """Everything needed to tell a missing dependency from a missing file."""
    try:
        import importlib.metadata as md

        installed = sorted(d.metadata["Name"] for d in md.distributions())[:60]
    except Exception:
        installed = ["<could not enumerate>"]
    return {
        "ok": False,
        "error": "Kiln could not be wired at import time",
        "traceback": trace.splitlines()[-14:],
        "python": sys.version,
        "cwd": os.getcwd(),
        "root": _ROOT,
        "root_contents": sorted(os.listdir(_ROOT))[:40],
        "src_on_path": os.path.isdir(os.path.join(_ROOT, "src")),
        "static_present": os.path.isdir(os.path.join(_ROOT, "static")),
        "installed": installed,
    }


def _bare_asgi(payload: dict):
    """A minimal ASGI app. No framework, so it cannot fail to import."""
    body = json.dumps(payload, indent=1).encode("utf-8")

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": body})

    return app


try:
    import kiln.main  # noqa: F401  (its import performs the wiring)
    from kiln.api import app
except Exception:  # pragma: no cover - only ever runs on a broken deploy
    _TRACE = traceback.format_exc()
    print(_TRACE, file=sys.stderr, flush=True)
    _INFO = _diagnosis(_TRACE)

    try:
        from fastapi import FastAPI

        app = FastAPI(title="Kiln (failed to start)")

        @app.get("/{path:path}")
        def _explain(path: str):
            return _INFO
    except Exception:
        # dependencies are not installed at all; answer with the standard
        # library alone rather than crashing the invocation
        print("fastapi unavailable; serving bare ASGI diagnosis",
              file=sys.stderr, flush=True)
        app = _bare_asgi(_INFO)

__all__ = ["app"]
