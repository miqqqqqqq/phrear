"""The locked environment provides the MODFLOW 6 version pinned in pixi.toml."""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _pinned_mf6_version() -> str:
    manifest = tomllib.loads((REPO_ROOT / "pixi.toml").read_text(encoding="utf-8"))
    spec = manifest["dependencies"]["modflow6"]
    match = re.fullmatch(r"==(\d+\.\d+\.\d+)", spec)
    assert match, f"modflow6 must be pinned exactly in pixi.toml, found {spec!r}"
    return match.group(1)


@pytest.mark.engine
def test_mf6_executable_matches_pinned_version() -> None:
    exe = shutil.which("mf6")
    assert exe is not None, "mf6 not on PATH: run the tests with `pixi run test`"
    result = subprocess.run([exe, "-v"], capture_output=True, text=True, check=True)
    # Linux prints "mf6: 6.8.1", Windows prints "bin\mf6.EXE: 6.8.1".
    match = re.search(r":\s*(\d+\.\d+\.\d+)\s*$", result.stdout, flags=re.MULTILINE)
    assert match is not None, f"unexpected `mf6 -v` output: {result.stdout!r}"
    assert match.group(1) == _pinned_mf6_version()
