"""Intersection of points, lines and polygons with the grid cells."""

from __future__ import annotations

import numpy as np
import pytest
import shapely

from phrear.boundaries.geometry import CellIndex
from phrear.grid.structured import StructuredGeometry


@pytest.mark.parametrize("angrot", [0.0, 30.0, -60.0])
def test_point_cell_at_cell_centres(angrot: float) -> None:
    geometry = StructuredGeometry(nrow=4, ncol=6, cell_size=10.0, xorigin=100.0, yorigin=200.0,
                                  angrot=angrot)  # fmt: skip
    index = CellIndex(geometry)
    x, y = geometry.centers()
    for row in range(4):
        for col in range(6):
            assert index.point_cell(float(x[row, col]), float(y[row, col])) == (row, col)
    assert index.point_cell(0.0, 0.0) is None


def test_line_lengths_add_up_and_chainage_grows() -> None:
    geometry = StructuredGeometry(nrow=5, ncol=5, cell_size=10.0, xorigin=0.0, yorigin=0.0,
                                  angrot=20.0)  # fmt: skip
    index = CellIndex(geometry)
    line = shapely.LineString([(3.0, 4.0), (20.0, 35.0)])
    pieces = index.line_pieces(line)
    assert sum(p.length for p in pieces) == pytest.approx(line.length)
    assert np.all(np.diff([p.chainage for p in pieces]) > 0)


def test_area_fractions_add_up() -> None:
    geometry = StructuredGeometry(nrow=5, ncol=5, cell_size=10.0, xorigin=0.0, yorigin=0.0,
                                  angrot=35.0)  # fmt: skip
    index = CellIndex(geometry)
    polygon = shapely.Point(5.0, 25.0).buffer(12.0)
    pieces = index.area_pieces(polygon)
    assert sum(p.fraction for p in pieces) * 100.0 == pytest.approx(polygon.area)
