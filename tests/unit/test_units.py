"""Conversion of user units to internal units (metres, days)."""

from __future__ import annotations

import numpy as np
import pytest

from phrear.errors import UnitError
from phrear.units import (
    INTERNAL_UNITS,
    INTERNAL_UNITS_DISPLAY,
    QUANTITY_LABELS,
    PhysicalQuantity,
    conversion_factor,
    normalise,
    to_internal,
)

Q = PhysicalQuantity
JULIAN_YEAR_D = 365.25


@pytest.mark.parametrize(
    ("value", "unit", "quantity", "expected"),
    [
        # discharge: 1 l/s = 1e-3 m³/s · 86400 s/d = 86.4 m³/d
        (1.0, "l/s", Q.DISCHARGE, 86.4),
        (1.0, "m3/s", Q.DISCHARGE, 86_400.0),
        (1.0, "m³/h", Q.DISCHARGE, 24.0),
        (JULIAN_YEAR_D, "m³/anno", Q.DISCHARGE, 1.0),
        (JULIAN_YEAR_D, "m**3/year", Q.DISCHARGE, 1.0),
        # hydraulic conductivity: 1e-4 m/s · 86400 s/d = 8.64 m/d
        (1e-4, "m/s", Q.VELOCITY, 8.64),
        (1.0, "cm/s", Q.VELOCITY, 864.0),
        # recharge: 365.25 mm/anno = 1 mm/d = 1e-3 m/d
        (JULIAN_YEAR_D, "mm/anno", Q.VELOCITY, 1e-3),
        (1.0, "mm/giorno", Q.VELOCITY, 1e-3),
        # transmissivity: 1e-3 m²/s = 86.4 m²/d
        (1e-3, "m2/s", Q.TRANSMISSIVITY, 86.4),
        (1e-3, "m²/s", Q.TRANSMISSIVITY, 86.4),
        (1e-5, "1/m", Q.SPECIFIC_STORAGE, 1e-5),
        (1e-6, "1/cm", Q.SPECIFIC_STORAGE, 1e-4),
        (1e-6, "1/s", Q.HYDRAULIC_CHARACTERISTIC, 0.0864),
        (25.0, "%", Q.DIMENSIONLESS, 0.25),
        (0.2, "", Q.DIMENSIONLESS, 0.2),
        (0.2, "-", Q.DIMENSIONLESS, 0.2),
        (1.0, "km", Q.LENGTH, 1000.0),
        (1.0, "km2", Q.AREA, 1e6),
        (1.0, "ore", Q.TIME, 1.0 / 24.0),
        (1.0, "anni", Q.TIME, JULIAN_YEAR_D),
    ],
)
def test_to_internal_scalar(value: float, unit: str, quantity: Q, expected: float) -> None:
    assert to_internal(value, unit, quantity) == pytest.approx(expected, rel=1e-12)


def test_to_internal_array_keeps_shape() -> None:
    values = np.array([[1.0, 2.0], [3.0, 4.0]])
    out = to_internal(values, "l/s", Q.DISCHARGE)
    assert out.shape == (2, 2)
    np.testing.assert_allclose(out, values * 86.4, rtol=1e-12)


def test_internal_unit_has_factor_one() -> None:
    for quantity, unit in INTERNAL_UNITS.items():
        assert conversion_factor(unit, quantity) == pytest.approx(1.0, rel=1e-15)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("m3/d", "m**3/d"),
        ("m³/anno", "m**3/year"),
        ("km2", "km**2"),
        ("mm/giorno", "mm/day"),
        ("l/s", "l/s"),
        ("%", "percent"),
    ],
)
def test_normalise(text: str, expected: str) -> None:
    assert normalise(text) == expected


def test_unknown_unit_raises_with_code() -> None:
    with pytest.raises(UnitError) as exc:
        to_internal(1.0, "furlong per fortnight foo", Q.VELOCITY)
    assert exc.value.code == "unit.unknown"
    assert "furlong" in exc.value.message("it")


def test_wrong_dimension_raises_with_localised_quantity() -> None:
    # a discharge typed as a velocity
    with pytest.raises(UnitError) as exc:
        to_internal(10.0, "l/s", Q.VELOCITY)
    error = exc.value
    assert error.code == "unit.dimension"
    assert "velocità" in error.message("it")
    assert "velocity" in error.message("en")
    assert "m/d" in error.message("it")


def test_every_quantity_has_labels_and_display_unit() -> None:
    for quantity in Q:
        assert quantity in INTERNAL_UNITS
        assert quantity in INTERNAL_UNITS_DISPLAY
        assert quantity in QUANTITY_LABELS
