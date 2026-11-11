"""
Pytest configuration for svc-accounting backend tests.

- Adds the backend directory to sys.path so `auth`, `models`, `platform` import.
- Preserves the stdlib `platform` module (avoids shadowing by backend/platform/).
- Sets ENVIRONMENT=test for auto-generated JWT keys.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _ensure_stdlib_platform() -> None:
    """Prevent backend/platform from breaking hypothesis (stdlib platform)."""
    mod = sys.modules.get("platform")
    if mod is not None and hasattr(mod, "python_implementation"):
        return

    for candidate in (
        Path(sys.base_prefix) / "Lib" / "platform.py",
        Path(sys.base_prefix) / "lib" / "platform.py",
    ):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("platform", candidate)
            if spec and spec.loader:
                stdlib_platform = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(stdlib_platform)
                sys.modules["platform"] = stdlib_platform
                return


_ensure_stdlib_platform()

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Re-apply after sys.path changes (backend/platform shadows stdlib for pytest/hypothesis).
_ensure_stdlib_platform()

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
