"""The entry point must import where no server will ever be started.

Vercel imports app.py to reach the ASGI callable and never runs uvicorn, so
uvicorn is not installed there. A module-level `import uvicorn` therefore takes
down the whole application before any of its own code runs — which is exactly
what happened, twice, in two different files.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# runs in a subprocess so the blocked import cannot leak into the test session
_WITHOUT_UVICORN = """
import builtins, sys
_real = builtins.__import__
def _blocked(name, *a, **k):
    if name == "uvicorn":
        raise ModuleNotFoundError("No module named 'uvicorn'")
    return _real(name, *a, **k)
builtins.__import__ = _blocked

import importlib.util
spec = importlib.util.spec_from_file_location("entry", {path!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.app
# a working wiring gives a FastAPI instance; the standard-library fallback
# gives a plain coroutine function, and that means something failed to import
print(type(app).__name__)
"""


def _import_without_uvicorn(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _WITHOUT_UVICORN.format(path=str(path))],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def test_app_py_imports_and_wires_without_uvicorn():
    result = _import_without_uvicorn(ROOT / "app.py")
    assert result.returncode == 0, result.stderr[-800:]
    # the wiring announces its storage and kinds on the way through, so only
    # the last line is the answer
    verdict = result.stdout.strip().splitlines()[-1]
    assert verdict == "FastAPI", (
        "app.py fell back to the bare ASGI diagnosis, which means something in "
        f"the wiring still needs uvicorn:\n{result.stderr[-800:]}"
    )


def test_no_module_level_uvicorn_import_anywhere_a_platform_loads():
    """scripts/ is exempt: those files are only ever run as a local server."""
    offenders = []
    for path in [ROOT / "app.py", *(ROOT / "src").rglob("*.py")]:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith(("import uvicorn", "from uvicorn")):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, (
        "uvicorn imported at module level in: " + ", ".join(offenders)
        + " — move it inside `if __name__ == '__main__':`"
    )
