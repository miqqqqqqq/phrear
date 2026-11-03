"""Grid commands: grid."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from phrear.commands.base import CommandSpec, Context
from phrear.grid.export import export_grid
from phrear.grid.model_grid import build_model_grid
from phrear.project import Project
from phrear.project.project import EXPORTS_DIR

GRID_EXPORT = "grid.gpkg"


def _configure_grid(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")
    parser.add_argument(
        "--export", action="store_true", help=f"write the cells to {EXPORTS_DIR}/{GRID_EXPORT}"
    )


def _text(data: dict[str, Any], lang: str) -> str:
    it = lang == "it"
    lines = [
        (
            f"Griglia DIS: {data['nlay']} layer × {data['nrow']} righe × {data['ncol']} colonne"
            if it
            else f"DIS grid: {data['nlay']} layers × {data['nrow']} rows × {data['ncol']} columns"
        ),
        (
            f"Cella {data['cell_size_m']:g} m, rotazione {data['angrot_deg']:g}°, origine "
            f"({data['xorigin']:.2f}, {data['yorigin']:.2f})"
            if it
            else f"Cell {data['cell_size_m']:g} m, rotation {data['angrot_deg']:g}°, origin "
            f"({data['xorigin']:.2f}, {data['yorigin']:.2f})"
        ),
        (
            f"Celle attive {data['active_cells']} su {data['cells']}; memoria stimata "
            f"~{data['memory_estimate_mb']:g} MB"
            if it
            else f"Active cells {data['active_cells']} of {data['cells']}; estimated memory "
            f"~{data['memory_estimate_mb']:g} MB"
        ),
    ]
    for layer in data["layers"]:
        lines.append(
            f"  layer {layer['layer']} (unità {layer['unit']}): {layer['active']} attive, "
            f"{layer['pass_through']} a passaggio verticale"
            if it
            else f"  layer {layer['layer']} (unit {layer['unit']}): {layer['active']} active, "
            f"{layer['pass_through']} pass-through"
        )
    if "export" in data:
        lines.append(f"Export: {data['export']}")
    return "\n".join(lines)


def _grid(args: argparse.Namespace, ctx: Context) -> int:
    project = Project.open(args.path)
    model_grid = build_model_grid(project)
    for problem in model_grid.warnings:
        ctx.warn(problem)
    data = model_grid.summary()
    if args.export:
        target = project.root / EXPORTS_DIR / GRID_EXPORT
        export_grid(model_grid, target, project.config.crs)
        data["export"] = str(target)
    ctx.result("grid", data, _text(data, ctx.lang))
    return 0


COMMANDS = [
    CommandSpec("grid", "build the model grid and check the geometry", _configure_grid, _grid)
]
