"""Entry point. One file, two platforms.

Vercel's Python runtime looks for a top-level `app` in this file and serves it.
Hugging Face Spaces runs `python app.py` and proxies port 7860, which the
`__main__` block below handles.

**`app` is bound by a plain top-level import, and must stay that way.** Vercel
reads this file statically to find the ASGI application, so wrapping the import
in a try/except hides it: the build fails with "does not define a top-level app
FastAPI instance" even though the code would run perfectly.

**uvicorn is imported inside `__main__` on purpose.** At module level it breaks
Vercel, where a server is never started and uvicorn is not installed: the import
fails before anything else runs, and the failure has nothing to do with Kiln.

Importing `kiln.main` performs the wiring: environment, B2 or memory, forge,
static files. Nothing contacts a provider or a bucket during that import, so a
cold start costs import time and no more.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import kiln.main  # noqa: E402,F401  (its import performs the wiring)
from kiln.api import app  # noqa: E402

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")),
                log_level="warning")
