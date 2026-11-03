"""Registry, stress period records and time series of the boundaries."""

from __future__ import annotations

from datetime import datetime

import pytest

from phrear.boundaries.base import BoundaryConditionType, PackageInput
from phrear.boundaries.registry import BOUNDARY_TYPES, register
from phrear.errors import Localized
from phrear.project import Project
from phrear.timeline import project_timeline

from .conftest import Build, add_series, add_well, center, package


def test_registered_types() -> None:
    assert list(BOUNDARY_TYPES) == ["wel", "chd", "rch"]
    assert {t.package for t in BOUNDARY_TYPES.values()} == {"wel", "chd", "rch"}
    assert BOUNDARY_TYPES["chd"].layers == ("fixed_head_lines", "fixed_head_areas", "line_stations")


def test_types_cannot_be_registered_twice() -> None:
    clash = BoundaryConditionType(
        "wel", Localized("x", "x"), "wel", (), lambda ctx: PackageInput("wel", "wel", ())
    )
    with pytest.raises(ValueError, match="already registered"):
        register(clash)


def test_empty_project_gives_empty_packages(build: Build) -> None:
    boundaries = build()
    assert [p.bc_type for p in boundaries.packages] == ["wel", "chd", "rch"]
    assert all(p.assignments == () for p in boundaries.packages)
    assert boundaries.ts_names() == {}


def test_records_follow_the_activation_of_each_object(valid_site: Project, build: Build) -> None:
    add_series(valid_site, "Q", "discharge", "m3/d",
               [(datetime(2020, 4, 1), 100.0), (datetime(2020, 8, 1), 200.0)])  # fmt: skip
    add_well(valid_site, *center(7, 4), name="costante", rate=1.0, rate_unit="m3/d")
    add_well(valid_site, *center(7, 14), name="serie", rate=None, series_id="Q")
    boundaries = build()
    wel = package(boundaries, "wel")
    calendar = project_timeline(valid_site).calendar
    names = boundaries.ts_names()
    assert list(names) == ["Q"]
    assert [(p.kind, p.start) for p in calendar.periods] == [
        ("steady", datetime(2020, 1, 1)),
        ("transient", datetime(2020, 1, 1)),
        ("transient", datetime(2020, 4, 1)),
    ]
    steady, first, second = wel.period_records(calendar, names)
    # the series starts after the model start: inactive in the steady period and in
    # the first transient period, then driven by its time series
    assert {r[3] for r in steady} == {r[3] for r in first} == {"well_1"}
    assert {r[1] for r in steady} == {1.0}
    assert {r[3] for r in second} == {"well_1", "well_2"}
    assert {r[1] for r in second if r[3] == "well_2"} == {names["Q"]}
    (records,) = wel.ts_records(calendar, names)
    assert records.name == names["Q"]
    assert records.rows[0] == (calendar.sim_time(datetime(2020, 4, 1)), 100.0)
    assert records.rows[-1] == (calendar.sim_time(datetime(2021, 1, 1)), 200.0)


def test_series_after_the_model_end_never_activates(valid_site: Project, build: Build) -> None:
    add_series(valid_site, "Q", "discharge", "m3/d", [(datetime(2022, 1, 1), 100.0)])
    add_well(valid_site, *center(7, 4), rate=None, series_id="Q")
    boundaries = build()
    wel = package(boundaries, "wel")
    calendar = project_timeline(valid_site).calendar
    assert all(rows == [] for rows in wel.period_records(calendar, boundaries.ts_names()))
    assert wel.ts_records(calendar, boundaries.ts_names()) == []
