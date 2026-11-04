"""Export of the parameters cell by cell, with their origin, to inspect them in QGIS.

One feature per cell (layer, row, column), so that QGIS can filter a layer and
colour any parameter. Values are in internal units, with K also in m/s. For each
parameter the origin is the source with the largest share of the cell: the
uniform value of the unit or a zone, whose fid is given.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import numpy.typing as npt
import pyogrio

from phrear.errors import ResultsError
from phrear.grid.model_grid import ModelGrid
from phrear.params.cells import ORIGINS, CellParameters

PARAMS = ("kh", "kv", "ss", "sy", "ne")
SECONDS_PER_DAY = 86400.0


def parameter_frame(grid: ModelGrid, cells: CellParameters, epsg: int) -> gpd.GeoDataFrame:
    g = grid.geometry
    polygons = g.cell_polygons().ravel()
    rows, cols = np.meshgrid(np.arange(1, g.nrow + 1), np.arange(1, g.ncol + 1), indexing="ij")
    columns: dict[str, list[npt.NDArray[np.generic]]] = {}
    geometry: list[object] = []
    names = {u.unit.position: u.unit.name for u in cells.units.values()}

    def add(name: str, values: npt.NDArray[np.generic]) -> None:
        columns.setdefault(name, []).append(values.ravel())

    for layer, position in enumerate(grid.layer_unit):
        unit = cells.units[position]
        n = g.nrow * g.ncol
        add("layer", np.full(n, layer + 1))
        add("row", rows)
        add("col", cols)
        add("unit", np.full(n, position))
        add("unit_name", np.full(n, names[position], dtype=object))
        add("idomain", grid.idomain[layer])
        for param in PARAMS:
            found = unit.fields.get(param)
            if found is None:
                add(param, np.full(n, np.nan))
                add(f"origin_{param}", np.full(n, ORIGINS[0], dtype=object))
                add(f"zone_{param}", np.zeros(n, dtype=np.int64))
                add(f"share_{param}", np.zeros(n))
                continue
            add(param, found.values)
            add(f"origin_{param}", np.vectorize(ORIGINS.get, otypes=[object])(found.origin))
            add(f"zone_{param}", found.zone)
            add(f"share_{param}", np.round(found.share, 4))
        geometry.extend(polygons)
    data = {name: np.concatenate(parts) for name, parts in columns.items()}
    data["kh_ms"] = data["kh"] / SECONDS_PER_DAY
    data["kv_ms"] = data["kv"] / SECONDS_PER_DAY
    return gpd.GeoDataFrame(data, geometry=geometry, crs=f"EPSG:{epsg}")


def export_parameters(grid: ModelGrid, cells: CellParameters, path: Path, epsg: int) -> int:
    """Write ``path`` (layer ``cells``); returns the number of features."""
    frame = parameter_frame(grid, cells, epsg)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            path.unlink()
        except PermissionError as exc:  # Windows: the file is open, e.g. as a QGIS layer
            raise ResultsError("results.file_locked", path=str(path)) from exc
    pyogrio.write_dataframe(frame, path, layer="cells", driver="GPKG")
    return len(frame)
