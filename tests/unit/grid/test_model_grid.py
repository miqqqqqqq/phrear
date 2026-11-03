"""Model grid built from a project: layering, pass-through cells, checks."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pyogrio
import pytest
import shapely

from phrear.errors import GeometryError, GridError
from phrear.grid.export import export_grid
from phrear.grid.model_grid import build_model_grid, isolated_cells
from phrear.project import Project, gpkg
from phrear.project.config import Dem

from ..sites import BOTTOM_2
from .conftest import X0, Y0, plane, write_raster


@pytest.fixture
def project(site: Project) -> Project:
    return site


def test_layers_units_and_elevations(project: Project) -> None:
    mg = build_model_grid(project)
    g = mg.geometry
    assert (mg.nlay, g.nrow, g.ncol) == (3, 15, 20)
    assert mg.layer_unit == (1, 2, 2)
    active = mg.idomain[2] != 0
    assert active.sum() == 300  # the domain covers 15 × 20 cells of 100 m
    x, _ = g.centers()
    pinched = active & (x > X0 + 1500)
    # the step of surface 1 at x = X0 + 1500 is spread over one pixel by the bilinear
    # interpolation; cells away from it are exact
    left = active & (x < X0 + 1400)
    np.testing.assert_allclose(mg.top[active], 50.0)
    np.testing.assert_allclose(mg.botm[0][left], 40.0)
    np.testing.assert_allclose(mg.botm[1][left], 20.0)  # half of unit 2
    np.testing.assert_allclose(mg.botm[2][active], 0.0)
    # unit 1 has zero thickness where pinched: pass-through, unit 2 stays active
    assert (mg.idomain[0][pinched] == -1).all()
    assert (mg.idomain[0][active & ~pinched] == 1).all()
    assert (mg.idomain[1:][:, active] == 1).all()
    assert [w.code for w in mg.warnings] == ["geometry.thin_unit"]
    summary = mg.summary()
    assert summary["layers"][0]["pass_through"] == int(pinched.sum())


def test_flopy_grid_is_consistent(project: Project) -> None:
    mg = build_model_grid(project)
    fg = mg.flopy_grid()
    x, y = mg.geometry.centers()
    np.testing.assert_allclose(fg.xcellcenters, x, atol=1e-6)
    np.testing.assert_allclose(fg.ycellcenters, y, atol=1e-6)
    assert fg.nlay == mg.nlay


def test_area_rule_activates_more_edge_cells(project: Project) -> None:
    project.config.grid.cell_size_m = 300.0
    by_centroid = (build_model_grid(project).idomain[2] != 0).sum()
    project.config.grid.activation = "area"
    project.config.grid.min_area_fraction = 0.1
    by_area = (build_model_grid(project).idomain[2] != 0).sum()
    assert by_area > by_centroid


def test_crossing_surfaces_are_an_error(project: Project) -> None:
    write_raster(project.root / "rasters" / "s1.tif", plane(0.0, 0.0, 55.0))
    with pytest.raises(GeometryError) as exc:
        build_model_grid(project)
    assert exc.value.code == "geometry.surfaces_crossing"
    assert "5" in exc.value.message("it")


def test_raster_not_covering_the_domain_is_an_error(project: Project) -> None:
    write_raster(project.root / "rasters" / "s2.tif", BOTTOM_2, size=1500.0)
    with pytest.raises(GeometryError) as exc:
        build_model_grid(project)
    assert exc.value.code == "geometry.raster_coverage"


def test_unit_positions_and_surface_indices_are_checked(project: Project) -> None:
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute('DELETE FROM "surfaces" WHERE surface_index = 2')
    with pytest.raises(GeometryError) as exc:
        build_model_grid(project)
    assert exc.value.code == "geometry.surfaces_mismatch"
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute('UPDATE "hydro_units" SET position = 3 WHERE position = 2')
    with pytest.raises(GeometryError) as exc:
        build_model_grid(project)
    assert exc.value.code == "geometry.unit_positions"


def test_missing_domain_and_cell_size(project: Project) -> None:
    project.config.grid.cell_size_m = None
    with pytest.raises(GridError) as gerr:
        build_model_grid(project)
    assert gerr.value.code == "grid.cell_size_missing"
    project.config.grid.cell_size_m = 100.0
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute('UPDATE "domain" SET active = 0')
    with pytest.raises(GeometryError) as exc:
        build_model_grid(project)
    assert exc.value.code == "geometry.no_domain"


def test_invalid_domain_is_reported(project: Project) -> None:
    bowtie = shapely.Polygon(
        [(X0 + 600, Y0 + 600), (X0 + 900, Y0 + 900), (X0 + 900, Y0 + 600), (X0 + 600, Y0 + 900)]
    )
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute('DELETE FROM "domain"')
    frame = gpd.GeoDataFrame({"name": ["x"]}, geometry=[bowtie], crs="EPSG:7791")
    pyogrio.write_dataframe(
        frame, project.gpkg_path, layer="domain", append=True, promote_to_multi=True
    )
    with pytest.raises(GeometryError) as exc:
        build_model_grid(project)
    assert exc.value.code == "geometry.domain_invalid"


def test_model_top_above_dem_is_a_warning(project: Project) -> None:
    write_raster(project.root / "rasters" / "dem.tif", plane(0.0, 0.0, 48.0))
    project.config.dem = Dem(raster_path="rasters/dem.tif")
    mg = build_model_grid(project)
    codes = [w.code for w in mg.warnings]
    assert "geometry.top_above_dem" in codes
    assert mg.dem is not None


def test_isolated_cells_are_found_through_pass_through_columns() -> None:
    idomain = np.zeros((3, 3, 3), dtype=np.int64)
    idomain[0, 1, 1] = 1
    idomain[1, 1, 1] = -1
    idomain[2, 1, 1] = 1  # connected to [0, 1, 1] through the pass-through cell
    idomain[2, 0, 0] = 1  # alone
    isolated = isolated_cells(idomain)
    assert isolated.sum() == 1 and isolated[2, 0, 0]


def test_export_writes_one_feature_per_column(project: Project, tmp_path: Path) -> None:
    mg = build_model_grid(project)
    target = tmp_path / "grid.gpkg"
    n = export_grid(mg, target, 7791)
    frame = pyogrio.read_dataframe(target, layer="cells")
    assert n == len(frame) == mg.geometry.ncell
    assert {"row", "col", "top", "botm_1", "thick_3", "idomain_2"} <= set(frame.columns)
