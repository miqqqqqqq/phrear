"""Horizontal DIS geometry: conventions, covering grid, active cells."""

from __future__ import annotations

import flopy
import numpy as np
import pytest
import shapely

from phrear.grid.structured import (
    StructuredGeometry,
    active_by_centroid,
    area_fractions,
    covering_geometry,
)

from .conftest import X0, Y0


@pytest.mark.parametrize("angrot", [0.0, 17.0, -30.0, 90.0])
def test_centres_match_flopy_and_mf6_convention(angrot: float) -> None:
    g = StructuredGeometry(nrow=4, ncol=7, cell_size=25.0, xorigin=X0, yorigin=Y0, angrot=angrot)
    fg = flopy.discretization.StructuredGrid(
        delc=np.full(g.nrow, g.cell_size),
        delr=np.full(g.ncol, g.cell_size),
        xoff=g.xorigin,
        yoff=g.yorigin,
        angrot=angrot,
    )
    x, y = g.centers()
    np.testing.assert_allclose(x, fg.xcellcenters, atol=1e-6)
    np.testing.assert_allclose(y, fg.ycellcenters, atol=1e-6)


def test_lower_left_corner_is_the_origin_and_cells_are_square() -> None:
    g = StructuredGeometry(nrow=3, ncol=5, cell_size=10.0, xorigin=X0, yorigin=Y0, angrot=25.0)
    cx, cy = g.corners()
    assert (cx[-1, 0], cy[-1, 0]) == pytest.approx((X0, Y0))
    areas = shapely.area(g.cell_polygons().ravel())
    np.testing.assert_allclose(areas, 100.0)


def test_covering_grid_snaps_unrotated_origin() -> None:
    domain = shapely.box(X0 + 15, Y0 + 30, X0 + 1015, Y0 + 630)
    g = covering_geometry(domain, 100.0, 0.0)
    assert (g.xorigin, g.yorigin) == (X0, Y0)
    assert (g.nrow, g.ncol) == (7, 11)


@pytest.mark.parametrize("angrot", [0.0, 20.0, -45.0])
def test_covering_grid_contains_the_domain(angrot: float) -> None:
    domain = shapely.Polygon([(X0, Y0), (X0 + 900, Y0 + 200), (X0 + 500, Y0 + 800)])
    g = covering_geometry(domain, 50.0, angrot)
    extent = shapely.union_all(g.cell_polygons().ravel())
    assert extent.buffer(1e-6).contains(domain)


def test_explicit_origin_is_kept() -> None:
    domain = shapely.box(X0 + 15, Y0 + 30, X0 + 1015, Y0 + 630)
    g = covering_geometry(domain, 100.0, 0.0, origin=(X0 + 15, Y0 + 30))
    assert (g.xorigin, g.yorigin, g.ncol, g.nrow) == (X0 + 15, Y0 + 30, 10, 6)


def test_area_fractions_sum_to_the_domain_area() -> None:
    domain = shapely.Polygon([(X0, Y0), (X0 + 930, Y0 + 170), (X0 + 410, Y0 + 770)])
    g = covering_geometry(domain, 50.0, 12.0)
    fractions = area_fractions(g, domain)
    assert fractions.min() >= 0.0 and fractions.max() <= 1.0 + 1e-12
    assert fractions.sum() * 2500.0 == pytest.approx(domain.area, rel=1e-9)


def test_centroid_rule_activates_cells_whose_centre_is_inside() -> None:
    g = StructuredGeometry(nrow=2, ncol=2, cell_size=10.0, xorigin=X0, yorigin=Y0)
    domain = shapely.box(X0, Y0, X0 + 6, Y0 + 20)  # covers the centres of column 0 only
    np.testing.assert_array_equal(active_by_centroid(g, domain), [[True, False], [True, False]])
