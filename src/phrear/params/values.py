"""Hydrogeological parameters of the units (docs/SPEC.md, section 11).

Each value is read from ``param_values`` with its own unit, converted to internal
units (m/d for K, 1/m for Ss, dimensionless for Sy, n_e and Kv/Kh) and kept with
its provenance. A value belongs to a unit (uniform value) or to a zone of a unit
(``param_zones``); ``params.cells`` combines them cell by cell (ADR 0024).

Required for flow: K horizontal, K vertical or the ratio Kv/Kh, Ss, and Sy for
convertible units. n_e is optional until particle tracking (M5).

Checks:
- errors: missing parameter or unit of measure, both Kv and Kv/Kh, non-positive K
  or Ss, Sy and n_e outside (0, 1);
- warnings: value outside the declared [min, max], value outside general plausible
  ranges, Kv > Kh. Lithology-specific ranges come with the borehole data (M8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

import shapely

from phrear.errors import (
    ErrorCollector,
    FieldValue,
    Localized,
    ObjectRef,
    ParameterError,
    PhrearError,
    UnitError,
)
from phrear.events import Problem
from phrear.project import Project, gpkg
from phrear.project.features import feature_label, is_null, read_features
from phrear.project.schema import PARAM_QUANTITIES, TABLES_BY_NAME
from phrear.units import INTERNAL_UNITS_DISPLAY, PhysicalQuantity, conversion_factor

PARAM_LABELS: dict[str, Localized] = {
    c.value: c.label for c in TABLES_BY_NAME["param_values"].field("param").choices
}

#: General plausible ranges in internal units (not lithology-specific).
PLAUSIBLE: Final[dict[str, tuple[float, float]]] = {
    "kh": (1e-11 * 86400, 1e-1 * 86400),  # 1e-11 – 1e-1 m/s
    "kv": (1e-11 * 86400, 1e-1 * 86400),
    "anisotropy": (1e-4, 10.0),  # Kv > Kh has its own warning
    "ss": (1e-7, 1e-2),
    "sy": (0.01, 0.40),
    "ne": (0.01, 0.50),
}
FRACTIONS: Final = {"sy", "ne"}

_Row = tuple[
    int, int, str, float | None, str | None, str | None, str | None, float | None, float | None
]
"""fid, object_id, param, value, raster_path, unit, source, min, max."""


@dataclass(frozen=True)
class ParamValue:
    param: str
    value: float
    """Internal units."""
    original_value: float
    original_unit: str
    source: str | None
    minimum: float | None
    maximum: float | None
    fid: int

    @property
    def ref(self) -> ObjectRef:
        return ObjectRef(kind="field", layer="param_values", fid=self.fid, field="value")


@dataclass(frozen=True)
class ZoneParameters:
    """A zone of a unit with its own values, which prevail inside the zone."""

    fid: int
    unit_fid: int
    name: str | None
    geometry: shapely.Geometry
    values: dict[str, ParamValue]

    @property
    def label(self) -> str:
        return feature_label(self.name, self.fid)


@dataclass(frozen=True)
class UnitParameters:
    unit_fid: int
    position: int
    name: str
    convertible: bool
    values: dict[str, ParamValue]
    """Uniform values of the unit; a parameter may instead come only from zones."""
    zones: tuple[ZoneParameters, ...] = ()
    vertical: str = "anisotropy"
    """How vertical K is given in this unit and its zones: ``kv`` or ``anisotropy``."""
    max_distance: float | None = None
    """``interp_max_distance`` of the unit, m (interpolation from field tests)."""

    @property
    def label(self) -> str:
        return f"{self.position} ({self.name})"

    def has(self, param: str) -> bool:
        """True if the parameter has a uniform value or a value in some zone."""
        return param in self.values or any(param in z.values for z in self.zones)

    def uniform(self, param: str) -> float | None:
        return self.values[param].value if param in self.values else None

    @property
    def kh(self) -> float:
        return self.values["kh"].value

    @property
    def kv(self) -> float:
        """Uniform vertical K, m/d, given directly or as Kv/Kh · Kh."""
        if "kv" in self.values:
            return self.values["kv"].value
        return self.values["anisotropy"].value * self.kh

    @property
    def ss(self) -> float:
        return self.values["ss"].value

    @property
    def sy(self) -> float | None:
        return self.uniform("sy")

    @property
    def ne(self) -> float | None:
        return self.uniform("ne")


@dataclass(frozen=True)
class ParameterSet:
    units: tuple[UnitParameters, ...]
    warnings: tuple[Problem, ...] = field(default_factory=tuple)

    def by_position(self, position: int) -> UnitParameters:
        for unit in self.units:
            if unit.position == position:
                return unit
        raise KeyError(position)


def _fmt(value: float) -> str:
    return f"{value:.4g}"


def _row_value(row: _Row, unit_label: FieldValue) -> ParamValue:
    fid, _, param, value, raster, unit_text, source, low, high = row
    label = PARAM_LABELS[param]
    if raster:
        raise ParameterError(
            "params.source_not_available",
            param=label,
            unit=unit_label,
            what=Localized("un raster", "a raster"),
            ref=ObjectRef(kind="field", layer="param_values", fid=fid, field="raster_path"),
        )
    if value is None:
        raise ParameterError(
            "params.value_missing",
            param=label,
            unit=unit_label,
            ref=ObjectRef(kind="field", layer="param_values", fid=fid, field="value"),
        )
    quantity = PARAM_QUANTITIES[param]
    if not unit_text and quantity is not PhysicalQuantity.DIMENSIONLESS:
        raise ParameterError(
            "params.unit_missing",
            param=label,
            unit=unit_label,
            example=INTERNAL_UNITS_DISPLAY[quantity],
            ref=ObjectRef(kind="field", layer="param_values", fid=fid, field="unit"),
        )
    try:
        factor = conversion_factor(unit_text or "", quantity)
    except UnitError as exc:
        ref = ObjectRef(kind="field", layer="param_values", fid=fid, field="unit")
        raise UnitError(exc.code, ref=ref, detail=exc.detail, **exc.fields) from exc
    return ParamValue(
        param=param,
        value=float(value) * factor,
        original_value=float(value),
        original_unit=unit_text or "",
        source=source,
        minimum=low,
        maximum=high,
        fid=fid,
    )


def _check(
    owner: FieldValue, values: dict[str, ParamValue], errors: ErrorCollector
) -> list[Problem]:
    """Checks on the values of a unit or of a zone (``owner`` names it in messages)."""
    warnings: list[Problem] = []
    for param, pv in values.items():
        label = PARAM_LABELS[param]
        fields: dict[str, FieldValue] = {
            "param": label,
            "unit": owner,
            "value": _fmt(pv.original_value),
        }
        value = _fmt(pv.original_value)
        if param in FRACTIONS and not 0.0 < pv.value < 1.0:
            errors.fail(
                ParameterError(
                    "params.not_fraction", param=label, unit=owner, value=value, ref=pv.ref
                )
            )
            continue
        if param not in FRACTIONS and pv.value <= 0.0:
            errors.fail(
                ParameterError(
                    "params.not_positive", param=label, unit=owner, value=value, ref=pv.ref
                )
            )
            continue
        if (pv.minimum is not None and pv.original_value < pv.minimum) or (
            pv.maximum is not None and pv.original_value > pv.maximum
        ):
            warnings.append(
                Problem.from_code(
                    "params.outside_declared_range",
                    {
                        **fields,
                        "low": "-∞" if pv.minimum is None else _fmt(pv.minimum),
                        "high": "+∞" if pv.maximum is None else _fmt(pv.maximum),
                    },
                    ref=pv.ref,
                )
            )
        low, high = PLAUSIBLE[param]
        if not low <= pv.value <= high:
            internal = INTERNAL_UNITS_DISPLAY[PARAM_QUANTITIES[param]]
            warnings.append(
                Problem.from_code(
                    "params.implausible",
                    {
                        **fields,
                        "value": _fmt(pv.value),
                        "internal": internal,
                        "low": _fmt(low),
                        "high": _fmt(high),
                    },
                    ref=pv.ref,
                )
            )
    if "kh" not in values or not ({"kv", "anisotropy"} & values.keys()):
        return warnings
    kh = values["kh"].value
    kv = values["kv"].value if "kv" in values else values["anisotropy"].value * kh
    if kv > kh * (1 + 1e-12):
        warnings.append(
            Problem.from_code("params.kv_above_kh", {"unit": owner, "kv": _fmt(kv), "kh": _fmt(kh)})
        )
    return warnings


def _read_zones(project: Project) -> tuple[dict[int, tuple[Any, ...]], set[int]]:
    """Active zones of the base model by fid, and the fids of every zone."""
    frame = read_features(project, "param_zones")
    with gpkg.connect(project.gpkg_path) as conn:
        every = {int(r[0]) for r in conn.execute('SELECT fid FROM "param_zones"')}
    zones: dict[int, tuple[Any, ...]] = {}
    for fid, row in frame.iterrows():
        unit = None if is_null(row["unit_id"]) else int(row["unit_id"])
        zones[int(fid)] = (unit, row["name"], row.geometry)
    return zones, every


def load_parameters(project: Project, errors: ErrorCollector | None = None) -> ParameterSet:
    """Uniform and zone values of every unit, validated and in internal units.

    With a collecting ``errors``, every row, zone and unit is checked and the
    errors are gathered; the returned set is then usable only if none was found.
    """
    errors = errors or ErrorCollector()
    with gpkg.connect(project.gpkg_path) as conn:
        units = conn.execute(
            "SELECT fid, position, name, k_from_tests, convertible, interp_max_distance "
            'FROM "hydro_units" ORDER BY position'
        ).fetchall()
        rows = conn.execute(
            'SELECT fid, object_id, param, value, raster_path, unit, source, "min", "max", '
            'object_type FROM "param_values" ORDER BY fid'
        ).fetchall()
    zones, every_zone = _read_zones(project)
    unit_by_fid = {u[0]: u for u in units}
    by_unit: dict[int, list[_Row]] = {}
    by_zone: dict[int, list[_Row]] = {}
    for *row, object_type in rows:
        fid, object_id = row[0], row[1]
        if (object_type or "unit") == "zone":  # empty means the schema default, unit
            if object_id in zones:
                by_zone.setdefault(object_id, []).append(tuple(row))
            elif object_id not in every_zone:
                errors.fail(
                    ParameterError(
                        "params.unknown_zone",
                        fid=object_id,
                        ref=ObjectRef(
                            kind="field", layer="param_values", fid=fid, field="object_id"
                        ),
                    )
                )
            continue  # rows of inactive zones and of scenario zones are not used
        if object_id not in unit_by_fid:
            errors.fail(
                ParameterError(
                    "params.unknown_unit",
                    fid=object_id,
                    ref=ObjectRef(kind="field", layer="param_values", fid=fid, field="object_id"),
                )
            )
            continue
        by_unit.setdefault(object_id, []).append(tuple(row))

    zones_of_unit: dict[int, list[ZoneParameters]] = {}
    warnings: list[Problem] = []
    for zone_fid, (unit_fid, zone_name, geometry) in zones.items():
        zone_ref = ObjectRef(kind="feature", layer="param_zones", fid=zone_fid)
        label = feature_label(zone_name, zone_fid)
        if unit_fid not in unit_by_fid:
            errors.fail(
                ParameterError(
                    "params.zone_unknown_unit",
                    zone=label,
                    fid=str(unit_fid),
                    ref=ObjectRef(kind="field", layer="param_zones", fid=zone_fid, field="unit_id"),
                )
            )
            continue
        if geometry is None or not shapely.is_valid(geometry) or geometry.is_empty:
            reason = "" if geometry is None else shapely.is_valid_reason(geometry)
            errors.fail(
                ParameterError("params.zone_invalid", zone=label, reason=reason, ref=zone_ref)
            )
            continue
        _, position, unit_name = unit_by_fid[unit_fid][:3]
        owner = Localized(
            f"{position} ({unit_name}), zona {label}", f"{position} ({unit_name}), zone {label}"
        )
        values: dict[str, ParamValue] = {}
        for row in by_zone.get(zone_fid, []):
            try:
                values[row[2]] = _row_value(row, owner)
            except PhrearError as exc:
                errors.fail(exc)
        if not by_zone.get(zone_fid):
            warnings.append(Problem.from_code("params.zone_empty", {"zone": label}, ref=zone_ref))
        warnings += _check(owner, values, errors)
        zones_of_unit.setdefault(unit_fid, []).append(
            ZoneParameters(zone_fid, unit_fid, zone_name, geometry, values)
        )

    result: list[UnitParameters] = []
    for fid, position, name, from_tests, convertible, max_distance in units:
        label = f"{position} ({name})"
        if from_tests:
            ref = ObjectRef(kind="field", layer="hydro_units", fid=fid, field="k_from_tests")
            mode = Localized("K interpolata dalle prove", "K interpolated from tests")
            errors.fail(ParameterError("params.mode_not_available", unit=label, mode=mode, ref=ref))
            continue
        values = {}
        failed: set[str] = set()
        for row in by_unit.get(fid, []):
            try:
                values[row[2]] = _row_value(row, label)
            except PhrearError as exc:
                failed.add(row[2])
                errors.fail(exc)
        unit_zones = tuple(zones_of_unit.get(fid, []))
        given = values.keys() | failed | {p for z in unit_zones for p in z.values}
        is_convertible = True if convertible is None else bool(convertible)
        unit_ref = ObjectRef(kind="table", layer="hydro_units", fid=fid)
        required = ["kh", "ss"] + (["sy"] if is_convertible else [])
        for param in required:
            if param not in given:
                errors.fail(
                    ParameterError(
                        "params.missing",
                        param=PARAM_LABELS[param],
                        unit=label,
                        fid=fid,
                        param_code=param,
                        ref=unit_ref,
                    )
                )
        vertical = {"kv", "anisotropy"} & given
        if not vertical:
            errors.fail(ParameterError("params.kv_or_anisotropy", unit=label, ref=unit_ref))
        if len(vertical) == 2:
            every = [*values.values(), *(pv for z in unit_zones for pv in z.values.values())]
            refs = [pv.ref for pv in every if pv.param == "anisotropy"]
            ref = refs[0] if refs else unit_ref
            errors.fail(ParameterError("params.kv_and_anisotropy", unit=label, ref=ref))
        unit = UnitParameters(
            fid,
            position,
            name,
            is_convertible,
            values,
            unit_zones,
            vertical="kv" if vertical == {"kv"} else "anisotropy",
            max_distance=None if max_distance is None else float(max_distance),
        )
        warnings += _check(label, values, errors)
        result.append(unit)
    return ParameterSet(tuple(result), tuple(warnings))
