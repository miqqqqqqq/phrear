"""Model checks that look across stages (docs/SPEC.md, section 15).

The plausibility limits on rates catch values entered in the wrong unit, which
shift by large factors (86.4 between l/s and m³/d, 365.25 between mm/d and
mm/year); they are not physical limits.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from phrear.boundaries.base import Assignment, Forcing
from phrear.checks.base import Check, Inspection
from phrear.errors import FieldValue, Localized
from phrear.events import Problem
from phrear.project.features import fmt

WELL_RATE_MAX_LS: Final = 200.0
"""Highest plausible rate of one well, l/s."""
RECHARGE_MAX_MM_Y: Final = 3000.0
"""Highest plausible recharge, mm/year."""
RECHARGE_MIN_MM_Y: Final = 1.0
"""Lowest plausible non-zero recharge, mm/year."""
_M3D_PER_LS: Final = 86.4
_MMY_PER_MD: Final = 1000.0 * 365.25


def _values(forcing: Forcing) -> np.ndarray:
    if forcing.series is not None:
        return np.abs(forcing.series.values)
    assert forcing.constant is not None
    return np.abs(np.array([forcing.constant]))


def _by_feature(assignments: tuple[Assignment, ...]) -> dict[str, list[Assignment]]:
    groups: dict[str, list[Assignment]] = {}
    for a in assignments:
        groups.setdefault(a.boundname, []).append(a)
    return groups


def no_fixed_head(ins: Inspection) -> list[Problem]:
    assert ins.timeline is not None
    if not ins.timeline.calendar.steady_initial:
        return []
    if any(a.forcing.steady is not None for a in ins.package("chd").assignments):
        return []
    return [Problem.from_code("check.no_fixed_head")]


def well_in_fixed_head(ins: Inspection) -> list[Problem]:
    fixed = {a.cell for a in ins.package("chd").assignments}
    problems: list[Problem] = []
    for entries in _by_feature(ins.package("wel").assignments).values():
        inside = [a for a in entries if a.cell in fixed]
        if inside:
            k, r, c = inside[0].cell
            problems.append(
                Problem.from_code(
                    "check.well_in_fixed_head",
                    {
                        "feature": inside[0].label,
                        "n_cells": len(inside),
                        "layer": k + 1,
                        "row": r + 1,
                        "col": c + 1,
                    },
                    ref=inside[0].ref,
                )
            )
    return problems


def rates(ins: Inspection) -> list[Problem]:
    problems: list[Problem] = []
    for entries in _by_feature(ins.package("wel").assignments).values():
        top = float(_values(entries[0].forcing).max()) / _M3D_PER_LS
        if top > WELL_RATE_MAX_LS:
            problems.append(
                Problem.from_code(
                    "check.well_rate_high",
                    {
                        "feature": entries[0].label,
                        "value": fmt(top),
                        "limit": fmt(WELL_RATE_MAX_LS),
                    },
                    ref=entries[0].ref,
                )
            )
    for entries in _by_feature(ins.package("rch").assignments).values():
        values = _values(entries[0].forcing) * _MMY_PER_MD
        nonzero = values[values > 0.0]
        label, ref = entries[0].label, entries[0].ref
        if values.max() > RECHARGE_MAX_MM_Y:
            high: dict[str, FieldValue] = {
                "feature": label,
                "value": fmt(float(values.max())),
                "limit": fmt(RECHARGE_MAX_MM_Y),
            }
            problems.append(Problem.from_code("check.recharge_high", high, ref=ref))
        if nonzero.size and nonzero.min() < RECHARGE_MIN_MM_Y:
            low: dict[str, FieldValue] = {
                "feature": label,
                "value": fmt(float(nonzero.min())),
                "limit": fmt(RECHARGE_MIN_MM_Y),
            }
            problems.append(Problem.from_code("check.recharge_low", low, ref=ref))
    return problems


def newton_off(ins: Inspection) -> list[Problem]:
    assert ins.grid is not None
    if ins.project.config.options.newton:
        return []
    convertible = [f"{u.position} ({u.name})" for u in ins.grid.units if u.convertible]
    if not convertible:
        return []
    return [Problem.from_code("check.newton_off", {"units": ", ".join(convertible)})]


CHECKS: tuple[Check, ...] = (
    Check(
        "no_fixed_head",
        Localized(
            "Carico di riferimento nel periodo stazionario", "Reference head in steady state"
        ),
        "error",
        ("time", "boundaries"),
        no_fixed_head,
    ),
    Check(
        "well_in_fixed_head",
        Localized("Pozzi in celle a carico imposto", "Wells in fixed head cells"),
        "warning",
        ("boundaries",),
        well_in_fixed_head,
    ),
    Check(
        "rates",
        Localized("Ordine di grandezza di portate e ricarica", "Magnitude of rates and recharge"),
        "warning",
        ("boundaries",),
        rates,
    ),
    Check(
        "newton_off",
        Localized("Newton e unità convertibili", "Newton and convertible units"),
        "warning",
        ("grid",),
        newton_off,
    ),
)
