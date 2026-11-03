"""Registry of the exporters of run results (docs/SPEC.md, section 21).

An exporter writes one product of a completed run into its folder, from the
run files and the manifest only, so that the export describes the run even if
the project changed afterwards.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from phrear.errors import Localized
from phrear.results.netcdf import HEADS_NC, write_heads

Writer = Callable[[Path, dict[str, Any], datetime], Path]


@dataclass(frozen=True)
class Exporter:
    name: str
    label: Localized
    format: str
    filename: str
    """Name of the file written in the run folder."""
    write: Writer = field(repr=False)


#: Registered exporters; ``heads`` is the default of ``phrear export``.
EXPORTERS: dict[str, Exporter] = {
    "heads": Exporter(
        "heads",
        Localized("Carichi per layer e per tempo", "Heads per layer and time"),
        "NetCDF UGRID",
        HEADS_NC,
        write_heads,
    )
}


def register(exporter: Exporter) -> None:
    """Add an exporter (used by later milestones and extensions)."""
    if exporter.name in EXPORTERS:
        raise ValueError(f"exporter {exporter.name!r} already registered")
    EXPORTERS[exporter.name] = exporter
