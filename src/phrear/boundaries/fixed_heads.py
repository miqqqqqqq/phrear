"""Fixed heads (CHD) along lines and over areas, with values at stations (docs/SPEC.md, 12).

Lines: the head of a crossed cell is the linear interpolation, by chainage, of the
stations on either side of the midpoint of the line inside the cell; beyond the
first and last station the end value holds. When the stations carry series, the
head of the cell is a new series w · h_a(t) + (1 - w) · h_b(t) on the union of
their dates. For two stepwise or two linear series this is exact at every
instant, which is why a line cannot mix the two kinds. The whole line becomes
active when all its stations are defined.

Areas: one station, uniform head, cells chosen with the activation rule of the grid
(centroid or area fraction).

Layers: those of the units from ``top_unit`` to ``bottom_unit``. MF6 rejects a
fixed head below the cell bottom, so a layer gets the fixed head only if its bottom
lies below the lowest head of the simulation. A layer whose bottom the head
crosses during the run is left free, with a warning; a layer always above the
head is left free silently, as it is dry there. A cell already fixed by another
feature keeps the first one (lines before areas, by fid), with a warning, because
MF6 rejects two fixed heads in one cell.
"""

from __future__ import annotations

import bisect
import dataclasses
import itertools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import shapely

from phrear.boundaries.base import (
    Assignment,
    BcContext,
    BoundaryConditionType,
    Cell,
    Forcing,
    PackageInput,
    layer_label,
)
from phrear.errors import BoundaryError, Localized, ObjectRef, PhrearError
from phrear.events import Problem
from phrear.project import gpkg
from phrear.project.features import feature_label, fmt, number, text
from phrear.timeline.calendar import Calendar
from phrear.timeline.series import TimeSeries
from phrear.units import PhysicalQuantity

LINES = "fixed_head_lines"
AREAS = "fixed_head_areas"
STATIONS = "line_stations"
_PREFIX = {LINES: "chdl", AREAS: "chda"}
_EPS = 1e-6


@dataclass(frozen=True)
class Station:
    fid: int
    label: str
    chainage: float
    forcing: Forcing


@dataclass
class _Candidate:
    cell: Cell
    forcing: Forcing
    boundname: str
    label: str
    ref: ObjectRef


def _ref(layer: str, fid: int, field: str | None = None) -> ObjectRef:
    if field is None:
        return ObjectRef(kind="feature", layer=layer, fid=fid)
    return ObjectRef(kind="field", layer=layer, fid=fid, field=field)


def _station_groups(ctx: BcContext) -> dict[tuple[str, int], list[tuple[int, Any]]]:
    with gpkg.connect(ctx.project.gpkg_path) as conn:
        existing = {
            layer: {int(r[0]) for r in conn.execute(f'SELECT fid FROM "{layer}"')}
            for layer in (LINES, AREAS)
        }
    groups: dict[tuple[str, int], list[tuple[int, Any]]] = {}
    for fid, row in ctx.features(STATIONS).iterrows():
        fid = int(fid)
        layer = text(row["feature_layer"])
        feature_id = number(row["feature_id"])
        if layer not in existing or feature_id is None or int(feature_id) not in existing[layer]:
            ctx.errors.fail(
                BoundaryError(
                    "bc.station_unknown_feature",
                    station=feature_label(row["name"], fid),
                    feature_id=str(feature_id if feature_id is None else int(feature_id)),
                    feature_layer=str(layer),
                    ref=_ref(STATIONS, fid, "feature_id"),
                )
            )
            continue
        groups.setdefault((layer, int(feature_id)), []).append((fid, row))
    return groups


def _station_forcing(ctx: BcContext, fid: int, label: str, row: Any) -> Forcing:
    series_id = text(row["series_id"])
    if series_id is not None:
        return ctx.series_forcing(
            series_id,
            PhysicalQuantity.LENGTH,
            feature=label,
            layer=STATIONS,
            ref=_ref(STATIONS, fid, "series_id"),
        )
    value = number(row["value"])
    if value is None:
        raise BoundaryError("bc.station_no_value", station=label, ref=_ref(STATIONS, fid))
    return Forcing.of_constant(value)


def combine(parts: list[tuple[float, Forcing]], series_id: str, calendar: Calendar) -> Forcing:
    """The forcing Σ w_i · f_i, exact when the series share their interpolation."""
    constant = sum(w * f.constant for w, f in parts if f.series is None and f.constant is not None)
    driven = [(w, f, f.series) for w, f in parts if f.series is not None]
    if not driven:
        return Forcing.of_constant(constant)
    start = max(s.start for _, _, s in driven)
    activation = max(f.activation or calendar.start for _, f, _ in driven)
    end = calendar.end
    inner = {t for _, _, s in driven for t in s.times if start < t < end}
    times = sorted({start, *inner, *([end] if end > start else [])})
    values = np.array(
        [constant + sum(w * s.value_at(t) for w, _, s in driven) for t in times], dtype=np.float64
    )
    steady: float | None = None
    if all(f.steady is not None for _, f, _ in driven):
        steady = constant + sum(w * f.steady for w, f, _ in driven if f.steady is not None)
    series = TimeSeries(
        series_id=series_id,
        quantity=PhysicalQuantity.LENGTH,
        unit="m",
        factor=1.0,
        interpolation=driven[0][2].interpolation,
        times=tuple(times),
        values=values,
    )
    return Forcing(series=series, activation=activation, steady=steady)


def interpolate(
    stations: list[Station], chainage: float, series_id: str, calendar: Calendar
) -> Forcing:
    """Forcing at ``chainage`` from stations sorted by chainage."""
    if chainage <= stations[0].chainage:
        return stations[0].forcing
    if chainage >= stations[-1].chainage:
        return stations[-1].forcing
    i = bisect.bisect_right([s.chainage for s in stations], chainage) - 1
    a, b = stations[i], stations[i + 1]
    w = (b.chainage - chainage) / (b.chainage - a.chainage)
    if w >= 1.0 - 1e-12:
        return a.forcing
    if w <= 1e-12:
        return b.forcing
    return combine([(w, a.forcing), (1.0 - w, b.forcing)], series_id, calendar)


def align(forcing: Forcing, stations: list[Station]) -> Forcing:
    """The forcing of a cell, active only when all stations of its line are defined."""
    dates = [s.forcing.activation for s in stations if s.forcing.activation is not None]
    if not dates:
        return forcing
    steady = forcing.steady if all(s.forcing.steady is not None for s in stations) else None
    return dataclasses.replace(forcing, activation=max(dates), steady=steady)


def _unit_layers(ctx: BcContext, layer: str, fid: int, label: str, row: Any) -> list[int]:
    top, bottom = number(row["top_unit"]), number(row["bottom_unit"])
    n_units = len(ctx.grid.units)
    first = 1 if top is None else int(top)
    last = n_units if bottom is None else int(bottom)
    if not 1 <= first <= last <= n_units:
        raise BoundaryError(
            "bc.unit_range",
            feature=label,
            layer=layer_label(layer),
            top_unit=first,
            bottom_unit=last,
            n_units=n_units,
            ref=_ref(layer, fid, "top_unit" if top is not None else "bottom_unit"),
        )
    return ctx.layers_of_units(first, last)


class _Column:
    """Layers of one column that receive the fixed head."""

    def __init__(self, ctx: BcContext, layers: list[int]) -> None:
        self.ctx = ctx
        self.layers = layers
        self.partly_dry: list[Cell] = []

    def layers_for(
        self, row: int, col: int, forcing: Forcing, label: str, ref: ObjectRef
    ) -> list[int] | None:
        """None when the column has no active cell in the units affected."""
        grid = self.ctx.grid
        active = [k for k in self.layers if grid.idomain[k, row, col] > 0]
        if not active:
            return None
        low, high = forcing.extremes(self.ctx.calendar)
        keep = [k for k in active if grid.botm[k, row, col] <= low]
        self.partly_dry += [(k, row, col) for k in active if low < grid.botm[k, row, col] < high]
        if not keep:
            raise BoundaryError(
                "bc.head_below_bottom",
                feature=label,
                head=fmt(low),
                row=row + 1,
                col=col + 1,
                bottom=fmt(float(grid.botm[active[-1], row, col])),
                ref=ref,
            )
        return keep

    def warning(self, label: str, ref: ObjectRef) -> Problem | None:
        if not self.partly_dry:
            return None
        k, r, c = self.partly_dry[0]
        return Problem.from_code(
            "bc.chd_layers_excluded",
            {
                "n_cells": len(self.partly_dry),
                "feature": label,
                "layer": k + 1,
                "row": r + 1,
                "col": c + 1,
            },
            ref=ref,
        )


def _stations_of_line(
    ctx: BcContext, line: shapely.Geometry, label: str, rows: list[tuple[int, Any]]
) -> tuple[list[Station], list[Problem]]:
    warnings: list[Problem] = []
    stations: list[Station] = []
    length = float(line.length)
    cell = ctx.grid.geometry.cell_size
    for fid, row in rows:
        station = feature_label(row["name"], fid)
        point = row.geometry
        chainage = number(row["chainage"])
        if point is None or point.is_empty:
            if chainage is None:
                raise BoundaryError(
                    "bc.geometry_missing",
                    feature=station,
                    layer=layer_label(STATIONS),
                    ref=_ref(STATIONS, fid),
                )
        else:
            distance = float(line.distance(point))
            if distance > cell:
                warnings.append(
                    Problem.from_code(
                        "bc.station_far",
                        {
                            "station": station,
                            "distance": fmt(distance),
                            "feature": label,
                            "cell": fmt(cell),
                        },
                        ref=_ref(STATIONS, fid),
                    )
                )
            if chainage is None:
                chainage = float(line.project(point))
        assert chainage is not None
        if chainage > length + _EPS:
            raise BoundaryError(
                "bc.chainage_beyond",
                station=station,
                chainage=fmt(chainage),
                feature=label,
                length=fmt(length),
                ref=_ref(STATIONS, fid, "chainage"),
            )
        stations.append(Station(fid, station, chainage, _station_forcing(ctx, fid, station, row)))
    stations.sort(key=lambda s: s.chainage)
    for a, b in itertools.pairwise(stations):
        if b.chainage - a.chainage < _EPS:
            raise BoundaryError(
                "bc.duplicate_chainage",
                first=a.label,
                second=b.label,
                feature=label,
                chainage=fmt(a.chainage),
                ref=_ref(STATIONS, b.fid, "chainage"),
            )
    kinds = {s.forcing.series.interpolation for s in stations if s.forcing.series is not None}
    if len(kinds) > 1:
        raise BoundaryError(
            "bc.mixed_interpolation", feature=label, ref=_ref(STATIONS, stations[0].fid)
        )
    return stations, warnings


def _geometry(layer: str, fid: int, label: str, row: Any) -> shapely.Geometry:
    geom = row.geometry
    if geom is None or geom.is_empty:
        raise BoundaryError(
            "bc.geometry_missing", feature=label, layer=layer_label(layer), ref=_ref(layer, fid)
        )
    return geom


Groups = dict[tuple[str, int], list[tuple[int, Any]]]
Built = tuple[list[_Candidate], list[Problem]]


def _line(ctx: BcContext, groups: Groups, fid: int, row: Any) -> Built:
    label = feature_label(row["name"], fid)
    ref = _ref(LINES, fid)
    parts = shapely.get_parts(shapely.line_merge(_geometry(LINES, fid, label, row)))
    if len(parts) != 1:
        raise BoundaryError("bc.multipart_line", feature=label, n=len(parts), ref=ref)
    line = parts[0]
    rows = groups.get((LINES, fid))
    if not rows:
        raise BoundaryError(
            "bc.no_stations",
            feature=label,
            layer=layer_label(LINES),
            layer_code=LINES,
            fid=fid,
            ref=ref,
        )
    stations, warnings = _stations_of_line(ctx, line, label, rows)
    column = _Column(ctx, _unit_layers(ctx, LINES, fid, label, row))
    boundname = f"{_PREFIX[LINES]}_{fid}"
    candidates: list[_Candidate] = []
    used: list[int] = []
    for piece in ctx.cells.line_pieces(line):
        series_id = f"{boundname}@{piece.row + 1}_{piece.col + 1}"
        forcing = align(interpolate(stations, piece.chainage, series_id, ctx.calendar), stations)
        layers = column.layers_for(piece.row, piece.col, forcing, label, ref)
        if layers is None:
            continue
        used.append(piece.row * ctx.grid.geometry.ncol + piece.col)
        candidates += [
            _Candidate((k, piece.row, piece.col), forcing, boundname, label, ref) for k in layers
        ]
    if not used:
        raise BoundaryError("bc.outside_active", feature=label, layer=layer_label(LINES), ref=ref)
    outside = float(line.difference(shapely.union_all(ctx.cells.polygons[used])).length)
    if outside > _EPS * max(1.0, float(line.length)):
        warnings.append(
            Problem.from_code(
                "bc.line_outside",
                {"feature": label, "length": fmt(float(line.length)), "outside": fmt(outside)},
                ref=ref,
            )
        )
    if (w := column.warning(label, ref)) is not None:
        warnings.append(w)
    return candidates, warnings


def _area(ctx: BcContext, groups: Groups, fid: int, row: Any) -> Built:
    settings = ctx.project.config.grid
    label = feature_label(row["name"], fid)
    ref = _ref(AREAS, fid)
    polygon = _geometry(AREAS, fid, label, row)
    rows = groups.get((AREAS, fid), [])
    if not rows:
        raise BoundaryError(
            "bc.no_stations",
            feature=label,
            layer=layer_label(AREAS),
            layer_code=AREAS,
            fid=fid,
            ref=ref,
        )
    if len(rows) > 1:
        raise BoundaryError("bc.area_stations", feature=label, n=len(rows), ref=ref)
    sfid, srow = rows[0]
    forcing = _station_forcing(ctx, sfid, feature_label(srow["name"], sfid), srow)
    column = _Column(ctx, _unit_layers(ctx, AREAS, fid, label, row))
    boundname = f"{_PREFIX[AREAS]}_{fid}"
    candidates: list[_Candidate] = []
    for piece in ctx.cells.area_pieces(polygon):
        if settings.activation == "area":
            selected = piece.fraction >= settings.min_area_fraction
        else:
            selected = piece.centroid_inside
        if not selected:
            continue
        layers = column.layers_for(piece.row, piece.col, forcing, label, ref)
        if layers is None:
            continue
        candidates += [
            _Candidate((k, piece.row, piece.col), forcing, boundname, label, ref) for k in layers
        ]
    if not candidates:
        raise BoundaryError("bc.outside_active", feature=label, layer=layer_label(AREAS), ref=ref)
    warning = column.warning(label, ref)
    return candidates, [] if warning is None else [warning]


def _features(
    ctx: BcContext,
    layer: str,
    groups: Groups,
    build: Callable[[BcContext, Groups, int, Any], Built],
) -> tuple[list[_Candidate], list[Problem], int]:
    """Candidates of every feature of ``layer``, one error per feature."""
    candidates: list[_Candidate] = []
    warnings: list[Problem] = []
    frame = ctx.features(layer)
    for fid, row in frame.iterrows():
        try:
            found, notes = build(ctx, groups, int(fid), row)
        except PhrearError as exc:
            ctx.errors.fail(exc)
            continue
        candidates += found
        warnings += notes
    return candidates, warnings, len(frame)


def build_fixed_heads(ctx: BcContext) -> PackageInput:
    groups = _station_groups(ctx)
    lines, line_warnings, n_lines = _features(ctx, LINES, groups, _line)
    areas, area_warnings, n_areas = _features(ctx, AREAS, groups, _area)
    taken: dict[Cell, _Candidate] = {}
    clashes: list[tuple[_Candidate, _Candidate]] = []
    for candidate in lines + areas:
        first = taken.get(candidate.cell)
        if first is None:
            taken[candidate.cell] = candidate
        elif first.boundname != candidate.boundname:
            clashes.append((first, candidate))
    warnings = line_warnings + area_warnings
    if clashes:
        first, second = clashes[0]
        k, r, c = second.cell
        warnings.append(
            Problem.from_code(
                "bc.chd_overlap",
                {
                    "n_cells": len({b.cell for _, b in clashes}),
                    "layer": k + 1,
                    "row": r + 1,
                    "col": c + 1,
                    "first": first.label,
                    "second": second.label,
                },
                ref=second.ref,
            )
        )
    assignments = tuple(
        Assignment(c.cell, c.forcing, 1.0, c.boundname, c.ref, c.label) for c in taken.values()
    )
    return PackageInput("chd", "chd", assignments, tuple(warnings), n_lines + n_areas)


TYPE = BoundaryConditionType(
    name="chd",
    label=Localized("Carichi imposti", "Fixed heads"),
    package="chd",
    layers=(LINES, AREAS, STATIONS),
    build=build_fixed_heads,
)
