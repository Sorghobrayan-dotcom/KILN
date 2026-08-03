"""Entry point for Vercel.

Vercel runs ASGI applications directly, so there is no server to start here.
It looks for a module under `api/` and serves whatever `app` it exports.

Importing `kiln.main` is what wires everything: it reads the environment, picks
B2 or memory, builds the forge and mounts the static files. Nothing contacts a
provider or a bucket during that import, which matters more on a serverless
platform than anywhere else, because it runs on every cold start.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import kiln.main  # noqa: E402,F401  (its import performs the wiring)
from kiln.api import app  # noqa: E402

__all__ = ["app"]
