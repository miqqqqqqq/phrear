"""Wells as MF6 WEL entries (docs/SPEC.md, section 12).

A well goes to the column that contains it. Its rate is shared among the active
layers crossed by the screen in proportion to the transmissivity of each screened
part, T_k = K_k · l_k with l_k the screen length inside layer k, so that a
screen across several layers draws more where the aquifer is more permeable.
The share uses the geometry of the cells, not the saturated thickness during the
run. Extraction is negative in MF6: the sign goes in the multiplier, the rate
stays as entered.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from phrear.boundaries.base import (
    Assignment,
    BcContext,
    BoundaryConditionType,
    Forcing,
    PackageInput,
    layer_label,
)
from phrear.errors import BoundaryError, Localized, ObjectRef, PhrearError, UnitError
from phrear.events import Problem
from phrear.project.features import feature_label, fmt, number, text
from phrear.units import PhysicalQuantity, conversion_factor

LAYER = "wells"
_TOL = 1e-3
"""Screen length outside the active cells below which no warning is given, m."""


def _ref(fid: int, field: str | None = None) -> ObjectRef:
    if field is None:
        return ObjectRef(kind="feature", layer=LAYER, fid=fid)
    return ObjectRef(kind="field", layer=LAYER, fid=fid, field=field)


def _screen(fid: int, label: str, row: Any) -> tuple[float, float]:
    """Screen top and bottom as elevations, m a.s.l."""
    top, bottom = number(row["screen_top"]), number(row["screen_bottom"])
    if top is None or bottom is None:
        field = "screen_top" if top is None else "screen_bottom"
        raise BoundaryError(
            "bc.value_missing",
            feature=label,
            layer=layer_label(LAYER),
            field=field,
            ref=_ref(fid, field),
        )
    if (text(row["depth_mode"]) or "depth") == "depth":
        z_ref = number(row["z_ref"])
        if z_ref is None:
            raise BoundaryError("bc.z_ref_missing", feature=label, ref=_ref(fid, "z_ref"))
        top, bottom = z_ref - top, z_ref - bottom
    if top <= bottom:
        raise BoundaryError(
            "bc.screen_order",
            feature=label,
            top=fmt(top),
            bottom=fmt(bottom),
            ref=_ref(fid, "screen_bottom"),
        )
    return top, bottom


def _forcing(ctx: BcContext, fid: int, label: str, row: Any) -> Forcing:
    series_id = text(row["series_id"])
    if series_id is not None:
        forcing = ctx.series_forcing(
            series_id,
            PhysicalQuantity.DISCHARGE,
            feature=label,
            layer=LAYER,
            ref=_ref(fid, "series_id"),
        )
        assert forcing.series is not None
        if np.any(forcing.series.values < 0):
            raise BoundaryError(
                "bc.negative_series",
                series_id=series_id,
                feature=label,
                ref=forcing.series.ref,
            )
        return forcing
    rate = number(row["rate"])
    if rate is None:
        raise BoundaryError(
            "bc.value_missing",
            feature=label,
            layer=layer_label(LAYER),
            field="rate",
            ref=_ref(fid, "rate"),
        )
    if rate < 0:
        raise BoundaryError(
            "bc.negative_rate", feature=label, value=fmt(rate), ref=_ref(fid, "rate")
        )
    unit = text(row["rate_unit"])
    if unit is None:
        raise BoundaryError(
            "bc.unit_missing",
            feature=label,
            layer=layer_label(LAYER),
            field="rate",
            unit_field="rate_unit",
            ref=_ref(fid, "rate_unit"),
        )
    try:
        factor = conversion_factor(unit, PhysicalQuantity.DISCHARGE)
    except UnitError as exc:
        raise UnitError(
            exc.code, ref=_ref(fid, "rate_unit"), detail=exc.detail, **exc.fields
        ) from exc
    return Forcing.of_constant(rate * factor)


def _well(ctx: BcContext, fid: int, row: Any) -> tuple[list[Assignment], list[Problem]]:
    grid = ctx.grid
    label = feature_label(row["name"], fid)
    ref = _ref(fid)
    if (text(row["model_as"]) or "auto") == "maw":
        raise BoundaryError("bc.maw_not_available", feature=label, ref=_ref(fid, "model_as"))
    geom = row.geometry
    if geom is None or geom.is_empty:
        raise BoundaryError("bc.geometry_missing", feature=label, layer=layer_label(LAYER), ref=ref)
    cell = ctx.cells.point_cell(geom.x, geom.y)
    if cell is None or not ctx.active_columns[cell]:
        raise BoundaryError("bc.outside_active", feature=label, layer=layer_label(LAYER), ref=ref)
    r, c = cell
    top, bottom = _screen(fid, label, row)
    cell_tops = np.concatenate([[grid.top[r, c]], grid.botm[:-1, r, c]])
    lengths = np.clip(
        np.minimum(top, cell_tops) - np.maximum(bottom, grid.botm[:, r, c]), 0.0, None
    )
    lengths[grid.idomain[:, r, c] <= 0] = 0.0
    transmissivity = ctx.layers.k[:, r, c] * lengths
    total = float(transmissivity.sum())
    if total <= 0.0:
        raise BoundaryError(
            "bc.screen_outside",
            feature=label,
            top=fmt(top),
            bottom=fmt(bottom),
            row=r + 1,
            col=c + 1,
            ref=ref,
        )
    warnings: list[Problem] = []
    inside = float(lengths.sum())
    if (top - bottom) - inside > _TOL:
        warnings.append(
            Problem.from_code(
                "bc.screen_clipped",
                {"feature": label, "length": fmt(top - bottom), "inside": fmt(inside)},
                ref=ref,
            )
        )
    forcing = _forcing(ctx, fid, label, row)
    sign = 1.0 if text(row["role"]) == "injection" else -1.0
    assignments = [
        Assignment(
            (int(k), r, c),
            forcing,
            sign * float(transmissivity[k]) / total,
            f"well_{fid}",
            ref,
            label,
        )
        for k in np.flatnonzero(transmissivity > 0.0)
    ]
    return assignments, warnings


def build_wells(ctx: BcContext) -> PackageInput:
    frame = ctx.features(LAYER)
    assignments: list[Assignment] = []
    warnings: list[Problem] = []
    for fid, row in frame.iterrows():
        try:
            found, notes = _well(ctx, int(fid), row)
        except PhrearError as exc:
            ctx.errors.fail(exc)
            continue
        assignments += found
        warnings += notes
    return PackageInput("wel", "wel", tuple(assignments), tuple(warnings), len(frame))


TYPE = BoundaryConditionType(
    name="wel",
    label=Localized("Pozzi", "Wells"),
    package="wel",
    layers=(LAYER,),
    build=build_wells,
)
