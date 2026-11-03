"""A small synthetic site shared by grid, parameter and build tests.

Domain 2000 m × 1500 m, cells of 100 m (15 rows × 20 columns), two units:
1 "copertura" from 50 m to 40 m, pinching out (zero thickness) for x > X0 + 1500;
2 "acquifero" from 40 m to 0 m, split into two sublayers. Three layers in total.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pyogrio
import shapely

from phrear.project import Project, gpkg

from .grid.conftest import X0, Y0, plane, write_raster

TOP = plane(0.0, 0.0, 50.0)
BOTTOM_1 = lambda x, y: np.where(x > X0 + 1500, 50.0, 40.0)  # noqa: E731
BOTTOM_2 = plane(0.0, 0.0, 0.0)
DOMAIN = shapely.box(X0 + 500, Y0 + 500, X0 + 2500, Y0 + 2000)
CELL = 100.0


def build_site(root: Path) -> Project:
    project = Project.create(
        root, name="Sito", start=datetime(2020, 1, 1), end=datetime(2021, 1, 1)
    )
    project.config.grid.cell_size_m = CELL
    project.save()
    write_raster(root / "rasters" / "s0.tif", TOP)
    write_raster(root / "rasters" / "s1.tif", BOTTOM_1)
    write_raster(root / "rasters" / "s2.tif", BOTTOM_2)
    frame = gpd.GeoDataFrame(
        {"name": ["dominio"], "active": [True]}, geometry=[DOMAIN], crs="EPSG:7791"
    )
    pyogrio.write_dataframe(
        frame, project.gpkg_path, layer="domain", append=True, promote_to_multi=True
    )
    with gpkg.connect(project.gpkg_path) as conn:
        conn.executemany(
            'INSERT INTO "hydro_units" (position, name, sublayers, convertible) '
            "VALUES (?, ?, ?, ?)",
            [(1, "copertura", 1, 1), (2, "acquifero", 2, 0)],
        )
        conn.executemany(
            'INSERT INTO "surfaces" (surface_index, raster_path) VALUES (?, ?)',
            [(0, "rasters/s0.tif"), (1, "rasters/s1.tif"), (2, "rasters/s2.tif")],
        )
    return project


#: Valid parameters of the site: unit 1 convertible, unit 2 confined.
VALID: dict[int, list[tuple[str, float, str]]] = {
    1: [("kh", 1e-4, "m/s"), ("anisotropy", 0.1, ""), ("ss", 1e-4, "1/m"), ("sy", 15.0, "%")],
    2: [("kh", 50.0, "m/d"), ("kv", 5.0, "m/d"), ("ss", 1e-5, "1/m"), ("ne", 0.2, "")],
}

AddParam = Callable[..., int]


def unit_fid(project: Project, position: int) -> int:
    with gpkg.connect(project.gpkg_path) as conn:
        row = conn.execute(
            'SELECT fid FROM "hydro_units" WHERE position = ?', (position,)
        ).fetchone()
    return int(row[0])


def gpkg_blob(geometry: shapely.Geometry, srs_id: int = 7791) -> bytes:
    """GeoPackage geometry blob without envelope, little endian."""
    header = b"GP" + bytes([0, 0x01]) + struct.pack("<i", srs_id)
    wkb: bytes = shapely.to_wkb(geometry, byte_order=1)
    return header + wkb


def insert(
    project: Project, layer: str, geometry: shapely.Geometry | None = None, **fields: Any
) -> int:
    """Insert a row (a feature if ``geometry`` is given); returns its fid."""
    values = dict(fields)
    if geometry is not None:
        values[gpkg.GEOMETRY_COLUMN] = gpkg_blob(geometry)
    names = ", ".join(f'"{k}"' for k in values)
    marks = ", ".join("?" for _ in values)
    with gpkg.connect(project.gpkg_path) as conn:
        cursor = conn.execute(
            f'INSERT INTO "{layer}" ({names}) VALUES ({marks})', tuple(values.values())
        )
        return int(cursor.lastrowid or 0)


__all__ = [
    "BOTTOM_1",
    "BOTTOM_2",
    "CELL",
    "DOMAIN",
    "TOP",
    "VALID",
    "X0",
    "Y0",
    "AddParam",
    "build_site",
    "gpkg_blob",
    "insert",
    "unit_fid",
]
