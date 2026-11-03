"""Example command: example."""

from __future__ import annotations

import argparse
from pathlib import Path

from phrear.commands.base import CommandSpec, Context
from phrear.examples.alluvial import create_example


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, help="new or empty folder for the example project")


def _example(args: argparse.Namespace, ctx: Context) -> int:
    project = create_example(args.path)
    root = str(project.root)
    data = {"path": root, "name": project.config.name}
    if ctx.lang == "it":
        text = (
            f"Progetto di esempio «{project.config.name}» creato in {root}\n"
            f"Passi successivi:\n"
            f'  phrear check "{root}"\n'
            f'  phrear run "{root}"\n'
            f"Poi apri model.gpkg e runs/<run_id>/heads.nc in QGIS."
        )
    else:
        text = (
            f"Example project '{project.config.name}' created in {root}\n"
            f"Next steps:\n"
            f'  phrear check "{root}"\n'
            f'  phrear run "{root}"\n'
            f"Then open model.gpkg and runs/<run_id>/heads.nc in QGIS."
        )
    ctx.result("example", data, text)
    return 0


COMMANDS = [CommandSpec("example", "create the example project", _configure, _example)]
