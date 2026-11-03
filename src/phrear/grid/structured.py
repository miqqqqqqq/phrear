"""Horizontal geometry of a regular, possibly rotated, DIS grid (docs/SPEC.md, section 14).

Conventions follow MF6 DIS: ``xorigin``/``yorigin`` are the lower-left corner of
the grid, ``angrot`` is the counter-clockwise rotation in degrees about it, row 0
is the northernmost row (largest local y) and column 0 the westernmost.

The affine :attr:`StructuredGeometry.transform` maps (column, row) indices of
cell corners to world coordinates, like the geotransform of a raster whose
pixels are the cells.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import shapely
from rasterio.transform import Affine

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class StructuredGeometry:
    nrow: int
    ncol: int
    cell_size: float
    """Square cells, metres."""
    xorigin: float
    yorigin: float
    angrot: float = 0.0

    @property
    def ncell(self) -> int:
        return self.nrow * self.ncol

    @property
    def transform(self) -> Affine:
        t = math.radians(self.angrot)
        c, s, d = math.cos(t), math.sin(t), self.cell_size
        ulx = self.xorigin - self.nrow * d * s
        uly = self.yorigin + self.nrow * d * c
        return Affine(d * c, d * s, ulx, d * s, -d * c, uly)

    def world(self, col: FloatArray, row: FloatArray) -> tuple[FloatArray, FloatArray]:
        """World coordinates of fractional (column, row) positions."""
        t = self.transform
        return t.c + col * t.a + row * t.b, t.f + col * t.d + row * t.e

    def centers(self) -> tuple[FloatArray, FloatArray]:
        """Cell centres, arrays of shape (nrow, ncol)."""
        row, col = np.meshgrid(
            np.arange(self.nrow, dtype=np.float64) + 0.5,
            np.arange(self.ncol, dtype=np.float64) + 0.5,
            indexing="ij",
        )
        return self.world(col, row)

    def sample_points(self, per_side: int) -> tuple[FloatArray, FloatArray]:
        """Midpoints of a per_side × per_side subdivision of every cell.

        Shape (nrow, ncol, per_side**2). Averaging a field over these points is the
        midpoint rule for its mean over the cell.
        """
        offsets = (np.arange(per_side, dtype=np.float64) + 0.5) / per_side
        dr, dc = np.meshgrid(offsets, offsets, indexing="ij")
        row = np.arange(self.nrow, dtype=np.float64)[:, None, None] + dr.ravel()[None, None, :]
        col = np.arange(self.ncol, dtype=np.float64)[None, :, None] + dc.ravel()[None, None, :]
        row = np.broadcast_to(row, (self.nrow, self.ncol, per_side**2))
        col = np.broadcast_to(col, (self.nrow, self.ncol, per_side**2))
        return self.world(col, row)

    def corners(self) -> tuple[FloatArray, FloatArray]:
        """Corner coordinates, arrays of shape (nrow + 1, ncol + 1)."""
        row, col = np.meshgrid(
            np.arange(self.nrow + 1, dtype=np.float64),
            np.arange(self.ncol + 1, dtype=np.float64),
            indexing="ij",
        )
        return self.world(col, row)

    def cell_polygons(self) -> npt.NDArray[np.object_]:
        """Shapely polygons of the cells, array of shape (nrow, ncol)."""
        x, y = self.corners()
        ring = np.stack(
            [
                np.stack([x[:-1, :-1], y[:-1, :-1]], axis=-1),
                np.stack([x[:-1, 1:], y[:-1, 1:]], axis=-1),
                np.stack([x[1:, 1:], y[1:, 1:]], axis=-1),
                np.stack([x[1:, :-1], y[1:, :-1]], axis=-1),
            ],
            axis=2,
        )
        polygons = shapely.polygons(ring.reshape(-1, 4, 2))
        return np.asarray(polygons, dtype=object).reshape(self.nrow, self.ncol)

    def local(self, x: FloatArray, y: FloatArray) -> tuple[FloatArray, FloatArray]:
        """Coordinates in the grid frame: u along rows, v along columns, from the origin."""
        t = math.radians(self.angrot)
        c, s = math.cos(t), math.sin(t)
        dx, dy = x - self.xorigin, y - self.yorigin
        return dx * c + dy * s, -dx * s + dy * c


def covering_geometry(
    domain: shapely.Geometry,
    cell_size: float,
    angrot: float,
    origin: tuple[float, float] | None = None,
) -> StructuredGeometry:
    """Smallest grid with the given cell size and rotation covering the domain.

    Without an explicit origin the lower-left corner is snapped, in the rotated
    frame, to a multiple of the cell size, so that unrotated grids have round
    coordinates.
    """
    t = math.radians(angrot)
    c, s = math.cos(t), math.sin(t)
    xs, ys = shapely.get_coordinates(domain).T
    u, v = xs * c + ys * s, -xs * s + ys * c
    if origin is None:
        u0 = math.floor(u.min() / cell_size) * cell_size
        v0 = math.floor(v.min() / cell_size) * cell_size
        xorigin, yorigin = u0 * c - v0 * s, u0 * s + v0 * c
    else:
        xorigin, yorigin = origin
        u0, v0 = xorigin * c + yorigin * s, -xorigin * s + yorigin * c
    ncol = max(1, math.ceil((u.max() - u0) / cell_size - 1e-9))
    nrow = max(1, math.ceil((v.max() - v0) / cell_size - 1e-9))
    return StructuredGeometry(nrow, ncol, cell_size, xorigin, yorigin, angrot)


def active_by_centroid(
    geometry: StructuredGeometry, domain: shapely.Geometry
) -> npt.NDArray[np.bool_]:
    x, y = geometry.centers()
    return np.asarray(shapely.contains_xy(domain, x, y), dtype=bool)


def area_fractions(geometry: StructuredGeometry, domain: shapely.Geometry) -> FloatArray:
    """Fraction of each cell area inside the domain."""
    polygons = geometry.cell_polygons().ravel()
    shapely.prepare(domain)
    inside = shapely.contains(domain, polygons)
    outside = ~shapely.intersects(domain, polygons)
    fraction = np.where(inside, 1.0, 0.0)
    edge = ~(inside | outside)
    if edge.any():
        cut = shapely.intersection(polygons[edge], domain)
        fraction[edge] = shapely.area(cut) / geometry.cell_size**2
    return fraction.reshape(geometry.nrow, geometry.ncol)
