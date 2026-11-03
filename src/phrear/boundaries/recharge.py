"""Recharge zones as MF6 RCH entries (docs/SPEC.md, section 12).

Each zone gives its rate to the uppermost active cell of every column it covers,
with the covered fraction of the cell as multiplier, so the recharged volume is
rate × covered area exactly. Overlapping zones add up, with a warning. A zone
partly outside the model is normal; a zone that covers no active cell gets a
warning.
"""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import shapely

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

LAYER = "recharge_zones"
_MIN_OVERLAP = 0.01
"""Overlap below this fraction of a cell area is ignored (digitising tolerance)."""


def _ref(fid: int, field: str | None = None) -> ObjectRef:
    if field is None:
        return ObjectRef(kind="feature", layer=LAYER, fid=fid)
    return ObjectRef(kind="field", layer=LAYER, fid=fid, field=field)


def _forcing(ctx: BcContext, fid: int, label: str, row: Any) -> Forcing:
    series_id = text(row["series_id"])
    if series_id is not None:
        return ctx.series_forcing(
            series_id,
            PhysicalQuantity.VELOCITY,
            feature=label,
            layer=LAYER,
            ref=_ref(fid, "series_id"),
        )
    rate = number(row["rate"])
    if rate is None:
        raise BoundaryError(
            "bc.value_missing",
            feature=label,
            layer=layer_label(LAYER),
            field="rate",
            ref=_ref(fid, "rate"),
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
        factor = conversion_factor(unit, PhysicalQuantity.VELOCITY)
    except UnitError as exc:
        raise UnitError(
            exc.code, ref=_ref(fid, "rate_unit"), detail=exc.detail, **exc.fields
        ) from exc
    return Forcing.of_constant(rate * factor)


def _active_area(ctx: BcContext, polygon: shapely.Geometry) -> float:
    """Area of the polygon over active columns, m²."""
    cell_area = ctx.grid.geometry.cell_size**2
    return sum(
        p.fraction * cell_area
        for p in ctx.cells.area_pieces(polygon)
        if ctx.active_columns[p.row, p.col]
    )


def build_recharge(ctx: BcContext) -> PackageInput:
    idomain = ctx.grid.idomain
    active = idomain > 0
    uppermost = np.where(active.any(axis=0), active.argmax(axis=0), -1)
    frame = ctx.features(LAYER)
    assignments: list[Assignment] = []
    warnings: list[Problem] = []
    zones: list[tuple[str, shapely.Geometry, ObjectRef]] = []
    for fid, row in frame.iterrows():
        fid = int(fid)
        label = feature_label(row["name"], fid)
        ref = _ref(fid)
        polygon = row.geometry
        try:
            if polygon is None or polygon.is_empty:
                raise BoundaryError(
                    "bc.geometry_missing", feature=label, layer=layer_label(LAYER), ref=ref
                )
            forcing = _forcing(ctx, fid, label, row)
        except PhrearError as exc:
            ctx.errors.fail(exc)
            continue
        found = False
        for piece in ctx.cells.area_pieces(polygon):
            k = int(uppermost[piece.row, piece.col])
            if k < 0:
                continue
            found = True
            assignments.append(
                Assignment(
                    (k, piece.row, piece.col), forcing, piece.fraction, f"rch_{fid}", ref, label
                )
            )
        if not found:
            warnings.append(Problem.from_code("bc.zone_outside", {"feature": label}, ref=ref))
        zones.append((label, polygon, ref))
    cell_area = ctx.grid.geometry.cell_size**2
    for (la, pa, _), (lb, pb, rb) in itertools.combinations(zones, 2):
        if not shapely.intersects(pa, pb):
            continue
        area = _active_area(ctx, shapely.intersection(pa, pb))
        if area > _MIN_OVERLAP * cell_area:
            warnings.append(
                Problem.from_code(
                    "bc.zone_overlap", {"first": la, "second": lb, "area": fmt(area)}, ref=rb
                )
            )
    return PackageInput("rch", "rch", tuple(assignments), tuple(warnings), len(frame))


TYPE = BoundaryConditionType(
    name="rch",
    label=Localized("Ricarica", "Recharge"),
    package="rch",
    layers=(LAYER,),
    build=build_recharge,
)
