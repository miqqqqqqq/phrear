"""Results commands: runs, export."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from phrear.commands.base import CommandSpec, Context
from phrear.errors import Lang
from phrear.project import Project
from phrear.results.exporters import EXPORTERS
from phrear.results.runs import completed_run, list_runs


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


def _configure_runs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")


def _runs_text(data: dict[str, Any], lang: Lang) -> str:
    if not data["runs"]:
        return "Nessun run." if lang == "it" else "No runs."
    changed = "progetto modificato dopo il run" if lang == "it" else "project changed since the run"
    lines = []
    for run in data["runs"]:
        parts = [run["run_id"], str(run.get("created") or "")[:16].replace("T", " ")]
        parts.append(run["status_label"][lang])
        if run.get("duration_s") is not None and run["status"] == "completed":
            parts.append(f"{run['duration_s']:.1f} s")
        if run.get("same_project") is False:
            parts.append(changed)
        lines.append("  ".join(parts))
    return "\n".join(lines)


def _runs(args: argparse.Namespace, ctx: Context) -> int:
    data = list_runs(Project.open(args.path))
    ctx.result("runs", data, _runs_text(data, ctx.lang))
    return 0


COMMANDS = [
    CommandSpec("runs", "list the runs of a project with their state", _configure_runs, _runs),
    CommandSpec("export", "export a product of a run (default: heads)", _configure_export, _export),
]
