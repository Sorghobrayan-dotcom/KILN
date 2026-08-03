"""Entry point. One file, two platforms.

Vercel's Python runtime auto-detects `app.py` at the repository root and serves
whatever ASGI `app` it exports — it does this in preference to anything under
`api/`, which is worth knowing: an earlier deploy failed on every request while
all the diagnostics sat unused in `api/index.py`.

Hugging Face Spaces runs `python app.py` and proxies port 7860, which the
`__main__` block below handles.

**uvicorn is imported inside that block on purpose.** At module level it breaks
Vercel, where a server is never started and uvicorn is not installed: the import
fails before anything else runs, and the failure has nothing to do with Kiln.

Importing `kiln.main` performs the wiring — environment, B2 or memory, forge,
static files. Nothing contacts a provider or a bucket during that import, so a
cold start costs import time and no more.
"""
import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "src"))

try:
    import kiln.main  # noqa: F401  (its import performs the wiring)
    from kiln.api import app
except Exception:  # pragma: no cover - only ever runs on a broken deploy
    _TRACE = traceback.format_exc()
    print(_TRACE, file=sys.stderr, flush=True)

    # A deployment that cannot explain itself costs more time than the bug it
    # hides. This answers with the standard library alone, so it works even
    # when no dependency was installed at all.
    import json

    def _payload() -> bytes:
        try:
            import importlib.metadata as md

            installed = sorted(d.metadata["Name"] for d in md.distributions())[:60]
        except Exception:
            installed = ["<could not enumerate>"]
        return json.dumps({
            "ok": False,
            "error": "Kiln could not be wired at import time",
            "traceback": _TRACE.splitlines()[-14:],
            "python": sys.version,
            "root": _ROOT,
            "root_contents": sorted(os.listdir(_ROOT))[:40],
            "src_on_path": os.path.isdir(os.path.join(_ROOT, "src")),
            "static_present": os.path.isdir(os.path.join(_ROOT, "static")),
            "installed": installed,
        }, indent=1).encode("utf-8")

    _BODY = _payload()

    async def app(scope, receive, send):  # noqa: F811
        if scope["type"] != "http":
            return
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": _BODY})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")),
                log_level="warning")
