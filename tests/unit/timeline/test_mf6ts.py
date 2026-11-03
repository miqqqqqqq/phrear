"""MF6 time series records and steady-state values."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from phrear.project.config import ModelTime, SteadyReference, TimeStepping
from phrear.timeline.calendar import build_calendar
from phrear.timeline.mf6ts import mf6_names, steady_value, ts_records
from phrear.timeline.series import TimeSeries
from phrear.units import PhysicalQuantity

START = datetime(2020, 1, 1)
END = datetime(2020, 3, 1)


def _series(
    series_id: str, points: list[tuple[datetime, float]], linear: bool = False
) -> TimeSeries:
    return TimeSeries(
        series_id=series_id,
        quantity=PhysicalQuantity.DISCHARGE,
        unit="m3/d",
        factor=1.0,
        interpolation="linear" if linear else "stepwise",
        times=tuple(t for t, _ in points),
        values=np.array([v for _, v in points], dtype=np.float64),
    )


def test_records_cover_activation_to_end_in_simulation_time() -> None:
    s = _series("Q", [(datetime(2019, 6, 1), -10.0), (datetime(2020, 1, 21), -30.0)])
    calendar = build_calendar(
        ModelTime(start_date=START, end_date=END), TimeStepping(), {"Q": s.start}
    )
    records = ts_records(s, calendar, "s001_q")
    assert records.method == "stepwise"
    # sim time 1 = model start (after the 1-day steady period); 61 = end (60 days later)
    assert records.rows == ((1.0, -10.0), (21.0, -30.0), (61.0, -30.0))


def test_linear_records_interpolate_at_the_boundaries() -> None:
    s = _series("H", [(datetime(2019, 12, 22), 0.0), (datetime(2020, 3, 11), 80.0)], linear=True)
    model = ModelTime(start_date=START, end_date=END, steady_initial=False)
    calendar = build_calendar(model, TimeStepping(), {"H": s.start})
    rows = ts_records(s, calendar, "h").rows
    assert rows[0][0] == 0.0 and rows[0][1] == pytest.approx(10.0)
    assert rows[-1][0] == 60.0 and rows[-1][1] == pytest.approx(70.0)


def test_activation_moved_earlier_holds_the_first_value_back() -> None:
    model = ModelTime(start_date=START, end_date=END, period_breaks=[datetime(2020, 2, 1)])
    s = _series("Q", [(datetime(2020, 2, 1, 12), -5.0)])
    calendar = build_calendar(model, TimeStepping(), {"Q": s.start})
    assert calendar.activations["Q"] == datetime(2020, 2, 1)
    rows = ts_records(s, calendar, "q").rows
    assert rows[0] == (32.0, -5.0)


def test_steady_value_uses_reference_average_or_start_value() -> None:
    s = _series("Q", [(datetime(2019, 1, 1), -10.0), (datetime(2019, 7, 1), -20.0)])
    plain = ModelTime(start_date=START, end_date=END)
    assert steady_value(s, plain) == -20.0
    reference = SteadyReference(start=datetime(2019, 1, 1), end=datetime(2020, 1, 1))
    model = ModelTime(start_date=START, end_date=END, steady_reference=reference)
    # 181 days at -10, 184 days at -20 → (-1810 - 3680) / 365
    assert steady_value(s, model) == pytest.approx((-10 * 181 - 20 * 184) / 365)


def test_series_starting_later_is_inactive_in_steady_state() -> None:
    s = _series("Q", [(datetime(2020, 2, 1), -10.0)])
    assert steady_value(s, ModelTime(start_date=START, end_date=END)) is None


def test_mf6_names_are_unique_and_safe() -> None:
    names = mf6_names(["Pozzo A (l/s)", "pozzo_a__l_s_", "x" * 60])
    assert len(set(names.values())) == 3
    for name in names.values():
        assert len(name) <= 40
        assert name == name.lower()
        assert all(c.isalnum() or c == "_" for c in name)
