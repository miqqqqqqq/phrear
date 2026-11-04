"""Parameters cell by cell, from the uniform values and the zones of each unit.

The sources of a parameter combine in every column of the grid (ADR 0024):

- each zone of the unit covers a fraction of the cell area (``CellIndex``);
- the uniform value of the unit, when given, covers the rest of the cell;
- the value of the cell is the area-weighted mean over the covered part:
  geometric for K and for the ratio Kv/Kh, arithmetic for Ss, Sy and n_e
  (docs/SPEC.md, section 11).

Rasters (increment 3) and the field interpolated from tests (increment 5) take
precedence where they have values. Zones of the same unit must not overlap. An
active cell without any value for a required parameter is an error.

Fields are per unit and per column: the sublayers of a unit share them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt
import shapely

from phrear.boundaries.geometry import CellIndex
from phrear.errors import ErrorCollector, ObjectRef, ParameterError
from phrear.grid.model_grid import ModelGrid
from phrear.params.values import PARAM_LABELS, ParameterSet, UnitParameters

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

#: Parameters averaged geometrically; the others arithmetically.
GEOMETRIC: Final = frozenset({"kh", "kv", "anisotropy"})
#: Origin of the value of a cell, by the source with the largest share.
NONE, UNIFORM, ZONE = 0, 1, 2
ORIGINS: Final = {NONE: "none", UNIFORM: "uniform", ZONE: "zone"}
_EPS: Final = 1e-9
#: Overlap between two zones that counts as an error, as a fraction of a cell area.
_OVERLAP: Final = 1e-6


@dataclass(frozen=True)
class ParamField:
    """One parameter of one unit over the columns of the grid, shape (nrow, ncol)."""

    values: FloatArray
    """Internal units; NaN where no source covers the cell."""
    origin: IntArray
    """Source with the largest share: ``NONE``, ``UNIFORM`` or ``ZONE``."""
    zone: IntArray
    """fid of that zone, 0 when the origin is not a zone."""
    share: FloatArray
    """Fraction of the covered part that the main source accounts for."""
    sources: IntArray
    """Number of sources that contribute to the cell."""

    @property
    def defined(self) -> npt.NDArray[np.bool_]:
        return ~np.isnan(self.values)


@dataclass(frozen=True)
class UnitCells:
    unit: UnitParameters
    active: npt.NDArray[np.bool_]
    """Columns where at least one layer of the unit is active."""
    fields: dict[str, ParamField]
    """kh, kv (given or from Kv/Kh), ss, and sy, ne, anisotropy when available."""


@dataclass(frozen=True)
class CellParameters:
    units: dict[int, UnitCells]
    """By unit position."""


def _field(
    shape: tuple[int, int],
    unit: UnitParameters,
    param: str,
    pieces: dict[int, list[tuple[int, int, float]]],
) -> ParamField | None:
    zones = [z for z in unit.zones if param in z.values]
    uniform = unit.uniform(param)
    if uniform is None and not zones:
        return None
    geometric = param in GEOMETRIC
    total = np.zeros(shape)
    weight = np.zeros(shape)
    covered = np.zeros(shape)
    best = np.zeros(shape)
    origin = np.full(shape, NONE, dtype=np.int64)
    zone_fid = np.zeros(shape, dtype=np.int64)
    sources = np.zeros(shape, dtype=np.int64)
    single = np.full(shape, np.nan)  # the value itself where only one source contributes
    for zone in zones:
        value = zone.values[param].value
        term = np.log(value) if geometric else value
        for row, col, fraction in pieces[zone.fid]:
            total[row, col] += fraction * term
            weight[row, col] += fraction
            covered[row, col] += fraction
            sources[row, col] += 1
            single[row, col] = value
            if fraction > best[row, col]:
                best[row, col] = fraction
                origin[row, col] = ZONE
                zone_fid[row, col] = zone.fid
    if uniform is not None:
        rest = np.clip(1.0 - covered, 0.0, 1.0)
        rest[rest < _EPS] = 0.0
        term = np.log(uniform) if geometric else uniform
        total += rest * term
        weight += rest
        sources += rest > 0.0
        single = np.where(rest > 0.0, uniform, single)
        wins = rest > best
        best = np.where(wins, rest, best)
        origin = np.where(wins, UNIFORM, origin)
        zone_fid = np.where(wins, 0, zone_fid)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(weight > _EPS, total / weight, np.nan)
        share = np.where(weight > _EPS, best / weight, 0.0)
    values = np.exp(mean) if geometric else mean
    # One source: its value exactly, without the round trip through the logarithm.
    values = np.where(sources == 1, single, values)
    return ParamField(values, origin, zone_fid, share, sources)


def _overlaps(unit: UnitParameters, cell_area: float, errors: ErrorCollector) -> None:
    zones = list(unit.zones)
    if len(zones) < 2:
        return
    tree = shapely.STRtree([z.geometry for z in zones])
    for i, first in enumerate(zones):
        for j in tree.query(first.geometry, predicate="intersects"):
            if j <= i:
                continue
            second = zones[int(j)]
            area = float(shapely.area(shapely.intersection(first.geometry, second.geometry)))
            if area > _OVERLAP * cell_area:
                errors.fail(
                    ParameterError(
                        "params.zones_overlap",
                        first=first.label,
                        second=second.label,
                        unit=unit.label,
                        area=f"{area:.0f}",
                        ref=ObjectRef(kind="feature", layer="param_zones", fid=second.fid),
                    )
                )


def unit_cells(
    grid: ModelGrid, index: CellIndex, unit: UnitParameters, errors: ErrorCollector
) -> UnitCells:
    g = grid.geometry
    shape = (g.nrow, g.ncol)
    layers = [k for k, position in enumerate(grid.layer_unit) if position == unit.position]
    active = np.any(grid.idomain[layers] > 0, axis=0) if layers else np.zeros(shape, dtype=bool)
    _overlaps(unit, g.cell_size**2, errors)
    pieces = {
        z.fid: [(p.row, p.col, p.fraction) for p in index.area_pieces(z.geometry)]
        for z in unit.zones
    }
    fields: dict[str, ParamField] = {}
    for param in ("kh", "kv", "anisotropy", "ss", "sy", "ne"):
        found = _field(shape, unit, param, pieces)
        if found is not None:
            fields[param] = found
    if unit.vertical == "anisotropy" and "anisotropy" in fields and "kh" in fields:
        ratio, kh = fields["anisotropy"], fields["kh"]
        fields["kv"] = ParamField(
            ratio.values * kh.values, ratio.origin, ratio.zone, ratio.share, ratio.sources
        )
    # Kv from the ratio is defined where K and the ratio are: check the ratio itself.
    required = ["kh", unit.vertical, "ss"] + (["sy"] if unit.convertible else [])
    unit_ref = ObjectRef(kind="table", layer="hydro_units", fid=unit.unit_fid)
    for param in required:
        found = fields.get(param)
        if found is None:
            continue  # reported by load_parameters
        missing = int(np.count_nonzero(active & ~found.defined))
        if missing:
            errors.fail(
                ParameterError(
                    "params.cells_without_value",
                    param=PARAM_LABELS[param],
                    unit=unit.label,
                    n_cells=missing,
                    ref=unit_ref,
                )
            )
    return UnitCells(unit, active, fields)


def assign_cells(
    grid: ModelGrid, params: ParameterSet, errors: ErrorCollector | None = None
) -> CellParameters:
    """Every parameter of every unit in every column; errors as in ``load_parameters``."""
    errors = errors or ErrorCollector()
    index = CellIndex(grid.geometry)
    units = {u.position: unit_cells(grid, index, u, errors) for u in params.units}
    return CellParameters(units)
