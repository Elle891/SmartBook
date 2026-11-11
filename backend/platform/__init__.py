"""SmartBook platform utilities.

This package intentionally shadows the stdlib ``platform`` *name* on
``PYTHONPATH``. To keep third-party libraries (attrs, jsonschema, mcp, …)
working, we re-export the standard library ``platform`` module API here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_stdlib_platform():
    """Load the real stdlib platform module without going through this package."""
    for candidate in (
        Path(sys.base_prefix) / "Lib" / "platform.py",
        Path(sys.base_prefix) / "lib" / "platform.py",
    ):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_stdlib_platform", candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
    raise ImportError("Could not locate the standard library platform module")


_stdlib = _load_stdlib_platform()

# Re-export common stdlib attributes used by third-party packages.
python_implementation = _stdlib.python_implementation
python_version = _stdlib.python_version
python_version_tuple = _stdlib.python_version_tuple
system = _stdlib.system
machine = _stdlib.machine
processor = _stdlib.processor
platform = _stdlib.platform
uname = _stdlib.uname
node = _stdlib.node
release = _stdlib.release
version = _stdlib.version
architecture = _stdlib.architecture
java_ver = getattr(_stdlib, "java_ver", None)
win32_ver = getattr(_stdlib, "win32_ver", None)
mac_ver = getattr(_stdlib, "mac_ver", None)
libc_ver = getattr(_stdlib, "libc_ver", None)
freedesktop_os_release = getattr(_stdlib, "freedesktop_os_release", None)

__all__ = [
    "python_implementation",
    "python_version",
    "python_version_tuple",
    "system",
    "machine",
    "processor",
    "platform",
    "uname",
    "node",
    "release",
    "version",
    "architecture",
]
