"""A small synthetic site shared by grid, parameter and build tests.

Domain 2000 m × 1500 m, cells of 100 m (15 rows × 20 columns), two units:
1 "copertura" from 50 m to 40 m, pinching out (zero thickness) for x > X0 + 1500;
2 "acquifero" from 40 m to 0 m, split into two sublayers. Three layers in total.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

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


__all__ = ["BOTTOM_1", "BOTTOM_2", "CELL", "DOMAIN", "TOP", "X0", "Y0", "build_site"]
