"""Entry point for Hugging Face Spaces.

Spaces now bills for the Docker SDK, so this Space runs on the Gradio runtime,
which is free and still does nothing more exotic than run `python app.py` and
proxy port 7860. Kiln is a FastAPI application, so this file starts it there
directly. No Gradio component is created; the SDK choice only picks the base
image and the port contract.

Importing `kiln.main` is what wires the application: it reads the environment,
picks B2 or memory, builds the forge, and mounts the static files. Nothing
contacts a provider or a bucket during that import, which is why the Space is
ready as soon as uvicorn binds.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import uvicorn  # noqa: E402

import kiln.main  # noqa: E402,F401  (its import performs the wiring)
from kiln.api import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")), log_level="warning")
