"""Raster surfaces sampled on the model grid (docs/SPEC.md, sections 10.1 and 10.2).

The value of a cell is the mean, over the cell area, of the bilinear interpolant
of the raster, computed with the midpoint rule on n × n sub-cells, where
n = ceil(2 · cell size / pixel size). For cells smaller than a pixel n = 1, so
the value is the bilinear interpolation at the cell centre. The method does not
depend on grid rotation and is exact for surfaces varying linearly in space.

Coverage is strict. A cell has no value, and is reported, if any of its sample
points falls outside the raster or inside a nodata pixel. Nodata neighbours are
left out of the interpolation stencil, so a raster clipped to the domain keeps
its values up to the edge. Nothing is extrapolated beyond valid pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import rasterio
from rasterio.errors import RasterioError
from rasterio.windows import Window, from_bounds

from phrear.errors import GeometryError
from phrear.events import Problem
from phrear.grid.structured import FloatArray, StructuredGeometry

MAX_SAMPLES_PER_SIDE = 16
_CHUNK_ROWS = 64


@dataclass(frozen=True)
class SampledSurface:
    path: str
    values: FloatArray
    """Shape (nrow, ncol); NaN where the raster gives no value."""
    pixel_size: float
    samples_per_side: int
    warnings: tuple[Problem, ...] = ()


def _bilinear(band: npt.NDArray[np.float64], col_f: FloatArray, row_f: FloatArray) -> FloatArray:
    """Bilinear interpolation at fractional pixel positions (pixel centres at k + 0.5).

    A point has a value only if the pixel containing it is valid. Nodata neighbours
    are dropped from the stencil and the remaining weights renormalised, so cells
    along the edge of a raster clipped to the domain keep their value.
    """
    nrows, ncols = band.shape
    pi = np.floor(row_f).astype(np.int64)
    pj = np.floor(col_f).astype(np.int64)
    inside = (pi >= 0) & (pi < nrows) & (pj >= 0) & (pj < ncols)
    own = np.full(col_f.shape, np.nan)
    own[inside] = band[pi[inside], pj[inside]]

    u = np.clip(col_f - 0.5, 0.0, ncols - 1.0)
    v = np.clip(row_f - 0.5, 0.0, nrows - 1.0)
    j0 = np.minimum(np.floor(u).astype(np.int64), max(ncols - 2, 0))
    i0 = np.minimum(np.floor(v).astype(np.int64), max(nrows - 2, 0))
    j1 = np.minimum(j0 + 1, ncols - 1)
    i1 = np.minimum(i0 + 1, nrows - 1)
    fu, fv = u - j0, v - i0
    total = np.zeros(col_f.shape)
    weight = np.zeros(col_f.shape)
    for i, j, w in (
        (i0, j0, (1 - fu) * (1 - fv)),
        (i0, j1, fu * (1 - fv)),
        (i1, j0, (1 - fu) * fv),
        (i1, j1, fu * fv),
    ):
        z = band[i, j]
        ok = ~np.isnan(z)
        total += np.where(ok, z * w, 0.0)
        weight += np.where(ok, w, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        value = total / weight
    return np.where(np.isnan(own) | (weight <= 0), np.nan, value)


def sample_surface(
    path: Path, label: str, geometry: StructuredGeometry, epsg: int
) -> SampledSurface:
    """Mean of the raster over each grid cell; ``label`` is the path shown to the user."""
    if not path.is_file():
        raise GeometryError("geometry.raster_missing", path=label)
    warnings: list[Problem] = []
    try:
        dataset = rasterio.open(path)
    except RasterioError as exc:
        raise GeometryError("geometry.raster_unreadable", path=label, detail=str(exc)) from exc
    with dataset:
        if dataset.crs is None:
            warnings.append(
                Problem.from_code("geometry.raster_no_crs", {"path": label, "epsg": epsg})
            )
        elif dataset.crs.to_epsg() != epsg:
            raise GeometryError(
                "geometry.raster_crs", path=label, raster_crs=str(dataset.crs), epsg=epsg
            )
        transform = dataset.transform
        pixel = math.sqrt(abs(transform.a * transform.e - transform.b * transform.d))
        per_side = min(MAX_SAMPLES_PER_SIDE, max(1, math.ceil(2 * geometry.cell_size / pixel)))

        # read only the window covering the grid, with a margin of two pixels
        cx, cy = geometry.corners()
        window = from_bounds(cx.min(), cy.min(), cx.max(), cy.max(), transform=transform)
        window = window.round_offsets(op="floor").round_lengths(op="ceil")
        col_off = max(0, int(window.col_off) - 2)
        row_off = max(0, int(window.row_off) - 2)
        width = min(dataset.width, int(window.col_off + window.width) + 2) - col_off
        height = min(dataset.height, int(window.row_off + window.height) + 2) - row_off
        if width <= 0 or height <= 0:
            nan = np.full((geometry.nrow, geometry.ncol), np.nan)
            return SampledSurface(label, nan, pixel, per_side, tuple(warnings))
        band = dataset.read(1, window=Window(col_off, row_off, width, height), masked=True).astype(
            np.float64
        )
        data = np.asarray(band.filled(np.nan), dtype=np.float64)

    inverse = ~transform
    values = np.empty((geometry.nrow, geometry.ncol), dtype=np.float64)
    for start in range(0, geometry.nrow, _CHUNK_ROWS):
        stop = min(geometry.nrow, start + _CHUNK_ROWS)
        x0, y0 = geometry.world(np.array(0.0), np.array(float(stop)))
        sub = StructuredGeometry(
            stop - start, geometry.ncol, geometry.cell_size, float(x0), float(y0), geometry.angrot
        )
        x, y = sub.sample_points(per_side)
        col_f = inverse.a * x + inverse.b * y + inverse.c - col_off
        row_f = inverse.d * x + inverse.e * y + inverse.f - row_off
        z = _bilinear(data, col_f, row_f)
        values[start:stop] = z.mean(axis=-1)  # NaN if any sample has no value
    return SampledSurface(label, values, pixel, per_side, tuple(warnings))
