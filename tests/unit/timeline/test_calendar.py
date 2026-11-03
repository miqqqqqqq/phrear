"""Stress periods at regime changes and automatic time steps."""

from __future__ import annotations

from datetime import datetime

import pytest

from phrear.errors import TimeError
from phrear.project.config import ModelTime, TimeStepping
from phrear.timeline.calendar import (
    STEADY_LENGTH_D,
    _last_step,
    build_calendar,
    first_step,
    time_steps,
)

START = datetime(2020, 1, 1)
END = datetime(2021, 1, 1)
DEFAULT = TimeStepping()


@pytest.mark.parametrize(
    ("length", "dt0", "mult", "dtmax"),
    [
        (366.0, 1.0, 1.2, 30.0),
        (31.0, 1.0, 1.2, 30.0),
        (10.0, 0.01, 1.5, 2.0),
        (3650.0, 1.0, 1.2, 30.0),
        (5.0, 1.0, 1.0, 1.0),
        (100.0, 0.5, 2.0, 100.0),
    ],
)
def test_time_steps_respect_limits_and_are_minimal(
    length: float, dt0: float, mult: float, dtmax: float
) -> None:
    stepping = TimeStepping(dt_initial_d=dt0, tsmult=mult, dt_max_d=dtmax)
    nstp, m = time_steps(length, stepping)
    tol = 1e-9
    assert 1.0 <= m <= mult
    assert first_step(length, nstp, m) <= dt0 * (1 + tol)
    assert _last_step(length, nstp, m) <= dtmax * (1 + tol)
    # with one step fewer no multiplier in [1, mult] satisfies both limits
    if nstp > 1:
        n = nstp - 1
        grid = [1.0 + (mult - 1.0) * k / 2000 for k in range(2001)]
        assert not any(
            first_step(length, n, g) <= dt0 * (1 + tol)
            and _last_step(length, n, g) <= dtmax * (1 + tol)
            for g in grid
        )


def test_short_period_has_a_single_step() -> None:
    assert time_steps(0.5, DEFAULT) == (1, 1.0)


def test_first_step_formula() -> None:
    # dt1 = L (m - 1) / (m^n - 1): L = 7, m = 2, n = 3 → 1
    assert first_step(7.0, 3, 2.0) == pytest.approx(1.0)
    assert first_step(6.0, 3, 1.0) == pytest.approx(2.0)


def test_too_many_steps_is_an_error() -> None:
    with pytest.raises(TimeError) as exc:
        time_steps(1e6, TimeStepping(dt_initial_d=1e-3, tsmult=1.0, dt_max_d=1e-3))
    assert exc.value.code == "time.too_many_steps"


def test_calendar_with_steady_period_breaks_and_activation() -> None:
    model = ModelTime(start_date=START, end_date=END, period_breaks=[datetime(2020, 7, 1)])
    calendar = build_calendar(
        model, DEFAULT, {"Q_old": datetime(2019, 6, 1), "Q_new": datetime(2020, 3, 15)}
    )
    kinds = [p.kind for p in calendar.periods]
    starts = [p.start for p in calendar.periods]
    assert kinds == ["steady", "transient", "transient", "transient"]
    assert starts == [START, START, datetime(2020, 3, 15), datetime(2020, 7, 1)]
    assert calendar.periods[2].reasons == ("series:Q_new",)
    assert calendar.periods[3].reasons == ("period_break",)
    assert [p.index for p in calendar.periods] == [1, 2, 3, 4]
    assert sum(p.perlen_d for p in calendar.transient_periods) == pytest.approx(366.0)
    assert calendar.periods[0].perlen_d == STEADY_LENGTH_D
    assert calendar.activations == {"Q_old": START, "Q_new": datetime(2020, 3, 15)}
    assert calendar.sim_time(START) == pytest.approx(1.0)
    assert calendar.sim_time(datetime(2020, 1, 11)) == pytest.approx(11.0)
    assert calendar.warnings == ()


def test_calendar_without_steady_period_starts_at_time_zero() -> None:
    model = ModelTime(start_date=START, end_date=END, steady_initial=False)
    calendar = build_calendar(model, DEFAULT, {})
    assert [p.kind for p in calendar.periods] == ["transient"]
    assert calendar.sim_time(START) == 0.0


def test_short_period_is_merged_into_the_next_with_a_warning() -> None:
    model = ModelTime(start_date=START, end_date=END, period_breaks=[datetime(2020, 5, 1)])
    near = datetime(2020, 5, 1, 12)  # half a day after the break
    calendar = build_calendar(model, DEFAULT, {"Q": near})
    starts = [p.start for p in calendar.transient_periods]
    assert starts == [START, datetime(2020, 5, 1)]
    assert calendar.activations["Q"] == datetime(2020, 5, 1)
    (warning,) = calendar.warnings
    assert warning.code == "time.period_merged"
    assert "2020-05-01 12:00" in warning.message.it


def test_short_last_period_is_merged_into_the_previous() -> None:
    model = ModelTime(start_date=START, end_date=END, period_breaks=[datetime(2020, 12, 31, 18)])
    calendar = build_calendar(model, DEFAULT, {})
    assert [p.start for p in calendar.transient_periods] == [START]
    assert len(calendar.warnings) == 1


def test_series_starting_after_the_end_is_reported() -> None:
    model = ModelTime(start_date=START, end_date=END)
    calendar = build_calendar(model, DEFAULT, {"late": datetime(2022, 1, 1)})
    assert "late" not in calendar.activations
    assert [w.code for w in calendar.warnings] == ["series.after_end"]


def test_sim_time_outside_the_period_is_rejected() -> None:
    calendar = build_calendar(ModelTime(start_date=START, end_date=END), DEFAULT, {})
    with pytest.raises(ValueError, match="outside"):
        calendar.sim_time(datetime(2022, 1, 1))
