"""Sampling raster surfaces on the grid."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phrear.errors import GeometryError
from phrear.geology.surfaces import sample_surface
from phrear.grid.structured import StructuredGeometry

from .conftest import X0, Y0, plane, write_raster

PLANE = plane(0.012, -0.007, 40.0)


@pytest.mark.parametrize("angrot", [0.0, 23.0, 45.0, -60.0])
@pytest.mark.parametrize("cell", [3.0, 10.0, 47.0, 200.0])
def test_linear_surface_is_exact_for_any_rotation_and_cell_size(
    tmp_path: Path, angrot: float, cell: float
) -> None:
    raster = write_raster(tmp_path / "s.tif", PLANE, pixel=10.0)
    # 3 × 4 cells of at most 200 m stay inside the 3 km raster for any rotation
    g = StructuredGeometry(
        nrow=3, ncol=4, cell_size=cell, xorigin=X0 + 1100, yorigin=Y0 + 1100, angrot=angrot
    )
    sampled = sample_surface(raster, "s.tif", g, 7791)
    x, y = g.centers()
    # the mean of a linear field over a square cell is its value at the centre
    np.testing.assert_allclose(sampled.values, PLANE(x, y), atol=2e-5)  # float32 raster
    assert sampled.samples_per_side == min(16, max(1, int(np.ceil(2 * cell / 10.0))))


def test_quadratic_surface_mean_matches_the_analytic_cell_mean(tmp_path: Path) -> None:
    a = 1e-4

    def parabola(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return a * (x - X0) ** 2 + 0.0 * y

    raster = write_raster(tmp_path / "q.tif", parabola, pixel=5.0)
    d = 100.0
    g = StructuredGeometry(nrow=2, ncol=10, cell_size=d, xorigin=X0 + 500, yorigin=Y0 + 500)
    x, _ = g.centers()
    exact = a * ((x - X0) ** 2 + d**2 / 12)  # mean of a·u² over a cell of width d
    sampled = sample_surface(raster, "q.tif", g, 7791).values
    # residual errors: bilinear interpolation (≤ a·px²/4) and midpoint rule on 16 sub-cells
    np.testing.assert_allclose(sampled, exact, atol=a * (5.0**2 + (d / 16) ** 2))


def test_cells_outside_the_raster_or_on_nodata_have_no_value(tmp_path: Path) -> None:
    hole = lambda x, y: (x > X0 + 1000) & (x < X0 + 1200)  # noqa: E731
    raster = write_raster(tmp_path / "h.tif", PLANE, nodata_mask=hole)
    g = StructuredGeometry(nrow=1, ncol=40, cell_size=100.0, xorigin=X0 + 50, yorigin=Y0 + 1000)
    values = sample_surface(raster, "h.tif", g, 7791).values[0]
    x, _ = g.centers()
    centres = x[0]
    touches_hole = (centres + 50 > X0 + 1000) & (centres - 50 < X0 + 1200)
    beyond = centres + 50 > X0 + 3000
    assert np.isnan(values[touches_hole | beyond]).all()
    assert not np.isnan(values[~(touches_hole | beyond)]).any()


def test_raster_clipped_to_the_domain_keeps_values_up_to_the_edge(tmp_path: Path) -> None:
    outside = lambda x, y: x > X0 + 1500  # noqa: E731
    raster = write_raster(tmp_path / "c.tif", PLANE, nodata_mask=outside)
    g = StructuredGeometry(nrow=1, ncol=3, cell_size=500.0, xorigin=X0, yorigin=Y0 + 1000)
    values = sample_surface(raster, "c.tif", g, 7791).values[0]
    assert not np.isnan(values).any()


def test_wrong_crs_is_an_error_and_missing_crs_a_warning(tmp_path: Path) -> None:
    g = StructuredGeometry(nrow=2, ncol=2, cell_size=100.0, xorigin=X0 + 100, yorigin=Y0 + 100)
    wrong = write_raster(tmp_path / "w.tif", PLANE, crs="EPSG:7792")
    with pytest.raises(GeometryError) as exc:
        sample_surface(wrong, "w.tif", g, 7791)
    assert exc.value.code == "geometry.raster_crs"
    none = write_raster(tmp_path / "n.tif", PLANE, crs=None)
    sampled = sample_surface(none, "n.tif", g, 7791)
    assert [w.code for w in sampled.warnings] == ["geometry.raster_no_crs"]


def test_missing_raster(tmp_path: Path) -> None:
    g = StructuredGeometry(nrow=1, ncol=1, cell_size=10.0, xorigin=X0, yorigin=Y0)
    with pytest.raises(GeometryError) as exc:
        sample_surface(tmp_path / "none.tif", "rasters/none.tif", g, 7791)
    assert exc.value.code == "geometry.raster_missing"
