"""One command from a fresh clone to a running app.

    python scripts/setup.py

Creates the virtualenv, installs dependencies, copies .env.example to .env if
it is missing, runs the tests, and prints what is enabled. Deliberately does
not ask for a single credential: Kiln generates real media without one, and a
setup that begins by demanding API keys is a setup most people abandon.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def step(message: str) -> None:
    print(f"\n=== {message} ===", flush=True)


def run(*args: str) -> None:
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"failed: {' '.join(args)}")


def main() -> None:
    if not PY.exists():
        step("Creating the virtual environment")
        run(sys.executable, "-m", "venv", str(VENV))
    else:
        print("Virtual environment already present.")

    step("Installing dependencies")
    run(str(PY), "-m", "pip", "install", "--quiet", "--upgrade", "pip")
    run(str(PY), "-m", "pip", "install", "--quiet", "-r", str(ROOT / "requirements.txt"))

    env = ROOT / ".env"
    if not env.exists():
        shutil.copy(ROOT / ".env.example", env)
        print("\nCreated .env from .env.example. No credentials required to start.")

    step("Running the tests")
    run(str(PY), "-m", "pytest", "-q")

    step("What this configuration can make")
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "scripts"))
    import _env  # noqa: E402

    _env.load()
    from kiln.config import settings  # noqa: E402
    from kiln.kinds import roster  # noqa: E402

    for row in roster(settings()):
        mark = "on " if row["enabled"] else "off"
        print(f"  [{mark}] {row['key']:7s} {row['label']:20s} {row['hint']}")

    print("\nReady. Start it with:")
    print(f"  {PY.relative_to(ROOT)} scripts/dev.py")
    print("Then open http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
