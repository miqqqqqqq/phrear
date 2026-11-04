"""The plugin package is importable without QGIS for its Qt-free parts."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO / "qgis_plugin"
PLUGIN = PLUGIN_ROOT / "phrear_qgis"
for path in (PLUGIN_ROOT, REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
