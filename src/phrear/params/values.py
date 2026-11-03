"""Hydrogeological parameters of the units (docs/SPEC.md, section 11).

Milestone M1a supports uniform values per unit. Each value is read from
``param_values`` with its own unit, converted to internal units (m/d for K, 1/m
for Ss, dimensionless for Sy, n_e and Kv/Kh) and kept with its provenance.

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
from typing import Final

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
class UnitParameters:
    unit_fid: int
    position: int
    name: str
    convertible: bool
    values: dict[str, ParamValue]

    @property
    def label(self) -> str:
        return f"{self.position} ({self.name})"

    @property
    def kh(self) -> float:
        return self.values["kh"].value

    @property
    def kv(self) -> float:
        """Vertical K, m/d, given directly or as Kv/Kh · Kh."""
        if "kv" in self.values:
            return self.values["kv"].value
        return self.values["anisotropy"].value * self.kh

    @property
    def ss(self) -> float:
        return self.values["ss"].value

    @property
    def sy(self) -> float | None:
        return self.values["sy"].value if "sy" in self.values else None

    @property
    def ne(self) -> float | None:
        return self.values["ne"].value if "ne" in self.values else None


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


def _row_value(row: _Row, unit_label: str) -> ParamValue:
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


def _check(unit: UnitParameters, errors: ErrorCollector) -> list[Problem]:
    warnings: list[Problem] = []
    for param, pv in unit.values.items():
        label = PARAM_LABELS[param]
        fields: dict[str, FieldValue] = {
            "param": label,
            "unit": unit.label,
            "value": _fmt(pv.original_value),
        }
        value = _fmt(pv.original_value)
        if param in FRACTIONS and not 0.0 < pv.value < 1.0:
            errors.fail(
                ParameterError(
                    "params.not_fraction", param=label, unit=unit.label, value=value, ref=pv.ref
                )
            )
            continue
        if param not in FRACTIONS and pv.value <= 0.0:
            errors.fail(
                ParameterError(
                    "params.not_positive", param=label, unit=unit.label, value=value, ref=pv.ref
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
    if not {"kh", "kv"} <= unit.values.keys() and not {"kh", "anisotropy"} <= unit.values.keys():
        return warnings
    if unit.kv > unit.kh * (1 + 1e-12):
        warnings.append(
            Problem.from_code(
                "params.kv_above_kh", {"unit": unit.label, "kv": _fmt(unit.kv), "kh": _fmt(unit.kh)}
            )
        )
    return warnings


def load_parameters(project: Project, errors: ErrorCollector | None = None) -> ParameterSet:
    """Uniform parameters of every unit, validated and in internal units.

    With a collecting ``errors``, every row and unit is checked and the errors are
    gathered; the returned set is then usable only if none was found.
    """
    errors = errors or ErrorCollector()
    with gpkg.connect(project.gpkg_path) as conn:
        units = conn.execute(
            'SELECT fid, position, name, param_mode, convertible FROM "hydro_units" '
            "ORDER BY position"
        ).fetchall()
        rows = conn.execute(
            'SELECT fid, object_id, param, value, raster_path, unit, source, "min", "max", '
            'object_type FROM "param_values" ORDER BY fid'
        ).fetchall()
    unit_fids = {u[0] for u in units}
    by_unit: dict[int, list[_Row]] = {}
    for *row, object_type in rows:
        fid, object_id = row[0], row[1]
        if object_type != "unit":
            errors.fail(
                ParameterError(
                    "params.source_not_available",
                    param=PARAM_LABELS.get(row[2], Localized(str(row[2]), str(row[2]))),
                    unit=str(object_id),
                    what=Localized("una zona", "a zone"),
                    ref=ObjectRef(kind="field", layer="param_values", fid=fid, field="object_type"),
                )
            )
            continue
        if object_id not in unit_fids:
            errors.fail(
                ParameterError(
                    "params.unknown_unit",
                    fid=object_id,
                    ref=ObjectRef(kind="field", layer="param_values", fid=fid, field="object_id"),
                )
            )
            continue
        by_unit.setdefault(object_id, []).append(tuple(row))

    result: list[UnitParameters] = []
    warnings: list[Problem] = []
    for fid, position, name, mode, convertible in units:
        label = f"{position} ({name})"
        ref = ObjectRef(kind="field", layer="hydro_units", fid=fid, field="param_mode")
        if (mode or "uniform") != "uniform":
            errors.fail(
                ParameterError("params.mode_not_available", unit=label, mode=str(mode), ref=ref)
            )
            continue
        values: dict[str, ParamValue] = {}
        failed: set[str] = set()
        for row in by_unit.get(fid, []):
            try:
                values[row[2]] = _row_value(row, label)
            except PhrearError as exc:
                failed.add(row[2])
                errors.fail(exc)
        is_convertible = True if convertible is None else bool(convertible)
        unit_ref = ObjectRef(kind="table", layer="hydro_units", fid=fid)
        required = ["kh", "ss"] + (["sy"] if is_convertible else [])
        for param in required:
            if param not in values and param not in failed:
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
        vertical = {"kv", "anisotropy"}
        if not (vertical & (values.keys() | failed)):
            errors.fail(ParameterError("params.kv_or_anisotropy", unit=label, ref=unit_ref))
        if vertical <= values.keys():
            errors.fail(
                ParameterError("params.kv_and_anisotropy", unit=label, ref=values["anisotropy"].ref)
            )
        unit = UnitParameters(fid, position, name, is_convertible, values)
        warnings += _check(unit, errors)
        result.append(unit)
    return ParameterSet(tuple(result), tuple(warnings))
