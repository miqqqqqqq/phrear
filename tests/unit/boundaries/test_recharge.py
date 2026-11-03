"""Recharge zones: uppermost active cell, covered fraction, overlaps."""

from __future__ import annotations

from datetime import datetime

import pytest
import shapely

from phrear.errors import BoundaryError
from phrear.project import Project

from ..sites import X0, Y0
from .conftest import Build, add_series, add_zone, cell_box, package


def test_zone_over_the_whole_model(valid_site: Project, build: Build) -> None:
    add_zone(valid_site, shapely.box(X0, Y0, X0 + 3000, Y0 + 3000))
    rch = package(build(), "rch")
    cells = {a.cell[1:]: a for a in rch.assignments}
    assert len(cells) == len(rch.assignments) == 300
    # uppermost active cell: layer 1 in the west, layer 2 where unit 1 pinches out
    assert {a.cell[0] for a in rch.assignments if a.cell[2] <= 9} == {0}
    assert {a.cell[0] for a in rch.assignments if a.cell[2] >= 10} == {1}
    assert {a.mult for a in rch.assignments} == {1.0}
    assert [a.forcing.constant for a in rch.assignments] == pytest.approx([0.001] * 300)  # m/d
    assert rch.warnings == ()


def test_partly_covered_cell_takes_the_fraction(valid_site: Project, build: Build) -> None:
    x0, y0, _, y1 = cell_box(7, 4).bounds
    add_zone(valid_site, shapely.box(x0, y0, x0 + 25.0, y1))
    (assignment,) = package(build(), "rch").assignments
    assert assignment.cell == (0, 7, 4)
    assert assignment.mult == pytest.approx(0.25)


def test_zone_outside_the_model(valid_site: Project, build: Build) -> None:
    add_zone(valid_site, shapely.box(X0, Y0, X0 + 300, Y0 + 300))
    rch = package(build(), "rch")
    assert rch.assignments == ()
    assert [w.code for w in rch.warnings] == ["bc.zone_outside"]


def test_overlapping_zones(valid_site: Project, build: Build) -> None:
    add_zone(valid_site, shapely.union_all([cell_box(7, 4), cell_box(7, 5)]))
    add_zone(valid_site, shapely.union_all([cell_box(7, 5), cell_box(7, 6)]))
    rch = package(build(), "rch")
    assert len(rch.assignments) == 4
    assert [w.code for w in rch.warnings] == ["bc.zone_overlap"]
    assert "10000 m²" in rch.warnings[0].message.it


def test_overlap_outside_the_model_is_ignored(valid_site: Project, build: Build) -> None:
    add_zone(valid_site, shapely.box(X0, Y0, X0 + 800, Y0 + 800))
    add_zone(valid_site, shapely.box(X0, Y0, X0 + 400, Y0 + 400))
    assert package(build(), "rch").warnings[-1].code == "bc.zone_outside"


def test_recharge_from_a_series(valid_site: Project, build: Build) -> None:
    add_series(valid_site, "R", "velocity", "mm/giorno", [(datetime(2020, 1, 1), 2.0)])
    add_zone(valid_site, cell_box(7, 4), rate=None, series_id="R")
    (assignment,) = package(build(), "rch").assignments
    assert assignment.forcing.steady == pytest.approx(0.002)


@pytest.mark.parametrize(
    ("fields", "code"),
    [({"rate": None}, "bc.value_missing"), ({"rate_unit": None}, "bc.unit_missing")],
)
def test_invalid_zones(
    valid_site: Project, build: Build, fields: dict[str, None], code: str
) -> None:
    add_zone(valid_site, cell_box(7, 4), **fields)
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == code
