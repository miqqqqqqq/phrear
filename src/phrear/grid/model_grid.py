"""Model grid from the conceptual model (docs/SPEC.md, sections 10 and 14).

Steps: domain → covering DIS grid → active columns → contact surfaces sampled on
the grid → checks → layers. Each unit becomes ``sublayers`` layers of equal
thickness. Where a unit is thinner than ``grid.min_thickness_m`` its cells become
vertical pass-through cells (IDOMAIN = -1), so vertical flow is not interrupted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import flopy
import numpy as np
import numpy.typing as npt
import pyogrio
import shapely

from phrear.errors import GeometryError, GridError, ObjectRef
from phrear.events import Problem
from phrear.geology.surfaces import sample_surface
from phrear.grid.structured import (
    FloatArray,
    StructuredGeometry,
    active_by_centroid,
    area_fractions,
    covering_geometry,
)
from phrear.project import Project, gpkg

IntArray = npt.NDArray[np.int64]
CROSSING_TOLERANCE_M = 1e-6
BYTES_PER_CELL = 1024
"""Order of magnitude of MF6 memory per active cell, for the preview only."""


@dataclass(frozen=True)
class Unit:
    fid: int
    position: int
    name: str
    sublayers: int
    convertible: bool


@dataclass(frozen=True)
class ModelGrid:
    geometry: StructuredGeometry
    top: FloatArray
    """(nrow, ncol), model top = surface 0."""
    botm: FloatArray
    """(nlay, nrow, ncol)."""
    idomain: IntArray
    """(nlay, nrow, ncol): 1 active, -1 vertical pass-through, 0 inactive."""
    layer_unit: tuple[int, ...]
    """Position of the hydrostratigraphic unit of each layer."""
    units: tuple[Unit, ...]
    dem: FloatArray | None
    warnings: tuple[Problem, ...]

    @property
    def nlay(self) -> int:
        return int(self.botm.shape[0])

    def flopy_grid(self) -> flopy.discretization.StructuredGrid:
        g = self.geometry
        return flopy.discretization.StructuredGrid(
            delc=np.full(g.nrow, g.cell_size),
            delr=np.full(g.ncol, g.cell_size),
            top=self.top,
            botm=self.botm,
            idomain=self.idomain,
            xoff=g.xorigin,
            yoff=g.yorigin,
            angrot=g.angrot,
        )

    def summary(self) -> dict[str, Any]:
        g = self.geometry
        active = int((self.idomain > 0).sum())
        return {
            "type": "dis",
            "nlay": self.nlay,
            "nrow": g.nrow,
            "ncol": g.ncol,
            "cell_size_m": g.cell_size,
            "xorigin": g.xorigin,
            "yorigin": g.yorigin,
            "angrot_deg": g.angrot,
            "cells": self.nlay * g.ncell,
            "active_cells": active,
            "layers": [
                {
                    "layer": k + 1,
                    "unit": self.layer_unit[k],
                    "active": int((self.idomain[k] > 0).sum()),
                    "pass_through": int((self.idomain[k] < 0).sum()),
                }
                for k in range(self.nlay)
            ],
            "memory_estimate_mb": round(active * BYTES_PER_CELL / 1e6, 1),
        }


# --- reading the conceptual model -----------------------------------------------


def _domain(project: Project) -> shapely.Geometry:
    frame = pyogrio.read_dataframe(project.gpkg_path, layer="domain", fid_as_index=True)
    if not frame.empty:
        # NULL in "active" means the schema default, True
        active = frame["active"].map(lambda v: True if v is None or v != v else bool(v))
        base = frame["scenario_id"].isna() | (frame["scenario_id"] == "")
        frame = frame[active.astype(bool) & base & frame.geometry.notna()]
    if frame.empty:
        raise GeometryError("geometry.no_domain")
    for fid, geom in zip(frame.index, frame.geometry, strict=True):
        if not shapely.is_valid(geom):
            raise GeometryError(
                "geometry.domain_invalid",
                reason=shapely.is_valid_reason(geom),
                ref=ObjectRef(kind="feature", layer="domain", fid=int(fid)),
            )
    return shapely.union_all(np.asarray(frame.geometry.values))


def _units(project: Project) -> tuple[Unit, ...]:
    with gpkg.connect(project.gpkg_path) as conn:
        rows = conn.execute(
            'SELECT fid, position, name, sublayers, convertible FROM "hydro_units" '
            "ORDER BY position"
        ).fetchall()
    if not rows:
        raise GeometryError("geometry.no_units")
    positions = [r[1] for r in rows]
    if positions != list(range(1, len(rows) + 1)):
        raise GeometryError("geometry.unit_positions", positions=", ".join(map(str, positions)))
    return tuple(
        Unit(
            fid=int(fid),
            position=int(pos),
            name=str(name),
            sublayers=int(sub) if sub else 1,
            convertible=True if conv is None else bool(conv),
        )
        for fid, pos, name, sub, conv in rows
    )


def _surface_paths(project: Project, n_units: int) -> list[str]:
    with gpkg.connect(project.gpkg_path) as conn:
        rows = conn.execute(
            'SELECT surface_index, raster_path FROM "surfaces" ORDER BY surface_index'
        ).fetchall()
    indices = [r[0] for r in rows]
    if indices != list(range(n_units + 1)):
        raise GeometryError(
            "geometry.surfaces_mismatch",
            n_units=n_units,
            indices=", ".join(map(str, indices)) or "—",
        )
    return [str(r[1]) for r in rows]


def _first(mask: npt.NDArray[np.bool_]) -> tuple[int, ...]:
    """1-based index of the first True cell."""
    return tuple(int(i) + 1 for i in np.argwhere(mask)[0])


# --- grid construction ------------------------------------------------------------


def _layers(
    surfaces: list[FloatArray],
    units: tuple[Unit, ...],
    active: npt.NDArray[np.bool_],
    min_thickness: float,
) -> tuple[FloatArray, IntArray, tuple[int, ...], list[Problem]]:
    warnings: list[Problem] = []
    botm_list: list[FloatArray] = []
    idomain_list: list[IntArray] = []
    layer_unit: list[int] = []
    thin_any = np.zeros_like(active)
    thin_all = active.copy()
    for unit, upper, lower in zip(units, surfaces[:-1], surfaces[1:], strict=True):
        thin = active & ((upper - lower) < min_thickness)
        thin_all &= thin
        thin_any |= thin
        n_thin = int(thin.sum())
        if n_thin:
            warnings.append(
                Problem.from_code(
                    "geometry.thin_unit",
                    {
                        "unit": f"{unit.position} ({unit.name})",
                        "min_m": f"{min_thickness:g}",
                        "n_cells": n_thin,
                    },
                )
            )
        for j in range(1, unit.sublayers + 1):
            botm_list.append(upper - (upper - lower) * j / unit.sublayers)
            layer_idomain = np.where(active, np.where(thin, -1, 1), 0).astype(np.int64)
            idomain_list.append(layer_idomain)
            layer_unit.append(unit.position)
    idomain = np.stack(idomain_list)
    empty = active & thin_all
    if empty.any():
        idomain[:, empty] = 0
        warnings.append(Problem.from_code("geometry.empty_columns", {"n_cells": int(empty.sum())}))
    botm = np.stack(botm_list)
    botm = np.where(np.isnan(botm), 0.0, botm)
    return botm, idomain, tuple(layer_unit), warnings


def isolated_cells(idomain: IntArray) -> npt.NDArray[np.bool_]:
    """Active cells without any active neighbour (lateral, or vertical through -1 cells)."""
    act = idomain > 0
    nlay, nrow, ncol = act.shape
    lateral = np.zeros_like(act)
    lateral[:, 1:, :] |= act[:, :-1, :]
    lateral[:, :-1, :] |= act[:, 1:, :]
    lateral[:, :, 1:] |= act[:, :, :-1]
    lateral[:, :, :-1] |= act[:, :, 1:]
    vertical = np.zeros_like(act)
    # scan down and up, carrying "an active cell is reachable" through -1 cells
    carry = np.zeros((nrow, ncol), dtype=bool)
    for k in range(nlay):
        vertical[k] |= carry
        carry = np.where(idomain[k] > 0, True, np.where(idomain[k] < 0, carry, False))
    carry = np.zeros((nrow, ncol), dtype=bool)
    for k in range(nlay - 1, -1, -1):
        vertical[k] |= carry
        carry = np.where(idomain[k] > 0, True, np.where(idomain[k] < 0, carry, False))
    isolated: npt.NDArray[np.bool_] = act & ~lateral & ~vertical
    return isolated


def build_model_grid(project: Project) -> ModelGrid:
    """Build the DIS grid of a project and run the geometric checks."""
    settings = project.config.grid
    if settings.type != "dis":
        raise GridError("grid.type_not_available", grid_type=settings.type)
    if settings.cell_size_m is None:
        raise GridError("grid.cell_size_missing")
    epsg = project.config.crs
    domain = _domain(project)
    origin = (
        (settings.origin_x, settings.origin_y)
        if settings.origin_x is not None and settings.origin_y is not None
        else None
    )
    geometry = covering_geometry(domain, settings.cell_size_m, settings.rotation_deg, origin)
    if settings.activation == "centroid":
        active = active_by_centroid(geometry, domain)
    else:
        active = area_fractions(geometry, domain) >= settings.min_area_fraction
    units = _units(project)
    paths = _surface_paths(project, len(units))

    warnings: list[Problem] = []
    surfaces: list[FloatArray] = []
    for index, rel in enumerate(paths):
        sampled = sample_surface(project.root / rel, rel, geometry, epsg)
        warnings += sampled.warnings
        missing = active & np.isnan(sampled.values)
        if missing.any():
            row, col = _first(missing)
            raise GeometryError(
                "geometry.raster_coverage",
                path=rel,
                n_cells=int(missing.sum()),
                row=row,
                col=col,
                ref=ObjectRef(kind="table", layer="surfaces", field=f"surface_index={index}"),
            )
        surfaces.append(sampled.values)

    for i in range(1, len(surfaces)):
        excess = np.where(active, surfaces[i] - surfaces[i - 1], -np.inf)
        crossing = excess > CROSSING_TOLERANCE_M
        if crossing.any():
            row, col = _first(crossing)
            raise GeometryError(
                "geometry.surfaces_crossing",
                lower=i,
                upper=i - 1,
                n_cells=int(crossing.sum()),
                max_m=f"{float(excess[crossing].max()):.3g}",
                row=row,
                col=col,
                ref=ObjectRef(kind="cell", cell=(row, col)),
            )

    botm, idomain, layer_unit, layer_warnings = _layers(
        surfaces, units, active, settings.min_thickness_m
    )
    warnings += layer_warnings
    top = np.where(active, surfaces[0], 0.0)

    dem_values: FloatArray | None = None
    if project.config.dem is not None:
        rel = project.config.dem.raster_path
        sampled = sample_surface(project.root / rel, rel, geometry, epsg)
        warnings += sampled.warnings
        dem_values = sampled.values
        missing = active & np.isnan(dem_values)
        if missing.any():
            row, col = _first(missing)
            raise GeometryError(
                "geometry.raster_coverage", path=rel, n_cells=int(missing.sum()), row=row, col=col
            )
        above = np.where(active, surfaces[0] - dem_values, -np.inf)
        over = above > settings.dem_tolerance_m
        if over.any():
            warnings.append(
                Problem.from_code(
                    "geometry.top_above_dem",
                    {
                        "tolerance_m": f"{settings.dem_tolerance_m:g}",
                        "n_cells": int(over.sum()),
                        "max_m": f"{float(above[over].max()):.3g}",
                    },
                )
            )

    isolated = isolated_cells(idomain)
    if isolated.any():
        layer, row, col = _first(isolated)
        warnings.append(
            Problem.from_code(
                "grid.isolated_cells",
                {"n_cells": int(isolated.sum()), "layer": layer, "row": row, "col": col},
            )
        )
    n_cells = len(layer_unit) * geometry.ncell
    if n_cells > settings.max_cells_warning:
        warnings.append(
            Problem.from_code(
                "grid.many_cells", {"n_cells": n_cells, "limit": settings.max_cells_warning}
            )
        )
    return ModelGrid(
        geometry=geometry,
        top=top,
        botm=botm,
        idomain=idomain,
        layer_unit=layer_unit,
        units=units,
        dem=dem_values,
        warnings=tuple(warnings),
    )
