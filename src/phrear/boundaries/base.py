"""Boundary conditions as package-neutral input for MF6 (docs/SPEC.md, sections 12 and 21).

Every boundary type turns its features into :class:`Assignment` objects, one per
model cell, each driven by a :class:`Forcing`:

- a constant value, or a time series in internal units;
- an activation date, the first date of the series as moved by the calendar
  (ADR 0009); the assignment enters the model from the stress period that
  starts there;
- the value in the initial steady period, None if the object is not active yet.

The ``mult`` of an assignment is the MF6 auxiliary multiplier (AUXMULTNAME): the
share and sign of a well rate in each screened layer, the fraction of the cell
covered by a recharge zone, 1 for fixed heads. Values stay as entered (absolute
rates), so a series can be shared by wells with different roles.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property

import geopandas as gpd
import numpy as np

from phrear.boundaries.geometry import CellIndex
from phrear.errors import BoundaryError, Localized, ObjectRef
from phrear.events import Problem
from phrear.grid.model_grid import ModelGrid
from phrear.params.layers import LayerParameters
from phrear.project import Project
from phrear.project.features import read_features
from phrear.project.schema import TABLES_BY_NAME
from phrear.timeline import Timeline
from phrear.timeline.calendar import Calendar, Period
from phrear.timeline.mf6ts import TsRecords, ts_records
from phrear.timeline.series import TimeSeries
from phrear.units import QUANTITY_LABELS, PhysicalQuantity

Cell = tuple[int, int, int]
"""(layer, row, column), 0-based."""
Record = tuple[Cell, float | str, float, str]
"""(cell, value or time series name, multiplier, boundname) of one MF6 list entry."""


@dataclass(frozen=True)
class Forcing:
    """Value of a boundary over time, internal units."""

    constant: float | None = None
    series: TimeSeries | None = None
    activation: datetime | None = None
    """Effective first date; None means from the model start."""
    steady: float | None = None
    """Value in the initial steady period; None if inactive there."""

    @classmethod
    def of_constant(cls, value: float) -> Forcing:
        return cls(constant=value, steady=value)

    def active_in(self, period: Period) -> bool:
        if period.kind == "steady":
            return self.steady is not None
        return self.activation is None or self.activation <= period.start

    def extremes(self, calendar: Calendar) -> tuple[float, float]:
        """Lowest and highest value over the simulation, steady period included."""
        if self.series is None:
            assert self.constant is not None
            return self.constant, self.constant
        s = self.series
        start = self.activation or calendar.start
        moments = [start, *(t for t in s.times if start < t < calendar.end), calendar.end]
        values = [s.value_at(max(t, s.start)) for t in moments]
        if self.steady is not None:
            values.append(self.steady)
        return min(values), max(values)


@dataclass(frozen=True)
class Assignment:
    cell: Cell
    forcing: Forcing
    mult: float
    boundname: str
    ref: ObjectRef
    """The feature that produced the assignment."""


@dataclass(frozen=True)
class PackageInput:
    bc_type: str
    package: str
    """MF6 package type: wel, chd, rch."""
    assignments: tuple[Assignment, ...]
    warnings: tuple[Problem, ...] = ()
    n_features: int = 0

    def series(self) -> dict[str, tuple[TimeSeries, datetime | None]]:
        """Time series driving the assignments, with their earliest activation date.

        A series shared by objects that activate at different dates is written from
        the earliest one; MF6 reads it only from the period in which each is active.
        """
        found: dict[str, tuple[TimeSeries, datetime | None]] = {}
        for a in self.assignments:
            s, activation = a.forcing.series, a.forcing.activation
            if s is None:
                continue
            if s.series_id in found:
                previous = found[s.series_id][1]
                if previous is None or (activation is not None and previous <= activation):
                    continue
            found[s.series_id] = (s, activation)
        return found

    def period_records(self, calendar: Calendar, names: dict[str, str]) -> list[list[Record]]:
        """MF6 list entries of every stress period, in calendar order.

        ``names`` maps series identifiers to MF6 time series names.
        """
        periods: list[list[Record]] = []
        for period in calendar.periods:
            rows: list[Record] = []
            for a in self.assignments:
                f = a.forcing
                if not f.active_in(period):
                    continue
                value: float | str
                if period.kind == "steady":
                    assert f.steady is not None
                    value = f.steady
                elif f.series is None:
                    assert f.constant is not None
                    value = f.constant
                else:
                    value = names[f.series.series_id]
                rows.append((a.cell, value, a.mult, a.boundname))
            periods.append(rows)
        return periods

    def ts_records(self, calendar: Calendar, names: dict[str, str]) -> list[TsRecords]:
        """MF6 time series of the package; series never active in the model are left out."""
        return [
            ts_records(s, calendar, names[series_id], activation=activation)
            for series_id, (s, activation) in sorted(self.series().items())
            if activation is None or activation < calendar.end
        ]


@dataclass
class BcContext:
    """What the boundary types need to read features and place them on the grid."""

    project: Project
    grid: ModelGrid
    layers: LayerParameters
    timeline: Timeline

    @cached_property
    def cells(self) -> CellIndex:
        return CellIndex(self.grid.geometry)

    @property
    def calendar(self) -> Calendar:
        return self.timeline.calendar

    @cached_property
    def active_columns(self) -> np.ndarray:
        return np.asarray((self.grid.idomain > 0).any(axis=0))

    def features(self, layer: str) -> gpd.GeoDataFrame:
        return read_features(self.project, layer)

    def series_forcing(
        self,
        series_id: str,
        expected: PhysicalQuantity,
        *,
        feature: str,
        layer: str,
        ref: ObjectRef,
    ) -> Forcing:
        s = self.timeline.series[series_id]
        if s.quantity is not expected:
            raise BoundaryError(
                "bc.series_quantity",
                feature=feature,
                layer=layer_label(layer),
                series_id=series_id,
                actual=QUANTITY_LABELS[s.quantity],
                expected=QUANTITY_LABELS[expected],
                ref=ref,
            )
        # a series starting after the model end never activates (the calendar warns)
        return Forcing(
            series=s,
            activation=self.calendar.activations.get(series_id, self.calendar.end),
            steady=self.timeline.steady_values[series_id],
        )

    def layers_of_units(self, top: int | None, bottom: int | None) -> list[int]:
        """Model layers of the units from position ``top`` to ``bottom`` (None: all)."""
        first = 1 if top is None else top
        last = len(self.grid.units) if bottom is None else bottom
        return [k for k, pos in enumerate(self.grid.layer_unit) if first <= pos <= last]


def layer_label(layer: str) -> Localized:
    return TABLES_BY_NAME[layer].label


@dataclass(frozen=True)
class BoundaryConditionType:
    """A registered kind of boundary condition (docs/SPEC.md, section 21).

    Fields, units and labels of its layers are defined once in
    :mod:`phrear.project.schema`; the QGIS style comes with the plugin (M1b).
    """

    name: str
    label: Localized
    package: str
    layers: tuple[str, ...]
    build: Callable[[BcContext], PackageInput] = field(repr=False)


__all__ = [
    "Assignment",
    "BcContext",
    "BoundaryConditionType",
    "Cell",
    "Forcing",
    "PackageInput",
    "Record",
    "layer_label",
]
