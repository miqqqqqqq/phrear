"""Stress periods and time steps from dates (docs/SPEC.md, section 13).

A new stress period starts only at a regime change: the model start, a date in
``model.period_breaks`` or the first date of a series in use (activation of the
object that uses it). Values that vary inside a period enter MODFLOW 6 through
time series files, which MF6 averages over each time step.

The optional initial steady-state period comes first and lasts
:data:`STEADY_LENGTH_D`; simulation time 0 is therefore one day before the model
start when the steady period is present. :meth:`Calendar.sim_time` converts dates
to simulation time and must be used for every time handed to MF6.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal

from phrear.errors import TimeError
from phrear.events import Problem
from phrear.project.config import ModelTime, TimeStepping
from phrear.timeline.series import days_between

STEADY_LENGTH_D: Final = 1.0
MAX_STEPS_PER_PERIOD: Final = 100_000

Reason = str
"""Why a period starts: ``model_start``, ``period_break``, ``series:<id>``, ``steady``."""


@dataclass(frozen=True)
class Period:
    index: int
    """1-based, as in MF6."""
    kind: Literal["steady", "transient"]
    start: datetime
    end: datetime
    perlen_d: float
    nstp: int
    tsmult: float
    reasons: tuple[Reason, ...]

    @property
    def dt_first_d(self) -> float:
        return first_step(self.perlen_d, self.nstp, self.tsmult)

    @property
    def dt_last_d(self) -> float:
        return self.dt_first_d * self.tsmult ** (self.nstp - 1)


@dataclass(frozen=True)
class Calendar:
    start: datetime
    end: datetime
    steady_initial: bool
    periods: tuple[Period, ...]
    activations: dict[str, datetime]
    """Effective activation date of each series in use (after any merge)."""
    warnings: tuple[Problem, ...] = field(default_factory=tuple)

    @property
    def offset_d(self) -> float:
        return STEADY_LENGTH_D if self.steady_initial else 0.0

    def sim_time(self, moment: datetime) -> float:
        """Simulation time (days) of a date inside the model period."""
        if not self.start <= moment <= self.end:
            raise ValueError(f"{moment.isoformat()} is outside the model period")
        return self.offset_d + days_between(self.start, moment)

    @property
    def transient_periods(self) -> tuple[Period, ...]:
        return tuple(p for p in self.periods if p.kind == "transient")

    def period_starting_at(self, moment: datetime) -> Period:
        for period in self.transient_periods:
            if period.start == moment:
                return period
        raise KeyError(moment)


# --- time steps -------------------------------------------------------------------


def first_step(length_d: float, nstp: int, tsmult: float) -> float:
    """Length of the first step of an MF6 period with ``nstp`` steps and ``tsmult``."""
    if nstp == 1 or tsmult == 1.0:
        return length_d / nstp
    return length_d * (tsmult - 1.0) / (tsmult**nstp - 1.0)


def _last_step(length_d: float, nstp: int, tsmult: float) -> float:
    return first_step(length_d, nstp, tsmult) * tsmult ** (nstp - 1)


def time_steps(length_d: float, stepping: TimeStepping) -> tuple[int, float]:
    """Fewest steps (nstp, tsmult) with first step ≤ dt_initial, last ≤ dt_max.

    The multiplier is the largest value not above ``stepping.tsmult`` that keeps
    the last step within ``dt_max_d``.
    """
    dt0, dtmax, mult = stepping.dt_initial_d, stepping.dt_max_d, stepping.tsmult
    tolerance = 1e-9
    for nstp in range(1, MAX_STEPS_PER_PERIOD + 1):
        if length_d / nstp > dtmax * (1 + tolerance):
            continue
        if nstp == 1:
            if length_d <= dt0 * (1 + tolerance):
                return 1, 1.0
            continue
        if _last_step(length_d, nstp, mult) <= dtmax * (1 + tolerance):
            m = mult
        else:  # bisection: _last_step grows with the multiplier
            lo, hi = 1.0, mult
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                if _last_step(length_d, nstp, mid) <= dtmax:
                    lo = mid
                else:
                    hi = mid
            m = lo
        if first_step(length_d, nstp, m) <= dt0 * (1 + tolerance):
            return nstp, m
    raise TimeError("time.too_many_steps", length_d=f"{length_d:g}", limit=MAX_STEPS_PER_PERIOD)


# --- stress periods -----------------------------------------------------------------


def _fmt(moment: datetime) -> str:
    return moment.isoformat(sep=" ", timespec="minutes").removesuffix(" 00:00")


def build_calendar(
    model: ModelTime, stepping: TimeStepping, series_starts: dict[str, datetime]
) -> Calendar:
    """Stress periods and time steps for the model period and the series in use."""
    breaks: dict[datetime, list[Reason]] = {model.start_date: ["model_start"]}
    for moment in model.period_breaks:
        breaks.setdefault(moment, []).append("period_break")
    activations: dict[str, datetime] = {}
    warnings: list[Problem] = []
    for series_id, first in sorted(series_starts.items()):
        if first <= model.start_date:
            activations[series_id] = model.start_date
        elif first < model.end_date:
            breaks.setdefault(first, []).append(f"series:{series_id}")
            activations[series_id] = first
        else:
            warnings.append(
                Problem.from_code(
                    "series.after_end", {"series_id": series_id, "start": _fmt(first)}
                )
            )

    times = sorted(breaks)
    reasons = [breaks[t] for t in times]
    i = 0
    while len(times) > 1 and i < len(times):
        end = times[i + 1] if i + 1 < len(times) else model.end_date
        duration = days_between(times[i], end)
        if duration >= stepping.min_period_d:
            i += 1
            continue
        if i + 1 < len(times):  # merge with the next period: its start moves back
            moved_from, moved_to, drop, keep = times[i + 1], times[i], i + 1, i
        else:  # last period too short: merge with the previous one
            moved_from, moved_to, drop, keep = times[i], times[i - 1], i, i - 1
        warnings.append(
            Problem.from_code(
                "time.period_merged",
                {
                    "start": _fmt(times[i]),
                    "end": _fmt(end),
                    "duration_d": f"{duration:g}",
                    "min_d": f"{stepping.min_period_d:g}",
                    "moved_from": _fmt(moved_from),
                    "moved_to": _fmt(moved_to),
                },
            )
        )
        reasons[keep] = reasons[keep] + reasons[drop]
        for series_id, moment in activations.items():
            if moment == moved_from:
                activations[series_id] = moved_to
        del times[drop]
        del reasons[drop]
        i = keep

    periods: list[Period] = []
    if model.steady_initial:
        periods.append(
            Period(
                1,
                "steady",
                model.start_date,
                model.start_date,
                STEADY_LENGTH_D,
                1,
                1.0,
                ("steady",),
            )
        )
    bounds = [*times, model.end_date]
    for k, (a, b) in enumerate(itertools.pairwise(bounds)):
        length = days_between(a, b)
        nstp, mult = time_steps(length, stepping)
        periods.append(
            Period(len(periods) + 1, "transient", a, b, length, nstp, mult, tuple(reasons[k]))
        )
    return Calendar(
        start=model.start_date,
        end=model.end_date,
        steady_initial=model.steady_initial,
        periods=tuple(periods),
        activations=activations,
        warnings=tuple(warnings),
    )


__all__ = [
    "MAX_STEPS_PER_PERIOD",
    "STEADY_LENGTH_D",
    "Calendar",
    "Period",
    "build_calendar",
    "first_step",
    "time_steps",
]
