"""Running the verification cases and judging the results."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from phrear.checks.inspection import inspect_project
from phrear.errors import RunError
from phrear.modflow.pipeline import build_run, execute, outcome_error
from phrear.verification.cases import Case, Comparison, reference


@dataclass(frozen=True)
class CaseResult:
    case: Case
    comparison: Comparison
    max_error: float
    """Largest absolute difference at the comparison points, m."""
    reference: float
    """s_max (m) for the well cases, 1 for the absolute tolerance."""
    points: int
    duration_s: float
    run_folder: Path

    @property
    def measure(self) -> float:
        """The quantity compared with the tolerance."""
        return self.max_error / self.reference

    @property
    def passed(self) -> bool:
        return self.measure <= self.case.tolerance


def run_case(case: Case, root: Path) -> CaseResult:
    start = time.perf_counter()
    project = case.build(root / case.name)
    ins = inspect_project(project)
    if not ins.ok:
        raise RuntimeError(f"verification case {case.name} has errors: {ins.errors[0].code}")
    run = build_run(ins, "verifica")
    outcome = execute(run)
    error: RunError | None = outcome_error(run, outcome)
    if error is not None:
        raise error
    comparison = case.compare(ins, run.folder)
    return CaseResult(
        case=case,
        comparison=comparison,
        max_error=comparison.max_error,
        reference=reference(case, comparison),
        points=int(comparison.simulated.size),
        duration_s=time.perf_counter() - start,
        run_folder=run.folder,
    )
