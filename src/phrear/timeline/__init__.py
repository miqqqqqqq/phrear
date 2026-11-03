"""Time discretisation: series, stress periods, time steps (docs/SPEC.md, section 13)."""

from __future__ import annotations

from dataclasses import dataclass

from phrear.project import Project
from phrear.timeline.calendar import Calendar, Period, build_calendar
from phrear.timeline.mf6ts import steady_value
from phrear.timeline.series import (
    TimeSeries,
    check_references,
    load_series,
    referenced_series,
)


@dataclass(frozen=True)
class Timeline:
    calendar: Calendar
    series: dict[str, TimeSeries]
    """Series used by active features of the base model."""
    steady_values: dict[str, float | None]
    """Value of each series in the initial steady period (None: not yet active)."""


def project_timeline(project: Project) -> Timeline:
    """Calendar and series in use for a project."""
    series = check_references(load_series(project.gpkg_path), referenced_series(project.gpkg_path))
    model = project.config.model
    calendar = build_calendar(
        model, project.config.time, {series_id: s.start for series_id, s in series.items()}
    )
    steady: dict[str, float | None] = {}
    for series_id, s in series.items():
        if series_id in calendar.activations:
            s.value_at(calendar.end)  # coverage up to the model end
        steady[series_id] = steady_value(s, model) if model.steady_initial else None
    return Timeline(calendar=calendar, series=series, steady_values=steady)


__all__ = ["Calendar", "Period", "TimeSeries", "Timeline", "build_calendar", "project_timeline"]
