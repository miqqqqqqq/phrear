"""Export of the model grid as a GeoPackage layer, to inspect it in QGIS."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pyogrio

from phrear.errors import ResultsError
from phrear.grid.model_grid import ModelGrid


def export_grid(model_grid: ModelGrid, path: Path, epsg: int) -> int:
    """Write one polygon per column with top, bottoms, thicknesses and IDOMAIN.

    Rows and columns are 1-based as in MF6. Returns the number of features.
    """
    g = model_grid.geometry
    rows, cols = np.meshgrid(np.arange(1, g.nrow + 1), np.arange(1, g.ncol + 1), indexing="ij")
    data: dict[str, np.ndarray] = {
        "row": rows.ravel(),
        "col": cols.ravel(),
        "top": model_grid.top.ravel(),
    }
    upper = model_grid.top
    for k in range(model_grid.nlay):
        lower = model_grid.botm[k]
        data[f"botm_{k + 1}"] = lower.ravel()
        data[f"thick_{k + 1}"] = (upper - lower).ravel()
        data[f"idomain_{k + 1}"] = model_grid.idomain[k].ravel()
        upper = lower
    if model_grid.dem is not None:
        data["dem"] = np.where(np.isnan(model_grid.dem), np.nan, model_grid.dem).ravel()
    frame = gpd.GeoDataFrame(data, geometry=list(g.cell_polygons().ravel()), crs=f"EPSG:{epsg}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            path.unlink()
        except PermissionError as exc:  # Windows: the file is open, e.g. as a QGIS layer
            raise ResultsError("results.file_locked", path=str(path)) from exc
    pyogrio.write_dataframe(frame, path, layer="cells", driver="GPKG")
    return len(frame)
