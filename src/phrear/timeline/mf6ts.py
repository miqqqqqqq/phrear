"""Time series records for MODFLOW 6 (TS files) and steady-state values.

MF6 STEPWISE and LINEAR time series are averaged over each time step (verified
by ``tests/engine/test_mf6_time_series.py``), so the records below reproduce the
project series exactly at the resolution of the time steps.

For each series in use the records start at its activation date and end at the
model end, in simulation time (:meth:`Calendar.sim_time`). If an activation was
moved earlier by a period merge, the first value is held back to the new
activation date; the calendar reports that move as a warning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from phrear.project.config import ModelTime
from phrear.timeline.calendar import Calendar
from phrear.timeline.series import TimeSeries

_NAME_CHARS = re.compile(r"[^a-z0-9_]")


@dataclass(frozen=True)
class TsRecords:
    """One MF6 time series: name, method, rows of (simulation time [d], value)."""

    name: str
    series_id: str
    method: str
    rows: tuple[tuple[float, float], ...]


def mf6_names(series_ids: list[str]) -> dict[str, str]:
    """Unique MF6-safe names (lowercase, ≤ 40 characters) for the series."""
    names: dict[str, str] = {}
    for index, series_id in enumerate(sorted(series_ids), start=1):
        stem = _NAME_CHARS.sub("_", series_id.lower())[:30]
        names[series_id] = f"s{index:03d}_{stem}".rstrip("_")
    return names


def ts_records(
    series: TimeSeries, calendar: Calendar, name: str, activation: datetime | None = None
) -> TsRecords:
    """Records from the activation date to the model end.

    ``activation`` defaults to the calendar activation of the series; series derived
    from others (for example the head of a cell between two stations) pass their own.
    """
    if activation is None:
        activation = calendar.activations[series.series_id]
    end = calendar.end

    def value(moment: datetime) -> float:
        return series.value_at(max(moment, series.start))

    moments = [activation, *(t for t in series.times if activation < t < end), end]
    rows = tuple((calendar.sim_time(t), value(t)) for t in moments)
    return TsRecords(name=name, series_id=series.series_id, method=series.interpolation, rows=rows)


def steady_value(series: TimeSeries, model: ModelTime) -> float | None:
    """Value of the series in the initial steady period, or None if not yet active.

    With ``model.steady_reference`` the value is the exact time average over the
    reference period; otherwise it is the value at the model start.
    """
    if series.start > model.start_date:
        return None
    reference = model.steady_reference
    if reference is None:
        return series.value_at(model.start_date)
    return series.mean_over(reference.start, reference.end)
