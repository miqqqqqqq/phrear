"""The MODFLOW 6 executable of the environment."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from phrear.errors import RunError

_VERSION = re.compile(r":\s*(\d+\.\d+\.\d+)\s*$", flags=re.MULTILINE)


def mf6_executable() -> Path:
    """mf6 on PATH, or in the environment of the running interpreter."""
    found = shutil.which("mf6")
    candidates = [
        *([Path(found)] if found else []),
        Path(sys.prefix) / "Library" / "bin" / "mf6.exe",  # conda on Windows
        Path(sys.prefix) / "bin" / "mf6",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RunError("run.engine_not_found")


def engine_version(executable: Path) -> str:
    """Version printed by ``mf6 -v``; Windows prints ``bin\\mf6.EXE: 6.8.1``."""
    output = subprocess.run(
        [str(executable), "-v"], capture_output=True, text=True, check=False
    ).stdout
    match = _VERSION.search(output)
    return match.group(1) if match else "unknown"
