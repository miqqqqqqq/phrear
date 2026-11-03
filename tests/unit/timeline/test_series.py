"""Time series: values, exact averages, loading and references."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from phrear.errors import SeriesError, UnitError
from phrear.project import Project, gpkg
from phrear.timeline.series import (
    TimeSeries,
    check_references,
    load_series,
    parse_local_datetime,
    referenced_series,
)
from phrear.units import PhysicalQuantity

from .conftest import add_series, add_well

D = [datetime(2020, 1, day) for day in range(1, 32)]  # D[k] = 2020-01-(k+1)


def _series(interpolation: str, points: list[tuple[int, float]]) -> TimeSeries:
    return TimeSeries(
        series_id="s",
        quantity=PhysicalQuantity.DISCHARGE,
        unit="m3/d",
        factor=1.0,
        interpolation="linear" if interpolation == "linear" else "stepwise",
        times=tuple(D[k] for k, _ in points),
        values=np.array([v for _, v in points], dtype=np.float64),
    )


def test_stepwise_value_holds_until_next_point_and_after_the_last() -> None:
    s = _series("stepwise", [(0, 1.0), (5, 3.0)])
    assert s.value_at(D[0]) == 1.0
    assert s.value_at(D[4]) == 1.0
    assert s.value_at(D[5]) == 3.0
    assert s.value_at(D[30]) == 3.0


def test_stepwise_is_undefined_before_its_first_date() -> None:
    s = _series("stepwise", [(2, 1.0)])
    with pytest.raises(SeriesError) as exc:
        s.value_at(D[1])
    assert exc.value.code == "series.not_covered"


def test_linear_interpolates_and_stops_at_the_last_point() -> None:
    s = _series("linear", [(0, 0.0), (10, 10.0)])
    assert s.value_at(D[3]) == pytest.approx(3.0)
    with pytest.raises(SeriesError):
        s.value_at(D[11])


def test_stepwise_mean_is_exact() -> None:
    # 1 on [0, 5), 3 afterwards: mean over [0, 10] = (1·5 + 3·5)/10 = 2
    s = _series("stepwise", [(0, 1.0), (5, 3.0)])
    assert s.mean_over(D[0], D[10]) == pytest.approx(2.0, rel=1e-12)
    # over [2, 7]: (1·3 + 3·2)/5 = 1.8
    assert s.mean_over(D[2], D[7]) == pytest.approx(1.8, rel=1e-12)


def test_linear_mean_is_exact() -> None:
    s = _series("linear", [(0, 0.0), (4, 8.0), (10, 2.0)])
    # integral of the polyline over [0, 10]: 16 + 30 = 46 → mean 4.6
    assert s.mean_over(D[0], D[10]) == pytest.approx(4.6, rel=1e-12)
    assert s.mean_over(D[1], D[3]) == pytest.approx(4.0, rel=1e-12)


def test_parse_local_datetime_ignores_utc_suffix() -> None:
    assert parse_local_datetime("2020-03-01T06:30:00.000Z") == datetime(2020, 3, 1, 6, 30)
    assert parse_local_datetime("2020-03-01") == datetime(2020, 3, 1)
    assert parse_local_datetime("2020-03-01 06:30") == datetime(2020, 3, 1, 6, 30)


def test_load_converts_to_internal_units(project: Project) -> None:
    add_series(
        project, "Q1", [("2020-01-01", 10.0), ("2020-02-01T00:00:00.000Z", 20.0)], unit="l/s"
    )
    series = load_series(project.gpkg_path)["Q1"]
    assert series.factor == pytest.approx(86.4)
    np.testing.assert_allclose(series.values, [864.0, 1728.0])
    assert series.times == (datetime(2020, 1, 1), datetime(2020, 2, 1))
    assert series.interpolation == "stepwise"


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"quantity": "temperature"}, "series.invalid_quantity"),
        ({"unit": "kg"}, "unit.dimension"),
    ],
)
def test_load_rejects_bad_metadata(project: Project, kwargs: dict[str, str], code: str) -> None:
    add_series(project, "S", [("2020-01-01", 1.0)], **kwargs)
    with pytest.raises((SeriesError, UnitError)) as exc:
        load_series(project.gpkg_path)
    assert exc.value.code == code
    assert exc.value.ref is not None and exc.value.ref.layer == "timeseries_meta"


def test_load_rejects_empty_series_and_orphan_values(project: Project) -> None:
    add_series(project, "EMPTY", [])
    with pytest.raises(SeriesError) as exc:
        load_series(project.gpkg_path)
    assert exc.value.code == "series.empty"
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute('DELETE FROM "timeseries_meta"')
        conn.execute(
            'INSERT INTO "timeseries_values" (series_id, "datetime", value) '
            "VALUES ('GHOST', '2020-01-01', 1.0)"
        )
    with pytest.raises(SeriesError) as exc:
        load_series(project.gpkg_path)
    assert exc.value.code == "series.orphan_values"


def test_bad_date_is_reported(project: Project) -> None:
    add_series(project, "S", [("31/01/2020", 1.0)])
    with pytest.raises(SeriesError) as exc:
        load_series(project.gpkg_path)
    assert exc.value.code == "series.bad_datetime"


def test_references_only_from_active_base_features(project: Project) -> None:
    add_series(project, "Q1", [("2020-01-01", 1.0)])
    add_series(project, "Q2", [("2020-01-01", 1.0)])
    fid = add_well(project, "P1", "Q1")
    add_well(project, "P2", "Q2", active=False)
    add_well(project, "P3", "Q2", scenario_id="alt")
    used = referenced_series(project.gpkg_path)
    assert set(used) == {"Q1"}
    assert used["Q1"][0].layer == "wells" and used["Q1"][0].fid == fid
    in_use = check_references(load_series(project.gpkg_path), used)
    assert set(in_use) == {"Q1"}


def test_reference_to_undefined_series_is_an_error(project: Project) -> None:
    add_well(project, "P1", "MISSING")
    with pytest.raises(SeriesError) as exc:
        check_references(load_series(project.gpkg_path), referenced_series(project.gpkg_path))
    assert exc.value.code == "series.not_defined"
    assert exc.value.ref is not None and exc.value.ref.layer == "wells"
