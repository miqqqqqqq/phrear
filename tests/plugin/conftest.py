"""The plugin package is importable without QGIS for its Qt-free parts."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from phrear import cli

REPO = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO / "qgis_plugin"
PLUGIN = PLUGIN_ROOT / "phrear_qgis"
for path in (PLUGIN_ROOT, REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(scope="session")
def schema() -> dict[str, Any]:
    """The schema document as the plugin receives it from ``phrear --json schema``."""
    stdout = io.BytesIO()
    assert cli.main(["--json", "schema"], stdout=stdout) == 0
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    data: dict[str, Any] = next(e for e in events if e["event"] == "result")["data"]
    return data
