"""Units of measure: parsing, validation and conversion to internal units.

The internal units of the model are metres and days (docs/SPEC.md, section 3.2).
Every physical input passes through this module before it reaches ``build``;
values keep their original unit in the project and are converted only here.

Conventions (docs/adr/0005):

- ``anno`` / ``year`` is the Julian year, 365.25 d.
- Accepted notations include ``m3/d``, ``m³/d``, ``m**3/d``, ``l/s``, ``mm/anno``,
  ``m/s``, ``1/m``, ``%``; Italian time words (anno, giorno, ora, minuto, secondo)
  are translated before parsing.
- An empty string, ``-`` or ``1`` means dimensionless.
"""

from __future__ import annotations

import re
from enum import StrEnum
from functools import cache
from typing import overload

import numpy as np
import numpy.typing as npt
import pint

from phrear.errors import Localized, UnitError

UREG = pint.UnitRegistry(cache_folder=None)


class PhysicalQuantity(StrEnum):
    """Physical quantities handled by the model, each with one internal unit."""

    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    TIME = "time"
    DISCHARGE = "discharge"
    VELOCITY = "velocity"
    TRANSMISSIVITY = "transmissivity"
    SPECIFIC_STORAGE = "specific_storage"
    HYDRAULIC_CHARACTERISTIC = "hydraulic_characteristic"
    CONDUCTANCE = "conductance"
    DIMENSIONLESS = "dimensionless"


#: Internal unit of each quantity. VELOCITY covers hydraulic conductivity,
#: recharge rate and specific discharge; HYDRAULIC_CHARACTERISTIC is K/thickness
#: of a barrier (MF6 HFB).
INTERNAL_UNITS: dict[PhysicalQuantity, str] = {
    PhysicalQuantity.LENGTH: "m",
    PhysicalQuantity.AREA: "m**2",
    PhysicalQuantity.VOLUME: "m**3",
    PhysicalQuantity.TIME: "d",
    PhysicalQuantity.DISCHARGE: "m**3/d",
    PhysicalQuantity.VELOCITY: "m/d",
    PhysicalQuantity.TRANSMISSIVITY: "m**2/d",
    PhysicalQuantity.SPECIFIC_STORAGE: "1/m",
    PhysicalQuantity.HYDRAULIC_CHARACTERISTIC: "1/d",
    PhysicalQuantity.CONDUCTANCE: "m**2/d",
    PhysicalQuantity.DIMENSIONLESS: "",
}

#: Display form of the internal units, used in messages.
INTERNAL_UNITS_DISPLAY: dict[PhysicalQuantity, str] = {
    PhysicalQuantity.LENGTH: "m",
    PhysicalQuantity.AREA: "m²",
    PhysicalQuantity.VOLUME: "m³",
    PhysicalQuantity.TIME: "d",
    PhysicalQuantity.DISCHARGE: "m³/d",
    PhysicalQuantity.VELOCITY: "m/d",
    PhysicalQuantity.TRANSMISSIVITY: "m²/d",
    PhysicalQuantity.SPECIFIC_STORAGE: "1/m",
    PhysicalQuantity.HYDRAULIC_CHARACTERISTIC: "1/d",
    PhysicalQuantity.CONDUCTANCE: "m²/d",
    PhysicalQuantity.DIMENSIONLESS: "-",
}

QUANTITY_LABELS: dict[PhysicalQuantity, Localized] = {
    PhysicalQuantity.LENGTH: Localized("lunghezza", "length"),
    PhysicalQuantity.AREA: Localized("area", "area"),
    PhysicalQuantity.VOLUME: Localized("volume", "volume"),
    PhysicalQuantity.TIME: Localized("tempo", "time"),
    PhysicalQuantity.DISCHARGE: Localized("portata", "discharge"),
    PhysicalQuantity.VELOCITY: Localized(
        "velocità (conducibilità, ricarica, flusso specifico)",
        "velocity (conductivity, recharge, specific discharge)",
    ),
    PhysicalQuantity.TRANSMISSIVITY: Localized("trasmissività", "transmissivity"),
    PhysicalQuantity.SPECIFIC_STORAGE: Localized("immagazzinamento specifico", "specific storage"),
    PhysicalQuantity.HYDRAULIC_CHARACTERISTIC: Localized(
        "caratteristica idraulica", "hydraulic characteristic"
    ),
    PhysicalQuantity.CONDUCTANCE: Localized("conduttanza", "conductance"),
    PhysicalQuantity.DIMENSIONLESS: Localized("adimensionale", "dimensionless"),
}

_ITALIAN_WORDS = {
    "anno": "year",
    "anni": "year",
    "giorno": "day",
    "giorni": "day",
    "ora": "hour",
    "ore": "hour",
    "minuto": "minute",
    "minuti": "minute",
    "secondo": "second",
    "secondi": "second",
    "litro": "liter",
    "litri": "liter",
}
_WORD_RE = re.compile(r"\b(" + "|".join(_ITALIAN_WORDS) + r")\b")
# "m3" -> "m**3", "km2" -> "km**2"; a digit right after a letter is a power.
_POWER_RE = re.compile(r"(?<=[A-Za-z])([23])(?![\d.])")
_DIMENSIONLESS_SPELLINGS = {"", "-", "1"}


def normalise(text: str) -> str:
    """Rewrite a user unit string into a form pint can parse."""
    out = text.strip().replace("³", "**3").replace("²", "**2").replace("%", "percent")
    out = _WORD_RE.sub(lambda m: _ITALIAN_WORDS[m.group(1)], out)
    return _POWER_RE.sub(r"**\1", out)


@cache
def parse_unit(text: str) -> pint.Unit:
    """Parse a unit string; raise :class:`UnitError` if it is not recognised."""
    norm = normalise(text)
    if norm in _DIMENSIONLESS_SPELLINGS:
        return UREG.dimensionless
    try:
        unit = UREG.parse_units(norm)
    except Exception as exc:  # pint raises several unrelated exception types
        raise UnitError("unit.unknown", unit=text, detail=f"{type(exc).__name__}: {exc}") from exc
    return unit


@cache
def conversion_factor(unit: str, quantity: PhysicalQuantity) -> float:
    """Factor f such that value_internal = f · value_in_unit.

    Raises :class:`UnitError` if ``unit`` is unknown or has the wrong dimensions.
    """
    source = parse_unit(unit)
    target = parse_unit(INTERNAL_UNITS[quantity])
    if source.dimensionality != target.dimensionality:
        raise UnitError(
            "unit.dimension",
            unit=unit,
            quantity=QUANTITY_LABELS[quantity],
            expected=INTERNAL_UNITS_DISPLAY[quantity],
            detail=f"{source.dimensionality} != {target.dimensionality}",
        )
    return float(UREG.Quantity(1.0, source).to(target).magnitude)


@overload
def to_internal(value: float, unit: str, quantity: PhysicalQuantity) -> float: ...


@overload
def to_internal(
    value: npt.NDArray[np.float64], unit: str, quantity: PhysicalQuantity
) -> npt.NDArray[np.float64]: ...


def to_internal(
    value: float | npt.NDArray[np.float64], unit: str, quantity: PhysicalQuantity
) -> float | npt.NDArray[np.float64]:
    """Convert ``value`` expressed in ``unit`` to the internal unit of ``quantity``."""
    return value * conversion_factor(unit, quantity)
