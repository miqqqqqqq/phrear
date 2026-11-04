"""Phrear plugin for QGIS 4: groundwater modelling with MODFLOW 6.

Copyright (C) 2026 Michele. Licensed under the GNU General Public License,
version 2 or (at your option) any later version; see LICENSE.

The plugin contains no modelling logic: it runs the Phrear core (``phrear``
command line, EUPL-1.2) in its own environment and reads its JSON events.
"""

from __future__ import annotations

from typing import Any


def classFactory(iface: Any) -> Any:
    from .plugin import PhrearPlugin

    return PhrearPlugin(iface)
