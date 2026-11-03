"""Registry of the boundary condition types and assembly of the model boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from phrear.boundaries import fixed_heads, recharge, wells
from phrear.boundaries.base import BcContext, BoundaryConditionType, PackageInput
from phrear.errors import ErrorCollector
from phrear.events import Problem
from phrear.grid.model_grid import ModelGrid
from phrear.params.layers import LayerParameters
from phrear.project import Project
from phrear.timeline import Timeline
from phrear.timeline.mf6ts import mf6_names

#: Registered types, in the order their packages are written.
BOUNDARY_TYPES: dict[str, BoundaryConditionType] = {
    t.name: t for t in (wells.TYPE, fixed_heads.TYPE, recharge.TYPE)
}


def register(bc_type: BoundaryConditionType) -> None:
    """Add a boundary condition type (used by later milestones and extensions)."""
    if bc_type.name in BOUNDARY_TYPES:
        raise ValueError(f"boundary condition type {bc_type.name!r} already registered")
    BOUNDARY_TYPES[bc_type.name] = bc_type


@dataclass(frozen=True)
class Boundaries:
    packages: tuple[PackageInput, ...]
    """One per registered type, possibly without assignments."""

    @property
    def warnings(self) -> tuple[Problem, ...]:
        return tuple(w for p in self.packages for w in p.warnings)

    def ts_names(self) -> dict[str, str]:
        """MF6 names of every time series used by the boundaries."""
        return mf6_names(sorted({sid for p in self.packages for sid in p.series()}))


def build_boundaries(
    project: Project,
    grid: ModelGrid,
    layers: LayerParameters,
    timeline: Timeline,
    errors: ErrorCollector | None = None,
) -> Boundaries:
    """Boundaries of the base model; ``errors`` may gather one error per feature."""
    ctx = BcContext(
        project=project,
        grid=grid,
        layers=layers,
        timeline=timeline,
        errors=errors or ErrorCollector(),
    )
    return Boundaries(tuple(t.build(ctx) for t in BOUNDARY_TYPES.values()))
