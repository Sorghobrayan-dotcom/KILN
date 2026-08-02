"""Load .env for local scripts.

On Hugging Face Spaces the variables come from Secrets, so this file is
development-only and deliberately dependency-free.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def load(path: Path | None = None) -> None:
    env_file = path or ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def report(*names: str) -> bool:
    """Print which variables are set, never what they contain."""
    ok = True
    for n in names:
        v = os.getenv(n, "")
        filled = bool(v) and not v.startswith("<")
        print(f"  {'OK ' if filled else 'MISSING'}  {n}" + (f"  ({len(v)} chars)" if filled else ""))
        ok = ok and filled
    return ok
