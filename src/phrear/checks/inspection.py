"""Assembly of the model with every problem gathered (docs/SPEC.md, section 15).

Each stage runs only if the stages it depends on passed; parameters and boundary
conditions report one error per row or feature, the other stages their first
error. Then the registered checks run on what was assembled.
"""

from __future__ import annotations

from collections.abc import Callable

from phrear.boundaries.registry import build_boundaries
from phrear.checks.base import Inspection, Stage, StageResult
from phrear.checks.registry import CHECKS
from phrear.conceptual.initial_heads import initial_heads
from phrear.errors import ErrorCollector, PhrearError
from phrear.events import Problem
from phrear.grid.model_grid import build_model_grid
from phrear.params.layers import layer_parameters
from phrear.params.values import load_parameters
from phrear.project import Project
from phrear.timeline import project_timeline


def _run(
    ins: Inspection,
    stage: Stage,
    requires: tuple[Stage, ...],
    body: Callable[[ErrorCollector], list[Problem]],
) -> None:
    missing = tuple(s for s in requires if not ins.passed(s))
    if missing:
        ins.stages.append(StageResult(stage, skipped_for=missing))
        return
    errors = ErrorCollector(collect=True)
    warnings: list[Problem] = []
    try:
        warnings = body(errors)
    except PhrearError as exc:
        errors.errors.append(exc)
    ins.stages.append(
        StageResult(stage, errors=[Problem.from_error(e) for e in errors.errors], warnings=warnings)
    )


def inspect_project(project: Project) -> Inspection:
    ins = Inspection(project)

    def time(_: ErrorCollector) -> list[Problem]:
        ins.timeline = project_timeline(project)
        return list(ins.timeline.calendar.warnings)

    def grid(_: ErrorCollector) -> list[Problem]:
        ins.grid = build_model_grid(project)
        return list(ins.grid.warnings)

    def params(errors: ErrorCollector) -> list[Problem]:
        loaded = load_parameters(project, errors)
        if not errors.errors:
            ins.params = loaded
        return list(loaded.warnings)

    def heads(_: ErrorCollector) -> list[Problem]:
        assert ins.grid is not None
        ins.heads = initial_heads(project, ins.grid)
        return list(ins.heads.warnings)

    def boundaries(errors: ErrorCollector) -> list[Problem]:
        assert ins.grid is not None and ins.params is not None and ins.timeline is not None
        ins.layers = layer_parameters(ins.grid, ins.params)
        built = build_boundaries(project, ins.grid, ins.layers, ins.timeline, errors)
        if not errors.errors:
            ins.boundaries = built
        return list(built.warnings)

    _run(ins, "time", (), time)
    _run(ins, "grid", (), grid)
    _run(ins, "params", (), params)
    _run(ins, "initial_heads", ("grid",), heads)
    _run(ins, "boundaries", ("time", "grid", "params"), boundaries)

    result = StageResult("model")
    for check in CHECKS.values():
        if not all(ins.passed(s) for s in check.requires):
            ins.checks[check.name] = "skipped"
            continue
        found = check.run(ins)
        if check.severity == "error":
            result.errors += found
            ins.checks[check.name] = "errors" if found else "ok"
        else:
            result.warnings += found
            ins.checks[check.name] = "warnings" if found else "ok"
    ins.stages.append(result)
    return ins
