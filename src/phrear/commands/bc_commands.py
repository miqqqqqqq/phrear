"""Boundary condition commands: bc."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from phrear.boundaries.export import export_boundaries
from phrear.boundaries.registry import BOUNDARY_TYPES, Boundaries, build_boundaries
from phrear.commands.base import CommandSpec, Context
from phrear.errors import Lang
from phrear.grid.model_grid import build_model_grid
from phrear.params.layers import layer_parameters
from phrear.params.values import load_parameters
from phrear.project import Project
from phrear.project.project import EXPORTS_DIR
from phrear.timeline import Timeline, project_timeline

BC_EXPORT = "bc.gpkg"
_HEADERS = {
    "it": ("Pacchetto", "Tipo", "Feature", "Celle", "Righe", "Serie", "Righe per periodo"),
    "en": ("Package", "Type", "Features", "Cells", "Entries", "Series", "Entries per period"),
}


def _data(boundaries: Boundaries, timeline: Timeline) -> dict[str, Any]:
    names = boundaries.ts_names()
    calendar = timeline.calendar
    packages = []
    for p in boundaries.packages:
        label = BOUNDARY_TYPES[p.bc_type].label
        packages.append(
            {
                "type": p.bc_type,
                "package": p.package,
                "label": {"it": label.it, "en": label.en},
                "features": p.n_features,
                "cells": len({a.cell for a in p.assignments}),
                "entries": len(p.assignments),
                "series": len(p.ts_records(calendar, names)),
                "entries_per_period": [len(r) for r in p.period_records(calendar, names)],
            }
        )
    return {"periods": len(calendar.periods), "packages": packages}


def _per_period(counts: list[int]) -> str:
    if not counts:
        return "-"
    if len(set(counts)) == 1:
        return f"{counts[0]} × {len(counts)}"
    return (
        ", ".join(str(c) for c in counts) if len(counts) <= 6 else (f"{counts[0]} … {counts[-1]}")
    )


def _text(data: dict[str, Any], lang: Lang) -> str:
    rows: list[tuple[str, ...]] = [_HEADERS[lang]]
    for p in data["packages"]:
        rows.append(
            (
                p["package"].upper(),
                p["label"][lang],
                str(p["features"]),
                str(p["cells"]),
                str(p["entries"]),
                str(p["series"]),
                _per_period(p["entries_per_period"]),
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows]
    if "export" in data:
        lines.append(f"Export: {data['export']}")
    return "\n".join(lines)


def _configure_bc(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")
    parser.add_argument(
        "--export", action="store_true", help=f"write the cells to {EXPORTS_DIR}/{BC_EXPORT}"
    )


def _bc(args: argparse.Namespace, ctx: Context) -> int:
    project = Project.open(args.path)
    grid = build_model_grid(project)
    layers = layer_parameters(grid, load_parameters(project))
    timeline = project_timeline(project)
    boundaries = build_boundaries(project, grid, layers, timeline)
    for problem in boundaries.warnings:
        ctx.warn(problem)
    data = _data(boundaries, timeline)
    if args.export:
        target = project.root / EXPORTS_DIR / BC_EXPORT
        export_boundaries(boundaries, grid, target, project.config.crs)
        data["export"] = str(target)
    ctx.result("bc", data, _text(data, ctx.lang))
    return 0


COMMANDS = [
    CommandSpec("bc", "boundary conditions on the grid, per package and period", _configure_bc, _bc)
]
