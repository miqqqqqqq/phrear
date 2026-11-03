"""Content hashes of a project (docs/SPEC.md, sections 3.1, 8.2 and 16).

The hash of the GeoPackage file would change on writes that do not touch the
model (QGIS layer styles, SQLite page layout, WAL). Hashes are therefore taken
on the content:

- each schema table: rows ordered by ``fid``, every column except the system
  timestamps; floats as exact hexadecimal; geometries as canonical WKB
  (GeoPackage header removed, little-endian);
- project.toml: the validated settings, without the software versions;
- rasters: the bytes of each file under ``rasters/``.

Tables outside the schema (``layer_styles``, ``gpkg_*``, R-tree indexes) are ignored.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import shapely

from phrear.project.gpkg import GEOMETRY_COLUMN, blob_wkb, connect
from phrear.project.schema import TABLES, TableDef


def gpkg_blob_to_wkb(blob: bytes) -> bytes:
    """Canonical WKB of a GeoPackage geometry blob (header stripped, little-endian)."""
    geometry = shapely.from_wkb(blob_wkb(blob))
    return bytes(shapely.to_wkb(geometry, byte_order=1, include_srid=False))


def _canonical(value: Any) -> Any:
    if isinstance(value, float):
        return {"f": value.hex()}
    if isinstance(value, bytes):
        return {"g": gpkg_blob_to_wkb(value).hex()}
    return value


def table_hash(conn: sqlite3.Connection, table: TableDef) -> str:
    columns = ["fid"]
    if table.is_layer:
        columns.append(GEOMETRY_COLUMN)
    columns += [f.name for f in table.fields if not f.system]
    select = ", ".join(f'"{c}"' for c in columns)
    digest = hashlib.sha256()
    digest.update(json.dumps(columns).encode("utf-8") + b"\n")
    for row in conn.execute(f'SELECT {select} FROM "{table.name}" ORDER BY fid'):
        line = json.dumps([_canonical(v) for v in row], ensure_ascii=False, separators=(",", ":"))
        digest.update(line.encode("utf-8") + b"\n")
    return digest.hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def settings_hash(settings: dict[str, Any]) -> str:
    """Hash of the validated project.toml settings (software versions excluded)."""
    data = {
        k: v
        for k, v in settings.items()
        if k not in {"software_version_created", "software_version_last_saved"}
    }
    text = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def gpkg_hashes(path: Path, tables: Iterable[TableDef] = TABLES) -> dict[str, str]:
    with connect(path) as conn:
        return {f"model.gpkg/{t.name}": table_hash(conn, t) for t in tables}


def raster_hashes(project_root: Path) -> dict[str, str]:
    rasters = project_root / "rasters"
    if not rasters.is_dir():
        return {}
    return {
        path.relative_to(project_root).as_posix(): file_hash(path)
        for path in sorted(rasters.rglob("*"))
        if path.is_file()
    }


def combined_hash(hashes: dict[str, str]) -> str:
    """One hash summarising a set of component hashes."""
    text = "\n".join(f"{key}={hashes[key]}" for key in sorted(hashes))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "combined_hash",
    "file_hash",
    "gpkg_blob_to_wkb",
    "gpkg_hashes",
    "raster_hashes",
    "settings_hash",
    "table_hash",
]
