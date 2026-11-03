"""Fixed heads along lines and over areas, with values at stations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
import shapely

from phrear.boundaries.base import Assignment
from phrear.errors import BoundaryError
from phrear.project import Project

from ..sites import X0, Y0, insert
from .conftest import Build, add_area, add_line, add_series, add_station, cell_box, package

LINES, AREAS = "fixed_head_lines", "fixed_head_areas"
# a south-north line in column 0, from y = Y0 + 650 (row 13) to Y0 + 1850 (row 1)
SOUTH = (X0 + 550.0, Y0 + 650.0)
NORTH = (X0 + 550.0, Y0 + 1850.0)


def _line(project: Project, south: dict[str, Any], north: dict[str, Any], **fields: Any) -> int:
    fid = add_line(project, [SOUTH, NORTH], **fields)
    add_station(project, LINES, fid, *SOUTH, name="S", **south)
    add_station(project, LINES, fid, *NORTH, name="N", **north)
    return fid


def _chd(build: Build) -> list[Assignment]:
    return list(package(build(), "chd").assignments)


def _by_cell(assignments: list[Assignment]) -> dict[tuple[int, int, int], Assignment]:
    return {a.cell: a for a in assignments}


def test_heads_are_interpolated_by_chainage(valid_site: Project, build: Build) -> None:
    _line(valid_site, {"value": 30.0}, {"value": 36.0})
    chd = package(build(), "chd")
    cells = _by_cell(list(chd.assignments))
    # rows 1-13 of column 0; layer 1 (40-50 m) is always above the head and stays free
    assert sorted(cells) == [(k, r, 0) for k in (1, 2) for r in range(1, 14)]
    assert chd.warnings == ()
    for row in range(2, 13):  # whole cells: chainage of the centre, 1300 - 100·row
        assert cells[(1, row, 0)].forcing.constant == pytest.approx(36.5 - 0.5 * row)
    assert cells[(2, 13, 0)].forcing.constant == pytest.approx(30.0 + 25.0 / 200.0)
    assert cells[(2, 1, 0)].forcing.constant == pytest.approx(30.0 + 1175.0 / 200.0)
    assert {a.boundname for a in chd.assignments} == {"chdl_1"}


def test_series_at_stations_are_combined_exactly(valid_site: Project, build: Build) -> None:
    add_series(valid_site, "HS", "length", "m",
               [(datetime(2020, 1, 1), 30.0), (datetime(2020, 6, 1), 32.0)])  # fmt: skip
    add_series(valid_site, "HN", "length", "m",
               [(datetime(2020, 1, 1), 36.0), (datetime(2020, 9, 1), 34.0)])  # fmt: skip
    _line(valid_site, {"series_id": "HS"}, {"series_id": "HN"})
    middle = _by_cell(_chd(build))[(1, 7, 0)].forcing  # chainage 600 m, half way
    assert middle.series is not None
    assert middle.series.series_id == "chdl_1@8_1"
    assert middle.series.times == (
        datetime(2020, 1, 1), datetime(2020, 6, 1), datetime(2020, 9, 1), datetime(2021, 1, 1)
    )  # fmt: skip
    assert list(middle.series.values) == pytest.approx([33.0, 34.0, 33.0, 33.0])
    assert middle.steady == pytest.approx(33.0)
    assert middle.activation == datetime(2020, 1, 1)


def test_line_activates_when_all_stations_are_defined(valid_site: Project, build: Build) -> None:
    add_series(valid_site, "HN", "length", "m", [(datetime(2020, 3, 1), 36.0)])
    _line(valid_site, {"value": 30.0}, {"series_id": "HN"})
    chd = _chd(build)
    assert {a.forcing.activation for a in chd} == {datetime(2020, 3, 1)}
    assert {a.forcing.steady for a in chd} == {None}


def test_stepwise_and_linear_stations_cannot_be_mixed(valid_site: Project, build: Build) -> None:
    add_series(valid_site, "HS", "length", "m", [(datetime(2020, 1, 1), 30.0)])
    add_series(valid_site, "HN", "length", "m",
               [(datetime(2020, 1, 1), 36.0), (datetime(2021, 1, 1), 34.0)], "linear")  # fmt: skip
    _line(valid_site, {"series_id": "HS"}, {"series_id": "HN"})
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == "bc.mixed_interpolation"


def test_layers_crossed_by_the_head_are_left_free(valid_site: Project, build: Build) -> None:
    add_series(valid_site, "H", "length", "m",
               [(datetime(2020, 1, 1), 38.0), (datetime(2021, 1, 1), 42.0)], "linear")  # fmt: skip
    fid = add_line(valid_site, [SOUTH, NORTH])
    add_station(valid_site, LINES, fid, *SOUTH, series_id="H")
    chd = package(build(), "chd")
    assert {a.cell[0] for a in chd.assignments} == {1, 2}
    assert [w.code for w in chd.warnings] == ["bc.chd_layers_excluded"]
    assert chd.warnings[0].message.it.startswith("In 13 celle")


def test_head_below_the_lowest_layer(valid_site: Project, build: Build) -> None:
    _line(valid_site, {"value": -5.0}, {"value": 30.0})
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == "bc.head_below_bottom"


@pytest.mark.parametrize(
    ("fields", "layers"), [({}, {0, 1, 2}), ({"top_unit": 2}, {1, 2}), ({"bottom_unit": 1}, {0})]
)
def test_units_affected(
    valid_site: Project, build: Build, fields: dict[str, Any], layers: set[int]
) -> None:
    _line(valid_site, {"value": 45.0}, {"value": 45.0}, **fields)
    assert {a.cell[0] for a in _chd(build)} == layers


def test_invalid_unit_range(valid_site: Project, build: Build) -> None:
    _line(valid_site, {"value": 30.0}, {"value": 30.0}, top_unit=2, bottom_unit=3)
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == "bc.unit_range"


def test_pass_through_cells_get_no_head(valid_site: Project, build: Build) -> None:
    fid = add_line(valid_site, [(X0 + 1750.0, Y0 + 650.0), (X0 + 1750.0, Y0 + 1850.0)])
    add_station(valid_site, LINES, fid, X0 + 1750.0, Y0 + 650.0, value=30.0)
    assert {a.cell[0] for a in _chd(build)} == {1, 2}


def test_part_of_the_line_outside_the_model(valid_site: Project, build: Build) -> None:
    fid = add_line(valid_site, [(X0 + 300.0, Y0 + 1250.0), (X0 + 800.0, Y0 + 1250.0)])
    add_station(valid_site, LINES, fid, X0 + 800.0, Y0 + 1250.0, value=30.0)
    chd = package(build(), "chd")
    assert {a.cell[1:] for a in chd.assignments} == {(7, 0), (7, 1), (7, 2)}
    assert [w.code for w in chd.warnings] == ["bc.line_outside"]
    assert "200 m" in chd.warnings[0].message.it


def test_line_on_the_grid_edge_takes_the_cells_along_it(valid_site: Project, build: Build) -> None:
    fid = add_line(valid_site, [(X0 + 500.0, Y0 + 650.0), (X0 + 500.0, Y0 + 1850.0)])
    add_station(valid_site, LINES, fid, X0 + 500.0, Y0 + 650.0, value=30.0)
    assert {a.cell[1:] for a in _chd(build)} == {(r, 0) for r in range(1, 14)}


def test_line_outside_the_model(valid_site: Project, build: Build) -> None:
    fid = add_line(valid_site, [(X0 + 100.0, Y0 + 100.0), (X0 + 400.0, Y0 + 100.0)])
    add_station(valid_site, LINES, fid, X0 + 100.0, Y0 + 100.0, value=30.0)
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == "bc.outside_active"


def test_station_far_from_its_line(valid_site: Project, build: Build) -> None:
    fid = add_line(valid_site, [SOUTH, NORTH])
    add_station(valid_site, LINES, fid, SOUTH[0] + 300.0, SOUTH[1], value=30.0)
    chd = package(build(), "chd")
    assert [w.code for w in chd.warnings] == ["bc.station_far"]


@pytest.mark.parametrize(
    ("stations", "code"),
    [
        ([], "bc.no_stations"),
        ([{"value": None}], "bc.station_no_value"),
        ([{"value": 30.0}, {"value": 31.0}], "bc.duplicate_chainage"),
        ([{"value": 30.0, "chainage": 5000.0}], "bc.chainage_beyond"),
    ],
)
def test_invalid_stations(
    valid_site: Project, build: Build, stations: list[dict[str, Any]], code: str
) -> None:
    fid = add_line(valid_site, [SOUTH, NORTH])
    for fields in stations:
        add_station(valid_site, LINES, fid, *SOUTH, **fields)
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == code


def test_station_of_an_unknown_feature(valid_site: Project, build: Build) -> None:
    add_station(valid_site, LINES, 99, *SOUTH, value=30.0)
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == "bc.station_unknown_feature"


def test_station_of_an_inactive_feature_is_ignored(valid_site: Project, build: Build) -> None:
    fid = add_line(valid_site, [SOUTH, NORTH], active=0)
    add_station(valid_site, LINES, fid, *SOUTH, value=30.0)
    assert _chd(build) == []


def test_multipart_line(valid_site: Project, build: Build) -> None:
    geometry = shapely.MultiLineString(
        [[SOUTH, (X0 + 550.0, Y0 + 900.0)], [(X0 + 550.0, Y0 + 1200.0), NORTH]]
    )
    fid = insert(valid_site, LINES, geometry, name="L")
    add_station(valid_site, LINES, fid, *SOUTH, value=30.0)
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == "bc.multipart_line"


def test_area_with_uniform_head(valid_site: Project, build: Build) -> None:
    polygon = shapely.union_all([cell_box(r, c) for r in (2, 3, 4) for c in (14, 15, 16)])
    fid = add_area(valid_site, polygon)
    add_station(valid_site, AREAS, fid, *polygon.centroid.coords[0], value=30.0)
    chd = _chd(build)
    # east of the pinch-out: layers 2 (50-25 m) and 3 (25-0 m)
    assert sorted(a.cell for a in chd) == [
        (k, r, c) for k in (1, 2) for r in (2, 3, 4) for c in (14, 15, 16)
    ]
    assert {a.boundname for a in chd} == {"chda_1"}


def test_area_needs_a_single_station(valid_site: Project, build: Build) -> None:
    fid = add_area(valid_site, cell_box(3, 15))
    for value in (30.0, 31.0):
        add_station(valid_site, AREAS, fid, *cell_box(3, 15).centroid.coords[0], value=value)
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == "bc.area_stations"


def test_overlapping_features_keep_the_first(valid_site: Project, build: Build) -> None:
    _line(valid_site, {"value": 30.0}, {"value": 30.0})
    fid = add_area(valid_site, cell_box(7, 0))
    add_station(valid_site, AREAS, fid, *cell_box(7, 0).centroid.coords[0], value=35.0)
    chd = package(build(), "chd")
    cells = _by_cell(list(chd.assignments))
    assert cells[(1, 7, 0)].boundname == "chdl_1"
    assert len(cells) == len(chd.assignments) == 26
    assert [w.code for w in chd.warnings] == ["bc.chd_overlap"]
    assert chd.warnings[0].message.it.startswith("2 celle")


def test_rows_are_unique_per_cell(valid_site: Project, build: Build) -> None:
    _line(valid_site, {"value": 30.0}, {"value": 36.0})
    cells = [a.cell for a in _chd(build)]
    assert len(cells) == len(set(cells))
