"""Parameters cell by cell: uniform values and zones (ADR 0024)."""

from __future__ import annotations

import math

import numpy as np
import pytest
import shapely

from phrear.checks.inspection import inspect_project
from phrear.errors import ErrorCollector, ParameterError
from phrear.grid.model_grid import ModelGrid, build_model_grid
from phrear.params.cells import UNIFORM, ZONE, assign_cells
from phrear.params.layers import layer_parameters
from phrear.params.values import load_parameters
from phrear.project import Project

from ..sites import insert, unit_fid


def strip(grid: ModelGrid, x_from: float, x_to: float) -> shapely.Geometry:
    """A polygon over the whole height of the grid between two distances from its origin."""
    g = grid.geometry
    x0, y0 = g.xorigin, g.yorigin
    return shapely.box(x0 + x_from, y0 - 10.0, x0 + x_to, y0 + g.nrow * g.cell_size + 10.0)


def add_zone(
    project: Project,
    position: int,
    geometry: shapely.Geometry,
    values: dict[str, tuple[float, str]],
    **cols: object,
) -> int:
    shape = shapely.MultiPolygon([geometry]) if geometry.geom_type == "Polygon" else geometry
    fid = insert(project, "param_zones", shape, unit_id=unit_fid(project, position), **cols)
    for param, (value, unit) in values.items():
        insert(
            project, "param_values", object_type="zone", object_id=fid, param=param,
            value=value, unit=unit,
        )  # fmt: skip
    return fid


def cells_of(project: Project) -> tuple[ModelGrid, object]:
    grid = build_model_grid(project)
    return grid, assign_cells(grid, load_parameters(project))


def test_uniform_values_are_kept_exactly(valid_site: Project) -> None:
    _, cells = cells_of(valid_site)
    aquifer = cells.units[2]  # type: ignore[attr-defined]
    assert np.all(aquifer.fields["kh"].values == 50.0)
    assert np.all(aquifer.fields["kh"].origin == UNIFORM)
    top = cells.units[1]  # type: ignore[attr-defined]
    assert np.all(top.fields["kv"].values == pytest.approx(0.864))  # Kv/Kh = 0.1 of 1e-4 m/s


def test_a_zone_prevails_and_is_averaged_on_partial_cells(valid_site: Project) -> None:
    grid = build_model_grid(valid_site)
    zone = add_zone(
        valid_site, 2, strip(grid, 0.0, 550.0), {"kh": (432.0, "m/d"), "ss": (1e-4, "1/m")}
    )
    cells = assign_cells(grid, load_parameters(valid_site))
    kh, ss = cells.units[2].fields["kh"], cells.units[2].fields["ss"]
    row = grid.geometry.nrow // 2
    assert kh.values[row, :5] == pytest.approx(432.0)
    assert kh.values[row, 6:] == pytest.approx(50.0)
    # half the cell in the zone: geometric mean for K, arithmetic for Ss
    assert kh.values[row, 5] == pytest.approx(math.sqrt(432.0 * 50.0))
    assert ss.values[row, 5] == pytest.approx(0.5 * (1e-4 + 1e-5))
    assert (kh.origin[row, 0], kh.zone[row, 0], kh.sources[row, 0]) == (ZONE, zone, 1)
    assert (kh.sources[row, 5], kh.share[row, 5]) == (2, pytest.approx(0.5))
    assert kh.origin[row, 7] == UNIFORM and kh.zone[row, 7] == 0
    # The sublayers of the unit share the field; the other unit is untouched.
    arrays = layer_parameters(grid, load_parameters(valid_site))
    assert arrays.k[1, row, 5] == arrays.k[2, row, 5] == pytest.approx(math.sqrt(432.0 * 50.0))
    assert np.all(arrays.k[0][grid.idomain[0] > 0] == pytest.approx(8.64))


def test_vertical_k_follows_the_ratio_of_the_zone(valid_site: Project) -> None:
    grid = build_model_grid(valid_site)
    add_zone(valid_site, 1, strip(grid, 0.0, 300.0), {"kh": (1e-3, "m/s")})
    cells = assign_cells(grid, load_parameters(valid_site))
    top = cells.units[1].fields
    row = grid.geometry.nrow // 2
    assert top["kh"].values[row, 0] == pytest.approx(86.4)
    assert top["kv"].values[row, 0] == pytest.approx(8.64)  # unit ratio 0.1 times the zone K


def test_zones_without_a_uniform_value_must_cover_the_active_cells(site: Project) -> None:
    grid = build_model_grid(site)
    for param, value, unit in [("kh", 50.0, "m/d"), ("kv", 5.0, "m/d"), ("ss", 1e-5, "1/m")]:
        insert(site, "param_values", object_type="unit", object_id=unit_fid(site, 2),
               param=param, value=value, unit=unit)  # fmt: skip
    for param, value, unit in [("anisotropy", 0.1, ""), ("ss", 1e-4, "1/m"), ("sy", 0.1, "")]:
        insert(site, "param_values", object_type="unit", object_id=unit_fid(site, 1),
               param=param, value=value, unit=unit)  # fmt: skip
    # The cover unit exists only in the first 1000 m of the grid (it pinches out).
    add_zone(site, 1, strip(grid, 0.0, 500.0), {"kh": (1e-4, "m/s")})
    errors = ErrorCollector(collect=True)
    assign_cells(grid, load_parameters(site), errors)
    assert [e.code for e in errors.errors] == ["params.cells_without_value"]
    expected = int(np.count_nonzero(grid.idomain[0][:, 5:] > 0))
    assert expected > 0
    assert errors.errors[0].fields["n_cells"] == expected
    # A second zone covering the rest completes the unit.
    add_zone(site, 1, strip(grid, 500.0, 5000.0), {"kh": (2e-4, "m/s")})
    errors = ErrorCollector(collect=True)
    assign_cells(grid, load_parameters(site), errors)
    assert errors.errors == []


def test_overlapping_zones_of_a_unit(valid_site: Project) -> None:
    grid = build_model_grid(valid_site)
    add_zone(valid_site, 2, strip(grid, 0.0, 600.0), {"kh": (100.0, "m/d")})
    second = add_zone(valid_site, 2, strip(grid, 500.0, 900.0), {"kh": (200.0, "m/d")})
    add_zone(valid_site, 1, strip(grid, 500.0, 900.0), {"kh": (1e-4, "m/s")})  # other unit: fine
    errors = ErrorCollector(collect=True)
    assign_cells(grid, load_parameters(valid_site), errors)
    assert [e.code for e in errors.errors] == ["params.zones_overlap"]
    assert errors.errors[0].ref is not None and errors.errors[0].ref.fid == second


def test_vertical_k_must_be_given_the_same_way(valid_site: Project) -> None:
    grid = build_model_grid(valid_site)
    add_zone(valid_site, 1, strip(grid, 0.0, 300.0), {"kv": (1e-5, "m/s")})
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.kv_and_anisotropy"


def test_zone_problems(valid_site: Project) -> None:
    grid = build_model_grid(valid_site)
    add_zone(valid_site, 2, strip(grid, 0.0, 300.0), {})
    inactive = add_zone(valid_site, 2, strip(grid, 400.0, 600.0), {"kh": (-1.0, "m/d")}, active=0)
    codes = [w.code for w in load_parameters(valid_site).warnings]
    assert codes == ["params.zone_empty"]  # the inactive zone and its row are left out
    assert inactive > 0
    bowtie = shapely.Polygon([(grid.geometry.xorigin, grid.geometry.yorigin),
                              (grid.geometry.xorigin + 200, grid.geometry.yorigin + 200),
                              (grid.geometry.xorigin + 200, grid.geometry.yorigin),
                              (grid.geometry.xorigin, grid.geometry.yorigin + 200)])  # fmt: skip
    add_zone(valid_site, 2, bowtie, {"kh": (100.0, "m/d")})
    insert(valid_site, "param_zones", shapely.MultiPolygon([strip(grid, 700, 800)]), unit_id=99)
    errors = ErrorCollector(collect=True)
    load_parameters(valid_site, errors)
    assert sorted(e.code for e in errors.errors) == [
        "params.zone_invalid",
        "params.zone_unknown_unit",
    ]


def test_negative_zone_value_is_an_error(valid_site: Project) -> None:
    grid = build_model_grid(valid_site)
    add_zone(valid_site, 2, strip(grid, 0.0, 300.0), {"kh": (-5.0, "m/d")}, name="Lente")
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.not_positive"
    assert "zona «Lente»" in info.value.message("it") and "zone «Lente»" in info.value.message("en")


def test_check_and_arrays_with_zones(valid_site: Project) -> None:
    grid = build_model_grid(valid_site)
    add_zone(valid_site, 2, strip(grid, 0.0, 550.0), {"kh": (432.0, "m/d")})
    ins = inspect_project(valid_site)
    assert ins.passed("params") and ins.cells is not None and ins.layers is not None
    row = grid.geometry.nrow // 2
    assert ins.layers.k[2, row, 5] == pytest.approx(math.sqrt(432.0 * 50.0))
