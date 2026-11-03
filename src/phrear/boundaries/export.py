"""Export of the boundary cells as a GeoPackage layer, to inspect them in QGIS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import pyogrio

from phrear.boundaries.registry import Boundaries
from phrear.grid.model_grid import ModelGrid

_COLUMNS = (
    "package", "feature_layer", "feature_fid", "boundname", "layer", "row", "col", "mult",
    "constant", "series_id", "activation", "steady",
)  # fmt: skip


def export_boundaries(boundaries: Boundaries, grid: ModelGrid, path: Path, epsg: int) -> int:
    """Write one cell polygon per assignment; returns the number of features.

    Layers, rows and columns are 1-based as in MF6; values are in internal units
    (m, d) and ``mult`` is the MF6 multiplier of the entry.
    """
    polygons = grid.geometry.cell_polygons()
    rows: list[dict[str, Any]] = []
    geometries = []
    for p in boundaries.packages:
        for a in p.assignments:
            k, r, c = a.cell
            f = a.forcing
            rows.append(
                {
                    "package": p.package,
                    "feature_layer": a.ref.layer,
                    "feature_fid": a.ref.fid,
                    "boundname": a.boundname,
                    "layer": k + 1,
                    "row": r + 1,
                    "col": c + 1,
                    "mult": a.mult,
                    "constant": f.constant,
                    "series_id": None if f.series is None else f.series.series_id,
                    "activation": None if f.activation is None else f.activation.isoformat(),
                    "steady": f.steady,
                }
            )
            geometries.append(polygons[r, c])
    frame = gpd.GeoDataFrame(
        rows or {name: [] for name in _COLUMNS}, geometry=geometries, crs=f"EPSG:{epsg}"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    pyogrio.write_dataframe(frame, path, layer="cells", driver="GPKG", geometry_type="Polygon")
    return len(frame)
