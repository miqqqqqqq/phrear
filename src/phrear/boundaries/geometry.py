"""Intersection of features with the cells of a DIS grid (docs/SPEC.md, section 12).

Points go to the cell that contains them; lines to every cell they cross, with the
length inside the cell; polygons to every cell they overlap, with the covered
fraction of the cell area. Cells are closed: a line running along a cell edge
belongs to the cells on both sides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import shapely

from phrear.grid.structured import StructuredGeometry

_MIN_LENGTH = 1e-6
"""Lines shorter than this inside a cell (m) only touch it."""


@dataclass(frozen=True)
class LinePiece:
    row: int
    col: int
    length: float
    """Length of the line inside the cell, m."""
    chainage: float
    """Chainage of the midpoint of the piece along the line, m."""


@dataclass(frozen=True)
class AreaPiece:
    row: int
    col: int
    fraction: float
    """Fraction of the cell area covered by the polygon."""
    centroid_inside: bool


def _linear(geometry: shapely.Geometry) -> shapely.Geometry:
    """The linear part of an intersection that may also contain points."""
    if shapely.get_type_id(geometry) == 7:  # GeometryCollection
        parts = [g for g in shapely.get_parts(geometry) if shapely.get_dimensions(g) == 1]
        return shapely.multilinestrings(parts) if parts else shapely.LineString()
    return geometry


class CellIndex:
    def __init__(self, geometry: StructuredGeometry) -> None:
        self.geometry = geometry
        self.polygons = geometry.cell_polygons().ravel()
        self.tree = shapely.STRtree(self.polygons)
        x, y = geometry.centers()
        self._cx, self._cy = x.ravel(), y.ravel()

    def _rc(self, index: int) -> tuple[int, int]:
        row, col = divmod(int(index), self.geometry.ncol)
        return row, col

    def point_cell(self, x: float, y: float) -> tuple[int, int] | None:
        """(row, col) of the cell containing the point, None outside the grid."""
        g = self.geometry
        u, v = g.local(np.array([x]), np.array([y]))
        col = math.floor(float(u[0]) / g.cell_size)
        row = g.nrow - 1 - math.floor(float(v[0]) / g.cell_size)
        if 0 <= row < g.nrow and 0 <= col < g.ncol:
            return row, col
        return None

    def line_pieces(self, line: shapely.Geometry) -> list[LinePiece]:
        """Cells crossed by a single-part line, ordered by chainage."""
        index = self.tree.query(line, predicate="intersects")
        if index.size == 0:
            return []
        pieces = shapely.intersection(self.polygons[index], line)
        lengths = shapely.length(pieces)
        keep = lengths > _MIN_LENGTH
        result: list[LinePiece] = []
        for i, piece, length in zip(index[keep], pieces[keep], lengths[keep], strict=True):
            mid = shapely.line_interpolate_point(_linear(piece), 0.5, normalized=True)
            row, col = self._rc(i)
            result.append(LinePiece(row, col, float(length), float(line.project(mid))))
        return sorted(result, key=lambda p: (p.chainage, p.row, p.col))

    def area_pieces(self, polygon: shapely.Geometry) -> list[AreaPiece]:
        """Cells overlapped by a polygon, in row-major order."""
        index = np.sort(self.tree.query(polygon, predicate="intersects"))
        if index.size == 0:
            return []
        shapely.prepare(polygon)
        areas = shapely.area(shapely.intersection(self.polygons[index], polygon))
        fractions = areas / self.geometry.cell_size**2
        inside = shapely.contains_xy(polygon, self._cx[index], self._cy[index])
        result: list[AreaPiece] = []
        for i, fraction, centroid in zip(index, fractions, inside, strict=True):
            if fraction > 0.0:
                row, col = self._rc(i)
                result.append(AreaPiece(row, col, float(min(fraction, 1.0)), bool(centroid)))
        return result
