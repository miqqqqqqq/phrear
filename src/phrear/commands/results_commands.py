"""Results commands: export."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from phrear.commands.base import CommandSpec, Context
from phrear.project import Project
from phrear.results.netcdf import write_heads
from phrear.results.runs import completed_run


def _configure_export(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")
    parser.add_argument("--run", default=None, help="run to export (default: latest completed)")


def _export(args: argparse.Namespace, ctx: Context) -> int:
    run_id, folder, manifest = completed_run(Project.open(args.path), args.run)
    target = write_heads(folder, manifest, datetime.now().astimezone())
    data = {"run_id": run_id, "heads": str(target)}
    text = (
        f"Carichi del run {run_id} esportati in {target}"
        if ctx.lang == "it"
        else f"Heads of run {run_id} exported to {target}"
    )
    ctx.result("export", data, text)
    return 0


COMMANDS = [
    CommandSpec("export", "export the heads of a run as NetCDF UGRID", _configure_export, _export)
]
