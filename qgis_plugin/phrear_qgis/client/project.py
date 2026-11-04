"""Projects of Phrear as seen by the plugin: folders, new-project rules, layers to load.

A project is a folder with ``project.toml`` and ``model.gpkg`` (docs/SPEC.md,
section 8). The layers and tables of the GeoPackage, their order and their names
come from the schema document of the core (``phrear schema``), never from a copy
in the plugin.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_FILE = "project.toml"
GPKG_FILE = "model.gpkg"
#: Geometry layers are listed points first, then lines, then polygons, so that
#: smaller features are drawn on top of larger ones.
GEOMETRY_ORDER = {"Point": 0, "MultiLineString": 1, "MultiPolygon": 2}


def is_project(folder: Path) -> bool:
    return (folder / PROJECT_FILE).is_file() and (folder / GPKG_FILE).is_file()


def slug(name: str) -> str:
    """A folder name from a project name: ASCII letters, digits, ``_`` and ``-``."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_name).strip("_")
    return cleaned[:60] or "progetto"


def folder_free(folder: Path) -> bool:
    """A new project may go only in a new or empty folder."""
    return not folder.exists() or (folder.is_dir() and not any(folder.iterdir()))


def new_project_problems(
    name: str, parent: Path, folder_name: str, start: date, end: date, crs_authid: str
) -> list[str]:
    """Keys of the messages that explain why the project cannot be created."""
    problems: list[str] = []
    if not name.strip():
        problems.append("name_missing")
    if not parent.is_dir():
        problems.append("parent_missing")
    elif not folder_name.strip() or not folder_free(parent / folder_name):
        problems.append("folder_used")
    if end <= start:
        problems.append("dates_order")
    if epsg_code(crs_authid) is None:
        problems.append("crs_not_epsg")
    return problems


def epsg_code(authid: str) -> int | None:
    match = re.fullmatch(r"EPSG:(\d+)", authid.strip().upper())
    return int(match.group(1)) if match else None


def new_project_args(name: str, folder: Path, start: date, end: date, crs_authid: str) -> list[str]:
    code = epsg_code(crs_authid)
    if code is None:
        raise ValueError(f"not an EPSG code: {crs_authid!r}")
    return [
        "new",
        str(folder),
        "--name",
        name.strip(),
        "--crs",
        str(code),
        "--start",
        start.isoformat(),
        "--end",
        end.isoformat(),
    ]


@dataclass(frozen=True)
class LayerSpec:
    name: str
    """Table name in the GeoPackage."""
    label: str
    geometry: str | None

    @property
    def is_table(self) -> bool:
        return self.geometry is None

    def uri(self, gpkg: Path) -> str:
        return layer_uri(gpkg, self.name)


#: Open option of every project layer. QGIS opens read-only GeoPackage layers in
#: SQLite "nolock" mode, which stops working once an edit session switches the
#: file to WAL journaling: after a save, the other layers of the same GeoPackage
#: can no longer compute their extent ("unable to open database file").
LAYER_OPTION = "option:NOLOCK=NO"


def layer_uri(gpkg: Path | str, table: str) -> str:
    return f"{gpkg}|layername={table}|{LAYER_OPTION}"


def upgraded_uri(source: str) -> str | None:
    """The source of a layer saved before :data:`LAYER_OPTION`, or None if up to date."""
    parts = source.split("|")
    if LAYER_OPTION in parts or not any(p.startswith("layername=") for p in parts):
        return None
    parts = [p for p in parts if not p.upper().startswith("OPTION:NOLOCK=")]
    return "|".join([*parts, LAYER_OPTION])


def _label(entry: dict[str, Any], lang: str) -> str:
    label = entry.get("label") or {}
    return str(label.get(lang) or label.get("en") or entry["name"])


def layer_plan(schema: dict[str, Any], lang: str) -> list[LayerSpec]:
    """Layers with geometry (points, lines, polygons), then tables, in schema order."""
    tables = schema["project"]["tables"]
    specs = [LayerSpec(t["name"], _label(t, lang), t.get("geometry")) for t in tables]
    layers = [s for s in specs if not s.is_table]
    layers.sort(key=lambda s: GEOMETRY_ORDER.get(s.geometry or "", 9))
    return layers + [s for s in specs if s.is_table]


def table_rows(info: dict[str, Any], schema: dict[str, Any], lang: str) -> list[tuple[str, int]]:
    """(label, number of rows) of every table of the project, in schema order."""
    counts: dict[str, int] = info.get("tables", {})
    return [(_label(t, lang), int(counts.get(t["name"], 0))) for t in schema["project"]["tables"]]
