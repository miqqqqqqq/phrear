"""Stages, inspection results and the registered check type."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, Literal

from phrear.boundaries.base import PackageInput
from phrear.boundaries.registry import Boundaries
from phrear.conceptual.initial_heads import InitialHeads
from phrear.errors import Localized
from phrear.events import Problem
from phrear.grid.model_grid import ModelGrid
from phrear.params.layers import LayerParameters
from phrear.params.values import ParameterSet
from phrear.project import Project
from phrear.timeline import Timeline

Stage = Literal["time", "grid", "params", "initial_heads", "boundaries", "model"]

#: Stages in the order they run, with their labels.
STAGES: Final[dict[Stage, Localized]] = {
    "time": Localized("Tempo", "Time"),
    "grid": Localized("Griglia", "Grid"),
    "params": Localized("Parametri", "Parameters"),
    "initial_heads": Localized("Carichi iniziali", "Initial heads"),
    "boundaries": Localized("Condizioni al contorno", "Boundary conditions"),
    "model": Localized("Controlli del modello", "Model checks"),
}


@dataclass
class StageResult:
    stage: Stage
    errors: list[Problem] = field(default_factory=list)
    warnings: list[Problem] = field(default_factory=list)
    skipped_for: tuple[Stage, ...] = ()
    """Failed stages this one depends on; not empty means it did not run."""

    @property
    def status(self) -> Literal["ok", "errors", "skipped"]:
        if self.skipped_for:
            return "skipped"
        return "errors" if self.errors else "ok"


@dataclass
class Inspection:
    """Everything assembled from a project, with the problems found on the way."""

    project: Project
    stages: list[StageResult] = field(default_factory=list)
    timeline: Timeline | None = None
    grid: ModelGrid | None = None
    params: ParameterSet | None = None
    layers: LayerParameters | None = None
    heads: InitialHeads | None = None
    boundaries: Boundaries | None = None
    checks: dict[str, Literal["ok", "errors", "warnings", "skipped"]] = field(default_factory=dict)

    @property
    def errors(self) -> list[Problem]:
        return [p for s in self.stages for p in s.errors]

    @property
    def warnings(self) -> list[Problem]:
        return [p for s in self.stages for p in s.warnings]

    @property
    def ok(self) -> bool:
        return not self.errors

    def stage(self, stage: Stage) -> StageResult:
        return next(s for s in self.stages if s.stage == stage)

    def passed(self, stage: Stage) -> bool:
        return any(s.stage == stage and s.status == "ok" for s in self.stages)

    def package(self, bc_type: str) -> PackageInput:
        assert self.boundaries is not None
        return next(p for p in self.boundaries.packages if p.bc_type == bc_type)


@dataclass(frozen=True)
class Check:
    """A registered model check (docs/SPEC.md, section 21).

    It runs only when the stages in ``requires`` passed, and returns problems of
    its ``severity``: errors block the run, warnings are recorded in its log.
    """

    name: str
    label: Localized
    severity: Literal["error", "warning"]
    requires: tuple[Stage, ...]
    run: Callable[[Inspection], list[Problem]] = field(repr=False)
