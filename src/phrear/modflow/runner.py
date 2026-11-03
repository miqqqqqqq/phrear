"""Execution of MODFLOW 6 with the executable, and reading of its outcome.

The executable prints the stress period and time step it is solving; each such
line is passed to ``on_step`` while the run goes on. At the end the listing
files tell whether the run terminated normally, which input errors MF6 found and
where the solver failed to converge; the budget CSV gives the percent budget
discrepancy of every time step. A detailed monitor through modflowapi is M7.
"""

from __future__ import annotations

import csv
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from phrear.modflow.simulation import BUDGET_CSV, MODEL_LISTING, SIM_LISTING

STDOUT_FILE = "mf6.stdout.txt"
_STEP = re.compile(r"Stress period:\s+(\d+)\s+Time step:\s+(\d+)")
_NOT_CONVERGED = re.compile(
    r"FAILED TO MEET SOLVER CONVERGENCE CRITERIA IN TIME STEP\s+(\d+)\s+OF STRESS PERIOD\s+(\d+)",
    flags=re.IGNORECASE,
)
_NORMAL = "Normal termination of simulation"


@dataclass(frozen=True)
class RunOutcome:
    returncode: int
    duration_s: float
    normal_termination: bool
    errors: tuple[str, ...] = ()
    """Lines of the MF6 error report."""
    not_converged: tuple[int, int] | None = None
    """(period, step) of the first convergence failure, 1-based."""
    last_step: tuple[int, int] | None = None
    discrepancies: list[tuple[float, float]] = field(default_factory=list)
    """(simulation time at the end of the step [d], percent discrepancy) of every step."""

    @property
    def success(self) -> bool:
        return self.returncode == 0 and self.normal_termination and self.not_converged is None

    @property
    def max_discrepancy(self) -> tuple[float, float] | None:
        if not self.discrepancies:
            return None
        return max(self.discrepancies, key=lambda d: abs(d[1]))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def error_report(listing: str) -> tuple[str, ...]:
    """Lines of the ERROR REPORT blocks of an MF6 listing, joined per numbered item."""
    items: list[str] = []
    inside = False
    for line in listing.splitlines():
        stripped = line.strip()
        if stripped.endswith("ERROR REPORT:"):
            inside = not stripped.startswith("UNIT")
            continue
        if not inside:
            continue
        if not stripped:
            if items:
                inside = False
            continue
        if re.match(r"^\d+\.\s", stripped):
            items.append(re.sub(r"^\d+\.\s+", "", stripped))
        elif items:
            items[-1] += " " + stripped
    return tuple(" ".join(item.split()) for item in items)


def discrepancies(path: Path) -> list[tuple[float, float]]:
    """(time, percent discrepancy) of every step from the MF6 budget CSV."""
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "PERCENT_DIFFERENCE" not in rows[0] or "time" not in rows[0]:
        return []
    return [(float(r["time"]), float(r["PERCENT_DIFFERENCE"])) for r in rows]


def run_mf6(
    workspace: Path, executable: Path, on_step: Callable[[int, int], None] | None = None
) -> RunOutcome:
    start = time.perf_counter()
    last: tuple[int, int] | None = None
    with (
        (workspace / STDOUT_FILE).open("w", encoding="utf-8") as log,
        subprocess.Popen(
            [str(executable)],
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process,
    ):
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            match = _STEP.search(line)
            if match:
                last = (int(match.group(1)), int(match.group(2)))
                if on_step is not None:
                    on_step(*last)
        returncode = process.wait()
    sim_listing = _read(workspace / SIM_LISTING)
    model_listing = _read(workspace / MODEL_LISTING)
    failure = _NOT_CONVERGED.search(model_listing) or _NOT_CONVERGED.search(sim_listing)
    return RunOutcome(
        returncode=returncode,
        duration_s=time.perf_counter() - start,
        normal_termination=_NORMAL in sim_listing,
        errors=error_report(sim_listing),
        not_converged=(int(failure.group(2)), int(failure.group(1))) if failure else None,
        last_step=last,
        discrepancies=discrepancies(workspace / BUDGET_CSV),
    )
