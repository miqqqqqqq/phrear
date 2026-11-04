"""Build of a run from an inspected project, execution and outcome."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from phrear.checks.base import Inspection
from phrear.errors import RunError
from phrear.events import Problem
from phrear.modflow.engine import engine_version, mf6_executable
from phrear.modflow.manifest import manifest_data, new_run_dir, read_manifest, write_manifest
from phrear.modflow.runner import STDOUT_FILE, RunOutcome, run_mf6
from phrear.modflow.simulation import MODEL_LISTING, SIM_LISTING, Simulation, write_simulation
from phrear.project.features import fmt
from phrear.timeline.calendar import Calendar, first_step

#: Budget discrepancy above which a run gets a warning, percent.
DISCREPANCY_WARNING_PCT = 1.0


@dataclass(frozen=True)
class BuiltRun:
    run_id: str
    folder: Path
    simulation: Simulation
    engine: dict[str, str]
    calendar: Calendar


def build_run(ins: Inspection, run_id: str | None = None) -> BuiltRun:
    """Write the MF6 files and the manifest of a new run; ``ins`` must have no errors."""
    assert ins.timeline is not None
    try:
        executable = mf6_executable()
        engine = {"version": engine_version(executable), "executable": str(executable)}
    except RunError:
        engine = {"version": "unknown", "executable": ""}
    now = datetime.now().astimezone()
    run_id, folder = new_run_dir(ins.project.root, run_id, now)
    simulation = write_simulation(ins, folder)
    write_manifest(folder, manifest_data(ins, run_id, simulation, engine, now))
    return BuiltRun(run_id, folder, simulation, engine, ins.timeline.calendar)


def step_ends(calendar: Calendar) -> dict[tuple[int, int], float]:
    """Simulation time [d] at the end of each (period, step), 1-based."""
    ends: dict[tuple[int, int], float] = {}
    elapsed = 0.0
    for p in calendar.periods:
        dt = first_step(p.perlen_d, p.nstp, p.tsmult)
        inside = 0.0
        for step in range(1, p.nstp + 1):
            inside += dt
            ends[(p.index, step)] = elapsed + inside
            dt *= p.tsmult
        elapsed += p.perlen_d
    return ends


def step_fractions(calendar: Calendar) -> dict[tuple[int, int], float]:
    """Fraction of the simulated time reached at the end of each (period, step)."""
    total = sum(p.perlen_d for p in calendar.periods)
    return {key: min(1.0, t / total) for key, t in step_ends(calendar).items()}


def worst_discrepancy(run: BuiltRun, outcome: RunOutcome) -> tuple[int, int, float] | None:
    """(period, step, percent) of the largest budget discrepancy of the run."""
    worst = outcome.max_discrepancy
    if worst is None:
        return None
    time, value = worst
    ends = step_ends(run.calendar)
    (period, step), _ = min(ends.items(), key=lambda item: abs(item[1] - time))
    return period, step, value


def outcome_error(run: BuiltRun, outcome: RunOutcome) -> RunError | None:
    listing = str(run.folder / SIM_LISTING)
    if outcome.errors:
        return RunError(
            "run.engine_error", run_id=run.run_id, message=outcome.errors[0], listing=listing
        )
    if outcome.not_converged is not None:
        period, step = outcome.not_converged
        return RunError(
            "run.convergence",
            run_id=run.run_id,
            period=period,
            step=step,
            listing=str(run.folder / MODEL_LISTING),
        )
    if not outcome.success:
        return RunError(
            "run.terminated",
            run_id=run.run_id,
            returncode=outcome.returncode,
            listing=listing,
            stdout=str(run.folder / STDOUT_FILE),
        )
    return None


def outcome_warnings(run: BuiltRun, outcome: RunOutcome) -> list[Problem]:
    worst = worst_discrepancy(run, outcome)
    if worst is None or abs(worst[2]) <= DISCREPANCY_WARNING_PCT:
        return []
    period, step, value = worst
    return [
        Problem.from_code(
            "run.budget_discrepancy",
            {"run_id": run.run_id, "value": fmt(value), "period": period, "step": step},
        )
    ]


def execute(run: BuiltRun, on_step: Callable[[int, int], None] | None = None) -> RunOutcome:
    """Run MF6 on a built run and record the outcome in its manifest."""
    executable = mf6_executable()
    started = datetime.now().astimezone()
    # A run stopped from outside (cancelled, killed) stays "running" in its manifest.
    data = read_manifest(run.folder)
    data["run"] = {"status": "running", "started": started.isoformat(timespec="seconds")}
    write_manifest(run.folder, data)
    outcome = run_mf6(run.folder, executable, on_step)
    error = outcome_error(run, outcome)
    worst = worst_discrepancy(run, outcome)
    data = read_manifest(run.folder)
    record: dict[str, Any] = {
        "status": "completed" if error is None else "failed",
        "started": started.isoformat(timespec="seconds"),
        "duration_s": round(outcome.duration_s, 3),
        "returncode": outcome.returncode,
        "last_step": list(outcome.last_step) if outcome.last_step else None,
        "max_budget_discrepancy": None
        if worst is None
        else {"period": worst[0], "step": worst[1], "pct": worst[2]},
    }
    if error is not None:
        record["error"] = {"code": error.code, "message": error.message("en")}
    data["run"] = record
    data["files"] = sorted(p.name for p in run.folder.iterdir() if p.is_file())
    write_manifest(run.folder, data)
    return outcome
