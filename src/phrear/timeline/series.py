"""Time series of the project (docs/SPEC.md, sections 8.2 and 13).

A series is a sequence of (date, value) pairs with an interpolation method:

- ``stepwise``: each value holds from its date until the next one; the last
  value holds until the end of the model;
- ``linear``: linear interpolation between points; undefined after the last one.

Before its first date a series is undefined: the object that uses it is inactive
until then, and its first date becomes a regime change (a new stress period).

Values are stored in the unit of the series and converted here to internal
units (metres, days) with an explicit factor. Dates are local civil time; a
trailing ``Z`` written by GDAL is ignored.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt

from phrear.errors import ObjectRef, SeriesError, UnitError
from phrear.project.gpkg import connect
from phrear.project.schema import SERIES_QUANTITIES, TABLES
from phrear.units import PhysicalQuantity, conversion_factor

Interpolation = Literal["stepwise", "linear"]
_DAY = timedelta(days=1)


def days_between(a: datetime, b: datetime) -> float:
    """b - a in days."""
    return (b - a) / _DAY


def parse_local_datetime(text: str) -> datetime:
    """Parse an ISO 8601 date or date-time as naive local time."""
    value = datetime.fromisoformat(text.strip().replace(" ", "T", 1))
    return value.replace(tzinfo=None)


@dataclass(frozen=True)
class TimeSeries:
    series_id: str
    quantity: PhysicalQuantity
    unit: str
    factor: float
    """value_internal = factor · value_in_unit."""
    interpolation: Interpolation
    times: tuple[datetime, ...]
    values: npt.NDArray[np.float64]
    """Values in internal units, one per time, times strictly increasing."""
    fid: int | None = None

    def __post_init__(self) -> None:
        if not self.times:
            raise SeriesError("series.empty", series_id=self.series_id)
        if len(self.times) != len(self.values):
            raise ValueError("times and values differ in length")
        if any(b <= a for a, b in zip(self.times, self.times[1:], strict=False)):
            raise ValueError("times must be strictly increasing")

    @property
    def start(self) -> datetime:
        return self.times[0]

    @property
    def end(self) -> datetime:
        """Last date. Stepwise series extend beyond it; linear ones do not."""
        return self.times[-1]

    @property
    def ref(self) -> ObjectRef:
        return ObjectRef(kind="series", layer="timeseries_meta", fid=self.fid)

    def _require(self, a: datetime, b: datetime) -> None:
        late_end = self.interpolation == "linear" and b > self.end
        if a < self.start or late_end:
            raise SeriesError(
                "series.not_covered",
                series_id=self.series_id,
                start=self.start.isoformat(),
                end=self.end.isoformat() if self.interpolation == "linear" else "∞",
                needed_start=a.isoformat(),
                needed_end=b.isoformat(),
                ref=self.ref,
            )

    def _x(self, moments: Iterable[datetime]) -> npt.NDArray[np.float64]:
        return np.array([days_between(self.start, t) for t in moments], dtype=np.float64)

    def value_at(self, t: datetime) -> float:
        """Value at instant ``t`` (internal units)."""
        self._require(t, t)
        if self.interpolation == "stepwise":
            return float(self.values[bisect.bisect_right(self.times, t) - 1])
        return float(np.interp(self._x([t])[0], self._x(self.times), self.values))

    def mean_over(self, a: datetime, b: datetime) -> float:
        """Exact time average over [a, b] (internal units)."""
        if b <= a:
            raise ValueError("empty interval")
        self._require(a, b)
        inner = [t for t in self.times if a < t < b]
        nodes = [a, *inner, b]
        x = self._x(nodes)
        widths = np.diff(x)
        if self.interpolation == "stepwise":
            levels = np.array([self.value_at(t) for t in nodes[:-1]])
            integral = float(np.sum(levels * widths))
        else:
            y = np.interp(x, self._x(self.times), self.values)
            integral = float(np.sum(0.5 * (y[1:] + y[:-1]) * widths))
        return integral / days_between(a, b)


def _series_layers() -> list[str]:
    return [t.name for t in TABLES if t.is_layer and "series_id" in t.field_names]


def load_series(gpkg_path: Path) -> dict[str, TimeSeries]:
    """Read all series of the GeoPackage, converted to internal units."""
    with connect(gpkg_path) as conn:
        meta = conn.execute(
            'SELECT fid, series_id, quantity, unit, interpolation FROM "timeseries_meta"'
        ).fetchall()
        rows = conn.execute(
            'SELECT series_id, "datetime", value FROM "timeseries_values" '
            'ORDER BY series_id, "datetime"'
        ).fetchall()
    by_id: dict[str, list[tuple[str, float]]] = {}
    for series_id, moment, value in rows:
        by_id.setdefault(series_id, []).append((moment, value))
    known = {m[1] for m in meta}
    orphans = sorted(set(by_id) - known)
    if orphans:
        raise SeriesError("series.orphan_values", series_id=orphans[0])

    out: dict[str, TimeSeries] = {}
    for fid, series_id, quantity_name, unit, interpolation in meta:
        ref = ObjectRef(kind="series", layer="timeseries_meta", fid=fid)
        if quantity_name not in SERIES_QUANTITIES:
            raise SeriesError(
                "series.invalid_quantity", series_id=series_id, quantity=str(quantity_name), ref=ref
            )
        quantity = SERIES_QUANTITIES[quantity_name]
        try:
            factor = conversion_factor(unit or "", quantity)
        except UnitError as exc:
            raise UnitError(exc.code, ref=ref, detail=exc.detail, **exc.fields) from exc
        pairs = by_id.get(series_id, [])
        if not pairs:
            raise SeriesError("series.empty", series_id=series_id, ref=ref)
        times = []
        for moment, _ in pairs:
            try:
                times.append(parse_local_datetime(str(moment)))
            except ValueError as exc:
                raise SeriesError(
                    "series.bad_datetime", series_id=series_id, value=str(moment), ref=ref
                ) from exc
        order = np.argsort(np.array([t.timestamp() for t in times]), kind="stable")
        out[series_id] = TimeSeries(
            series_id=series_id,
            quantity=quantity,
            unit=unit,
            factor=factor,
            interpolation="linear" if interpolation == "linear" else "stepwise",
            times=tuple(times[i] for i in order),
            values=np.array([pairs[i][1] for i in order], dtype=np.float64) * factor,
            fid=fid,
        )
    return out


def referenced_series(gpkg_path: Path) -> dict[str, list[ObjectRef]]:
    """Series used by the active features of the base model, with their users."""
    used: dict[str, list[ObjectRef]] = {}
    with connect(gpkg_path) as conn:
        for layer in _series_layers():
            query = (
                f'SELECT fid, series_id FROM "{layer}" WHERE series_id IS NOT NULL '
                "AND series_id <> '' AND COALESCE(active, 1) = 1 AND scenario_id IS NULL"
            )
            for fid, series_id in conn.execute(query):
                used.setdefault(series_id, []).append(
                    ObjectRef(kind="feature", layer=layer, fid=fid)
                )
    return used


def check_references(
    series: dict[str, TimeSeries], used: dict[str, list[ObjectRef]]
) -> dict[str, TimeSeries]:
    """The series actually used; raise if a feature refers to an undefined one."""
    for series_id, refs in sorted(used.items()):
        if series_id not in series:
            raise SeriesError("series.not_defined", series_id=series_id, ref=refs[0])
    return {k: v for k, v in series.items() if k in used}
