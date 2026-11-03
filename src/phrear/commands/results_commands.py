"""Results commands: export."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from phrear.commands.base import CommandSpec, Context
from phrear.project import Project
from phrear.results.exporters import EXPORTERS
from phrear.results.runs import completed_run


def _configure_export(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")
    parser.add_argument("--run", default=None, help="run to export (default: latest completed)")
    parser.add_argument(
        "--format",
        default="heads",
        choices=sorted(EXPORTERS),
        help="product to export (default: heads, NetCDF UGRID)",
    )


def _export(args: argparse.Namespace, ctx: Context) -> int:
    run_id, folder, manifest = completed_run(Project.open(args.path), args.run)
    exporter = EXPORTERS[args.format]
    target = exporter.write(folder, manifest, datetime.now().astimezone())
    data = {"run_id": run_id, "format": exporter.name, args.format: str(target)}
    label = exporter.label.get(ctx.lang)
    text = (
        f"{label} del run {run_id} esportati in {target}"
        if ctx.lang == "it"
        else f"{label} of run {run_id} exported to {target}"
    )
    ctx.result("export", data, text)
    return 0


COMMANDS = [
    CommandSpec("export", "export a product of a run (default: heads)", _configure_export, _export)
]
