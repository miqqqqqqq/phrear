"""Run commands: build, run."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from phrear.checks.base import Inspection
from phrear.checks.inspection import inspect_project
from phrear.commands.base import CommandSpec, Context
from phrear.commands.check_commands import emit_problems, print_problems, raise_if_errors
from phrear.errors import Lang
from phrear.events import Problem, Progress, RunCompleted, RunFailed, RunStarted, Text
from phrear.modflow.manifest import read_manifest
from phrear.modflow.pipeline import (
    BuiltRun,
    build_run,
    execute,
    outcome_error,
    outcome_warnings,
    step_fractions,
    worst_discrepancy,
)
from phrear.modflow.runner import RunOutcome
from phrear.project import Project
from phrear.results.exporters import EXPORTERS


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")
    parser.add_argument("--run-id", default=None, help="name of the run folder (default: date)")


def _inspected(args: argparse.Namespace, ctx: Context) -> Inspection:
    ins = inspect_project(Project.open(args.path))
    emit_problems(ins, ctx)
    print_problems(ins, ctx)
    raise_if_errors(ins)
    return ins


def _build_data(run: BuiltRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "folder": str(run.folder),
        "files": list(run.simulation.files),
        "entries": run.simulation.entries,
        "series": run.simulation.series,
        "engine": run.engine,
    }


def _build_text(data: dict[str, Any], lang: Lang) -> str:
    entries = ", ".join(f"{k.upper()} {v}" for k, v in data["entries"].items()) or "-"
    if lang == "it":
        return (
            f"Run {data['run_id']} costruito in {data['folder']}\n"
            f"{len(data['files'])} file; righe nell'ultimo periodo {entries}; "
            f"{data['series']} serie temporali"
        )
    return (
        f"Run {data['run_id']} built in {data['folder']}\n"
        f"{len(data['files'])} files; entries in the last period {entries}; "
        f"{data['series']} time series"
    )


def _build(args: argparse.Namespace, ctx: Context) -> int:
    run = build_run(_inspected(args, ctx), args.run_id)
    data = _build_data(run)
    ctx.result("build", data, _build_text(data, ctx.lang))
    return 0


def _run_text(data: dict[str, Any], lang: Lang) -> str:
    worst = data["max_budget_discrepancy"]
    if lang == "it":
        text = f"Run {data['run_id']} completato in {data['duration_s']:.1f} s"
        if worst:
            text += (
                f"; errore di bilancio massimo {worst['pct']:.2g} % "
                f"(periodo {worst['period']}, passo {worst['step']})"
            )
        return text + f"\nRisultati in {data['folder']}; carichi in {data['heads']}"
    text = f"Run {data['run_id']} completed in {data['duration_s']:.1f} s"
    if worst:
        text += (
            f"; largest budget error {worst['pct']:.2g} % "
            f"(period {worst['period']}, step {worst['step']})"
        )
    return text + f"\nResults in {data['folder']}; heads in {data['heads']}"


def _run_data(run: BuiltRun, outcome: RunOutcome) -> dict[str, Any]:
    worst = worst_discrepancy(run, outcome)
    return {
        **_build_data(run),
        "duration_s": round(outcome.duration_s, 3),
        "steps": len(outcome.discrepancies),
        "max_budget_discrepancy": None
        if worst is None
        else {"period": worst[0], "step": worst[1], "pct": worst[2]},
    }


def _run(args: argparse.Namespace, ctx: Context) -> int:
    run = build_run(_inspected(args, ctx), args.run_id)
    sink = ctx.sink
    if sink is not None:
        sink.emit(RunStarted(run_id=run.run_id, engine_version=run.engine["version"]))
    fractions = step_fractions(run.calendar)
    n_periods = len(run.calendar.periods)
    shown: set[int] = set()

    def on_step(period: int, step: int) -> None:
        if sink is not None:
            message = Text(
                it=f"Periodo {period} di {n_periods}, passo {step}",
                en=f"Period {period} of {n_periods}, step {step}",
            )
            fraction = fractions.get((period, step))
            sink.emit(Progress(stage="run", fraction=fraction, message=message))
        elif period not in shown:
            shown.add(period)
            word = "Periodo" if ctx.lang == "it" else "Period"
            ctx.out.write(f"{word} {period}/{n_periods}\n")

    outcome = execute(run, on_step)
    error = outcome_error(run, outcome)
    if error is not None:
        if sink is not None:
            sink.emit(RunFailed(run_id=run.run_id, error=Problem.from_error(error)))
        raise error
    if sink is not None:
        sink.emit(RunCompleted(run_id=run.run_id, duration_s=outcome.duration_s))
    for problem in outcome_warnings(run, outcome):
        ctx.warn(problem)
    data = _run_data(run, outcome)
    heads = EXPORTERS["heads"]
    data["heads"] = str(
        heads.write(run.folder, read_manifest(run.folder), datetime.now().astimezone())
    )
    data["heads_default"] = heads.default_dataset
    ctx.result("run", data, _run_text(data, ctx.lang))
    return 0


COMMANDS = [
    CommandSpec("build", "write the MODFLOW 6 files of a new run", _configure, _build),
    CommandSpec("run", "build a new run and execute MODFLOW 6", _configure, _run),
]
