"""Initial heads (docs/SPEC.md, sections 8.1 and 9).

M1a supports a constant value or a raster (a piezometric map), sampled on the
grid like the contact surfaces and applied to every layer. Interpolation of the
measurements (M3) and heads from a previous run come later.
With the initial steady period enabled, the initial heads are only the starting
guess of the solver.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from phrear.errors import GeometryError, InitialHeadsError
from phrear.events import Problem
from phrear.geology.surfaces import sample_surface
from phrear.grid.model_grid import ModelGrid
from phrear.project import Project
from phrear.project.config import ConstantHeads, RasterHeads

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class InitialHeads:
    strt: FloatArray
    """(nlay, nrow, ncol), m a.s.l."""
    mode: str
    warnings: tuple[Problem, ...] = ()


def _lowest_active_bottom(grid: ModelGrid) -> FloatArray:
    """Bottom of the lowest active cell of each column (NaN where none is active)."""
    bottom = np.full(grid.top.shape, np.nan)
    for layer in range(grid.nlay):
        bottom = np.where(grid.idomain[layer] > 0, grid.botm[layer], bottom)
    return bottom


def _first(mask: npt.NDArray[np.bool_]) -> tuple[int, int]:
    row, col = (int(i) + 1 for i in np.argwhere(mask)[0])
    return row, col


def initial_heads(project: Project, grid: ModelGrid) -> InitialHeads:
    settings = project.config.initial_heads
    if settings is None:
        raise InitialHeadsError("init.missing")
    warnings: list[Problem] = []
    if isinstance(settings, ConstantHeads):
        head2d = np.full(grid.top.shape, settings.value_m)
    elif isinstance(settings, RasterHeads):
        rel = settings.raster_path
        sampled = sample_surface(project.root / rel, rel, grid.geometry, project.config.crs)
        warnings += sampled.warnings
        active = (grid.idomain != 0).any(axis=0)
        missing = active & np.isnan(sampled.values)
        if missing.any():
            row, col = _first(missing)
            raise GeometryError(
                "geometry.raster_coverage", path=rel, n_cells=int(missing.sum()), row=row, col=col
            )
        head2d = np.where(np.isnan(sampled.values), 0.0, sampled.values)
    else:
        raise InitialHeadsError("init.mode_not_available", mode=settings.mode)

    bottom = _lowest_active_bottom(grid)
    dry = ~np.isnan(bottom) & (head2d < bottom)
    if dry.any():
        row, col = _first(dry)
        warnings.append(
            Problem.from_code(
                "init.dry_columns", {"n_cells": int(dry.sum()), "row": row, "col": col}
            )
        )
    strt = np.broadcast_to(head2d, grid.botm.shape).copy()
    return InitialHeads(strt=strt, mode=settings.mode, warnings=tuple(warnings))
