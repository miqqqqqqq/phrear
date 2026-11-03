"""Time commands: calendar."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from phrear.commands.base import CommandSpec, Context
from phrear.project import Project
from phrear.timeline import Period, project_timeline

_HEADERS = {
    "it": ("Periodo", "Tipo", "Inizio", "Fine", "Durata [d]", "Passi", "Molt.",
           "Δt1 [d]", "Δtn [d]", "Motivo"),
    "en": ("Period", "Kind", "Start", "End", "Length [d]", "Steps", "Mult.",
           "Δt1 [d]", "Δtn [d]", "Reason"),
}  # fmt: skip
_KINDS = {
    "it": {"steady": "staz.", "transient": "trans."},
    "en": {"steady": "steady", "transient": "trans."},
}


def _date(period: Period, which: str) -> str:
    moment = period.start if which == "start" else period.end
    return moment.isoformat(sep=" ", timespec="minutes").removesuffix(" 00:00")


def _row(period: Period, lang: str) -> tuple[str, ...]:
    end = "—" if period.kind == "steady" else _date(period, "end")
    return (
        str(period.index),
        _KINDS[lang][period.kind],
        _date(period, "start"),
        end,
        f"{period.perlen_d:g}",
        str(period.nstp),
        f"{period.tsmult:.4g}",
        f"{period.dt_first_d:.4g}",
        f"{period.dt_last_d:.4g}",
        ", ".join(period.reasons),
    )


def _table(periods: tuple[Period, ...], lang: str) -> str:
    rows = [_HEADERS[lang], *(_row(p, lang) for p in periods)]
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows
    )


def _period_data(period: Period) -> dict[str, Any]:
    return {
        "index": period.index,
        "kind": period.kind,
        "start": period.start.isoformat(),
        "end": period.end.isoformat(),
        "perlen_d": period.perlen_d,
        "nstp": period.nstp,
        "tsmult": period.tsmult,
        "dt_first_d": period.dt_first_d,
        "dt_last_d": period.dt_last_d,
        "reasons": list(period.reasons),
    }


def _configure_calendar(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")


def _calendar(args: argparse.Namespace, ctx: Context) -> int:
    timeline = project_timeline(Project.open(args.path))
    calendar = timeline.calendar
    for problem in calendar.warnings:
        ctx.warn(problem)
    data = {
        "start": calendar.start.isoformat(),
        "end": calendar.end.isoformat(),
        "steady_initial": calendar.steady_initial,
        "periods": [_period_data(p) for p in calendar.periods],
        "series": {
            series_id: {
                "activation": calendar.activations[series_id].isoformat()
                if series_id in calendar.activations
                else None,
                "steady_value": timeline.steady_values.get(series_id),
            }
            for series_id in sorted(timeline.series)
        },
    }
    ctx.result("calendar", data, _table(calendar.periods, ctx.lang))
    return 0


COMMANDS = [
    CommandSpec("calendar", "stress periods and time steps", _configure_calendar, _calendar),
]
