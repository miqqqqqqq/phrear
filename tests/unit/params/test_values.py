"""Uniform parameters per unit: conversion, required values, checks."""

from __future__ import annotations

from typing import Any

import pytest

from phrear.errors import ParameterError, UnitError
from phrear.params.values import load_parameters
from phrear.project import Project, gpkg

from .conftest import VALID, AddParam, unit_fid


def _codes(project: Project) -> list[str]:
    return [w.code for w in load_parameters(project).warnings]


def _replace(project: Project, position: int, param: str, **cols: Any) -> None:
    sets = ", ".join(f'"{k}" = ?' for k in cols)
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute(
            f'UPDATE "param_values" SET {sets} WHERE object_id = ? AND param = ?',
            (*cols.values(), unit_fid(project, position), param),
        )


def _delete(project: Project, position: int, param: str) -> None:
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute(
            'DELETE FROM "param_values" WHERE object_id = ? AND param = ?',
            (unit_fid(project, position), param),
        )


def test_values_are_converted_to_internal_units(valid_site: Project) -> None:
    params = load_parameters(valid_site)
    assert [u.position for u in params.units] == [1, 2]
    top, aquifer = params.units
    assert top.convertible and not aquifer.convertible
    assert top.kh == pytest.approx(8.64)  # 1e-4 m/s
    assert top.kv == pytest.approx(0.864)  # Kv/Kh = 0.1
    assert top.ss == pytest.approx(1e-4)
    assert top.sy == pytest.approx(0.15)  # 15 %
    assert top.ne is None
    assert (aquifer.kh, aquifer.kv, aquifer.ne) == pytest.approx((50.0, 5.0, 0.2))
    assert aquifer.sy is None
    kh = top.values["kh"]
    assert (kh.original_value, kh.original_unit) == (1e-4, "m/s")
    assert params.warnings == ()


def test_other_units_and_provenance(site: Project, add_param: AddParam) -> None:
    add_param(1, "kh", 1e-2, "cm/s", source="pumping_test", min=1e-3, max=1e-1)
    add_param(1, "kv", 1.0, "m/giorno")
    add_param(1, "ss", 1e-6, "1/cm")
    add_param(1, "sy", 0.1, None)
    for param, value, unit in VALID[2]:
        add_param(2, param, value, unit)
    top = load_parameters(site).by_position(1)
    assert top.kh == pytest.approx(8.64)
    assert top.kv == pytest.approx(1.0)
    assert top.ss == pytest.approx(1e-4)
    assert top.sy == pytest.approx(0.1)
    kh = top.values["kh"]
    assert (kh.source, kh.minimum, kh.maximum) == ("pumping_test", 1e-3, 1e-1)


def test_unit_with_wrong_dimension_points_to_the_field(valid_site: Project) -> None:
    _replace(valid_site, 2, "kh", unit="m")
    with pytest.raises(UnitError) as info:
        load_parameters(valid_site)
    assert info.value.code == "unit.dimension"
    assert info.value.ref is not None and info.value.ref.field == "unit"


@pytest.mark.parametrize("unit", [None, ""])
def test_dimensional_value_needs_a_unit(valid_site: Project, unit: str | None) -> None:
    _replace(valid_site, 2, "ss", unit=unit)
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.unit_missing"
    assert "1/m" in info.value.hint("it")


@pytest.mark.parametrize(
    ("position", "param", "code"),
    [
        (1, "kh", "params.missing"),
        (1, "ss", "params.missing"),
        (1, "sy", "params.missing"),
        (1, "anisotropy", "params.kv_or_anisotropy"),
        (2, "kv", "params.kv_or_anisotropy"),
    ],
)
def test_required_parameters(valid_site: Project, position: int, param: str, code: str) -> None:
    _delete(valid_site, position, param)
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == code


def test_sy_is_not_required_for_confined_units(valid_site: Project) -> None:
    assert load_parameters(valid_site).by_position(2).sy is None


def test_missing_message_names_parameter_and_unit(valid_site: Project) -> None:
    _delete(valid_site, 1, "sy")
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.message("it").endswith("per l'unità 1 (copertura).")
    assert "param = sy" in info.value.hint("it")
    assert info.value.ref is not None and info.value.ref.layer == "hydro_units"


def test_kv_and_anisotropy_together(valid_site: Project, add_param: AddParam) -> None:
    add_param(2, "anisotropy", 0.1, "")
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.kv_and_anisotropy"


@pytest.mark.parametrize(
    ("position", "param", "value", "code"),
    [
        (2, "kh", -1.0, "params.not_positive"),
        (2, "ss", 0.0, "params.not_positive"),
        (1, "sy", 100.0, "params.not_fraction"),  # 100 %
        (2, "ne", 1.5, "params.not_fraction"),
        (2, "ne", 0.0, "params.not_fraction"),
    ],
)
def test_invalid_values(
    valid_site: Project, position: int, param: str, value: float, code: str
) -> None:
    _replace(valid_site, position, param, value=value)
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == code
    assert info.value.ref is not None and info.value.ref.layer == "param_values"


def test_row_without_value(valid_site: Project) -> None:
    _replace(valid_site, 2, "ss", value=None)
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.value_missing"


def test_raster_values_are_not_available_yet(valid_site: Project) -> None:
    _replace(valid_site, 2, "kh", raster_path="rasters/kh.tif")
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.source_not_available"
    assert info.value.ref is not None and info.value.ref.field == "raster_path"


def test_zone_values_are_not_available_yet(valid_site: Project) -> None:
    _replace(valid_site, 2, "kh", object_type="zone")
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.source_not_available"


def test_unknown_unit(valid_site: Project) -> None:
    with gpkg.connect(valid_site.gpkg_path) as conn:
        conn.execute('UPDATE "param_values" SET object_id = 99 WHERE param = ?', ("ne",))
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.unknown_unit"


def test_k_from_tests_is_not_yet_available(valid_site: Project) -> None:
    with gpkg.connect(valid_site.gpkg_path) as conn:
        conn.execute('UPDATE "hydro_units" SET k_from_tests = 1 WHERE position = 2')
    with pytest.raises(ParameterError) as info:
        load_parameters(valid_site)
    assert info.value.code == "params.mode_not_available"
    assert info.value.ref is not None and info.value.ref.field == "k_from_tests"


def test_implausible_value_is_a_warning(valid_site: Project) -> None:
    _replace(valid_site, 2, "kh", value=50.0, unit="m/s")  # 4.3e6 m/d
    assert _codes(valid_site) == ["params.implausible"]


def test_kv_above_kh_is_a_warning(valid_site: Project) -> None:
    _replace(valid_site, 2, "kv", value=80.0)
    assert _codes(valid_site) == ["params.kv_above_kh"]


def test_anisotropy_above_one_is_a_warning(valid_site: Project) -> None:
    _replace(valid_site, 1, "anisotropy", value=2.0)
    assert _codes(valid_site) == ["params.kv_above_kh"]


def test_outside_declared_range_is_a_warning(valid_site: Project) -> None:
    # min and max are in the unit of the row (m/d here)
    _replace(valid_site, 2, "kh", min=60.0, max=None)
    warnings = load_parameters(valid_site).warnings
    assert [w.code for w in warnings] == ["params.outside_declared_range"]
    assert "+∞" in warnings[0].message.it
    _replace(valid_site, 2, "kh", min=10.0, max=40.0)
    assert _codes(valid_site) == ["params.outside_declared_range"]
    _replace(valid_site, 2, "kh", min=10.0, max=60.0)
    assert _codes(valid_site) == []


def test_empty_object_type_means_unit(valid_site: Project) -> None:
    with gpkg.connect(valid_site.gpkg_path) as conn:
        conn.execute('UPDATE "param_values" SET object_type = NULL')
    assert len(load_parameters(valid_site).units) == 2
