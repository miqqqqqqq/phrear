"""Synthetic rasters and projects for geometry tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import numpy.typing as npt
import rasterio
from rasterio.transform import from_origin

X0, Y0 = 680_000.0, 4_850_000.0  # lower-left corner of the test area
SIZE = 3_000.0  # side of the raster area, m

Field = Callable[[npt.NDArray[np.float64], npt.NDArray[np.float64]], npt.NDArray[np.float64]]


def plane(a: float, b: float, c: float) -> Field:
    """z = c + a·(x - X0) + b·(y - Y0)."""
    return lambda x, y: c + a * (x - X0) + b * (y - Y0)


def write_raster(
    path: Path,
    field: Field,
    *,
    pixel: float = 10.0,
    x0: float = X0,
    y0: float = Y0,
    size: float = SIZE,
    crs: str | None = "EPSG:7791",
    nodata_mask: Callable[[npt.NDArray[np.float64], npt.NDArray[np.float64]], npt.NDArray[np.bool_]]
    | None = None,
) -> Path:
    n = round(size / pixel)
    cols, rows = np.meshgrid(np.arange(n), np.arange(n))
    x = np.asarray(x0 + (cols + 0.5) * pixel, dtype=np.float64)
    y = np.asarray(y0 + size - (rows + 0.5) * pixel, dtype=np.float64)
    z = field(x, y).astype(np.float32)
    nodata = -9999.0
    if nodata_mask is not None:
        z = np.where(nodata_mask(x, y), nodata, z).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=n,
        height=n,
        count=1,
        dtype="float32",
        crs=crs,
        transform=from_origin(x0, y0 + size, pixel, pixel),
        nodata=nodata,
    ) as dst:
        dst.write(z, 1)
    return path
