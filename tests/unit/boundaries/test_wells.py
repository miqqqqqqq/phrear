"""Wells: column, share of the rate among the screened layers, rate and series."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from phrear.errors import BoundaryError
from phrear.project import Project

from ..sites import X0, Y0
from .conftest import Build, add_series, add_well, center, package

#: Screen 45-10 m in a western column: 5 m in layer 1 (K 8.64 m/d), 20 m in layer 2 and
#: 10 m in layer 3 (K 50 m/d).
WEST_T = (8.64 * 5, 50.0 * 20, 50.0 * 10)


def _wells(build: Build) -> list[tuple[tuple[int, int, int], float, float | str | None]]:
    wel = package(build(), "wel")
    return [(a.cell, a.mult, a.forcing.constant) for a in wel.assignments]


def test_rate_is_shared_by_transmissivity(valid_site: Project, build: Build) -> None:
    add_well(valid_site, *center(7, 4))
    wells = _wells(build)
    total = sum(WEST_T)
    assert [cell for cell, _, _ in wells] == [(0, 7, 4), (1, 7, 4), (2, 7, 4)]
    assert [m for _, m, _ in wells] == pytest.approx([-t / total for t in WEST_T])
    assert all(value == pytest.approx(864.0) for _, _, value in wells)  # 10 l/s in m³/d
    assert package(build(), "wel").warnings == ()


def test_depth_below_reference_gives_the_same_screen(valid_site: Project, build: Build) -> None:
    add_well(valid_site, *center(7, 4), depth_mode="depth", z_ref=50.0, screen_top=5.0,
             screen_bottom=40.0)  # fmt: skip
    total = sum(WEST_T)
    assert [m for _, m, _ in _wells(build)] == pytest.approx([-t / total for t in WEST_T])


def test_injection_is_positive(valid_site: Project, build: Build) -> None:
    add_well(valid_site, *center(7, 4), role="injection")
    assert sum(m for _, m, _ in _wells(build)) == pytest.approx(1.0)


def test_pass_through_layer_gets_no_share(valid_site: Project, build: Build) -> None:
    # east of x = X0 + 1500 unit 1 pinches out: layer 1 is pass-through,
    # layer 2 spans 50-25 m and layer 3 25-0 m
    add_well(valid_site, *center(7, 14))
    wells = _wells(build)
    assert [cell for cell, _, _ in wells] == [(1, 7, 14), (2, 7, 14)]
    assert [m for _, m, _ in wells] == pytest.approx([-20 / 35, -15 / 35])


def test_screen_below_the_model_is_clipped(valid_site: Project, build: Build) -> None:
    add_well(valid_site, *center(7, 4), screen_bottom=-5.0)
    wel = package(build(), "wel")
    assert [w.code for w in wel.warnings] == ["bc.screen_clipped"]
    assert "lungo 50 m e 45 m" in wel.warnings[0].message.it
    assert sum(a.mult for a in wel.assignments) == pytest.approx(-1.0)


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"depth_mode": "depth", "z_ref": None}, "bc.z_ref_missing"),
        ({"screen_top": 10.0, "screen_bottom": 45.0}, "bc.screen_order"),
        ({"screen_top": -10.0, "screen_bottom": -20.0}, "bc.screen_outside"),
        ({"model_as": "maw"}, "bc.maw_not_available"),
        ({"rate": -3.0}, "bc.negative_rate"),
        ({"rate": None}, "bc.value_missing"),
        ({"rate_unit": None}, "bc.unit_missing"),
        ({"rate_unit": "m"}, "unit.dimension"),
    ],
)
def test_invalid_wells(
    valid_site: Project, build: Build, fields: dict[str, Any], code: str
) -> None:
    fid = add_well(valid_site, *center(7, 4), **fields)
    with pytest.raises(Exception) as info:
        build()
    assert getattr(info.value, "code", None) == code
    ref = info.value.ref  # type: ignore[attr-defined]
    assert ref.layer == "wells" and ref.fid == fid


def test_well_outside_the_active_cells(valid_site: Project, build: Build) -> None:
    add_well(valid_site, X0 + 100.0, Y0 + 100.0)
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == "bc.outside_active"


def test_inactive_and_scenario_wells_are_ignored(valid_site: Project, build: Build) -> None:
    add_well(valid_site, X0 + 100.0, Y0 + 100.0, active=0)
    add_well(valid_site, X0 + 100.0, Y0 + 100.0, scenario_id="s1")
    wel = package(build(), "wel")
    assert wel.assignments == () and wel.n_features == 0


def test_rate_from_a_series(valid_site: Project, build: Build) -> None:
    add_series(valid_site, "Q", "discharge", "l/s",
               [(datetime(2020, 1, 1), 5.0), (datetime(2020, 7, 1), 10.0)])  # fmt: skip
    add_well(valid_site, *center(7, 4), rate=None, series_id="Q")
    forcing = package(build(), "wel").assignments[0].forcing
    assert forcing.series is not None and forcing.series.series_id == "Q"
    assert forcing.activation == datetime(2020, 1, 1)
    assert forcing.steady == pytest.approx(5.0 * 86.4)


@pytest.mark.parametrize(
    ("quantity", "unit", "value", "code"),
    [("length", "m", 5.0, "bc.series_quantity"), ("discharge", "l/s", -5.0, "bc.negative_series")],
)
def test_invalid_series(
    valid_site: Project, build: Build, quantity: str, unit: str, value: float, code: str
) -> None:
    add_series(valid_site, "Q", quantity, unit, [(datetime(2020, 1, 1), value)])
    add_well(valid_site, *center(7, 4), rate=None, series_id="Q")
    with pytest.raises(BoundaryError) as info:
        build()
    assert info.value.code == code
