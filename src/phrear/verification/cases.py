"""Verification cases, each built as a complete Phrear project (docs/SPEC.md, section 20).

Every case goes through the whole chain a user goes through: GeoPackage features,
rasters, checks, MF6 files, run. The results are compared with the analytical
solution at the cell centres:

- ``flow_1d``: confined strip between two fixed-head lines with uniform recharge.
  The finite-difference solution is exact at the nodes for a quadratic profile,
  so the error must stay within the solver closure (outer_dvclose).
- ``thiem``: confined steady well inside a circular fixed-head boundary.
- ``dupuit``: the same in an unconfined aquifer, solved with the Newton formulation.
- ``theis``: confined transient well in an aquifer large enough for the cone not
  to reach the boundary during pumping.

For the well cases the comparison points are at least three cells from the well
(section 20): the head of the well cell differs from the head in the well.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import numpy.typing as npt
import shapely

from phrear.boundaries.base import PackageInput
from phrear.checks.base import Inspection
from phrear.errors import Localized
from phrear.project import Project
from phrear.project.config import ConstantHeads
from phrear.project.editing import add_row, add_series, add_surface, add_unit, write_raster
from phrear.verification import analytical

FloatArray = npt.NDArray[np.float64]
X0, Y0 = 600_000.0, 4_800_000.0
"""Lower-left corner of every case, EPSG:7791 (RDN2008 / UTM 32N)."""


@dataclass(frozen=True)
class Comparison:
    """Simulated and analytical values at the comparison points."""

    distance: FloatArray
    """Distance from the well, or from the first fixed-head line, m."""
    simulated: FloatArray
    expected: FloatArray
    time: FloatArray | None = None
    """Time since pumping started, d (transient cases)."""
    quantity: Localized = field(default_factory=lambda: Localized("abbassamento", "drawdown"))

    @property
    def max_error(self) -> float:
        return float(np.max(np.abs(self.simulated - self.expected)))


@dataclass(frozen=True)
class Case:
    name: str
    title: Localized
    description: Localized
    tolerance: float
    relative: bool
    """True: tolerance on max error / s_max; False: absolute tolerance in m."""
    build: Callable[[Path], Project] = field(repr=False)
    compare: Callable[[Inspection, Path], Comparison] = field(repr=False)
    parameters: dict[str, str] = field(default_factory=dict)


# --- building blocks ---------------------------------------------------------------


def _project(root: Path, name: str, end: str, size: tuple[float, float], cell: float) -> Project:
    project = Project.create(
        root, name=name, start=datetime(2020, 1, 1), end=datetime.fromisoformat(end)
    )
    project.config.grid.cell_size_m = cell
    add_row(
        project,
        "domain",
        shapely.box(X0, Y0, X0 + size[0], Y0 + size[1]),
        name="dominio",
        active=1,
    )
    return project


def _surfaces(
    project: Project, size: tuple[float, float], cell: float, levels: list[float]
) -> None:
    margin = 2 * cell
    bounds = (X0 - margin, Y0 - margin, X0 + size[0] + margin, Y0 + size[1] + margin)
    for i, level in enumerate(levels):
        add_surface(project, i, write_raster(project, f"rasters/s{i}.tif", bounds, cell, level))


def _fixed_head_outside(project: Project, size: float, centre: tuple[float, float],
                        radius: float, head: float) -> None:  # fmt: skip
    """Fixed head on the cells whose centre lies outside a circle around the well."""
    outside = shapely.box(X0, Y0, X0 + size, Y0 + size).difference(
        shapely.Point(centre).buffer(radius, quad_segs=256)
    )
    fid = add_row(project, "fixed_head_areas", outside, name="contorno")
    add_row(project, "line_stations", shapely.Point(X0 + 1.0, Y0 + 1.0),
            feature_layer="fixed_head_areas", feature_id=fid, value=head)  # fmt: skip


def _well(project: Project, centre: tuple[float, float], top: float, bottom: float,
          **rate: object) -> None:  # fmt: skip
    add_row(project, "wells", shapely.Point(centre), name="pozzo", role="extraction",
            depth_mode="elevation", screen_top=top, screen_bottom=bottom, model_as="wel",
            **rate)  # fmt: skip


def _package(ins: Inspection, name: str) -> PackageInput:
    assert ins.boundaries is not None
    return next(p for p in ins.boundaries.packages if p.package == name)


def _heads(folder: Path) -> tuple[FloatArray, FloatArray]:
    import flopy

    head_file = flopy.utils.HeadFile(str(folder / "gwf.hds"))
    times = np.asarray(head_file.get_times(), dtype=np.float64)
    return times, np.asarray(head_file.get_alldata(), dtype=np.float64)


def _radial_points(ins: Inspection, centre: tuple[float, float], min_r: float,
                   ) -> tuple[npt.NDArray[np.bool_], FloatArray]:  # fmt: skip
    """Free cells at least ``min_r`` from the well, and their distances."""
    assert ins.grid is not None
    x, y = ins.grid.geometry.centers()
    r = np.hypot(x - centre[0], y - centre[1])
    fixed = np.zeros(r.shape, dtype=bool)
    for a in _package(ins, "chd").assignments:
        fixed[a.cell[1:]] = True
    return (~fixed) & (r >= min_r), r


# --- 1D flow -------------------------------------------------------------------------

L1D, W1D, CELL1D = 1000.0, 100.0, 10.0
H1, H2, K1D, B1D = 20.0, 15.0, 10.0, 10.0
N1D = 365.25  # mm/year = 0.001 m/d


def _build_1d(root: Path) -> Project:
    project = _project(root, "Verifica flusso 1D", "2020-01-02", (L1D, W1D), CELL1D)
    project.config.initial_heads = ConstantHeads(value_m=17.0)
    project.save()
    _surfaces(project, (L1D, W1D), CELL1D, [B1D, 0.0])
    add_unit(project, 1, "acquifero", convertible=False,
             params={"kh": (K1D, "m/d"), "kv": (K1D, "m/d"), "ss": (1e-5, "1/m")})  # fmt: skip
    for x, head in ((X0 + CELL1D / 2, H1), (X0 + L1D - CELL1D / 2, H2)):
        fid = add_row(project, "fixed_head_lines", shapely.LineString([(x, Y0), (x, Y0 + W1D)]))
        add_row(project, "line_stations", shapely.Point(x, Y0), feature_layer="fixed_head_lines",
                feature_id=fid, value=head)  # fmt: skip
    add_row(project, "recharge_zones", shapely.box(X0, Y0, X0 + L1D, Y0 + W1D),
            rate=N1D, rate_unit="mm/anno")  # fmt: skip
    return project


def _compare_1d(ins: Inspection, folder: Path) -> Comparison:
    assert ins.grid is not None
    _, heads = _heads(folder)
    x, _ = ins.grid.geometry.centers()
    row = ins.grid.geometry.nrow // 2
    xi = x[row, 1:-1] - (X0 + CELL1D / 2)
    length = L1D - CELL1D
    expected = analytical.flow_1d(xi, length, H1, H2, N1D / 365250.0, K1D * B1D)
    return Comparison(
        distance=xi,
        simulated=heads[0, 0, row, 1:-1],
        expected=expected,
        quantity=Localized("carico", "head"),
    )


# --- Thiem and Dupuit ------------------------------------------------------------------

SIZE_R, CELL_R, RADIUS, HEAD_R = 2010.0, 10.0, 900.0, 20.0
CENTRE_R = (X0 + SIZE_R / 2, Y0 + SIZE_R / 2)
Q_R, K_R, B_R = 500.0, 10.0, 10.0


def _build_thiem(root: Path) -> Project:
    project = _project(root, "Verifica Thiem", "2020-01-02", (SIZE_R, SIZE_R), CELL_R)
    project.config.initial_heads = ConstantHeads(value_m=HEAD_R)
    project.save()
    _surfaces(project, (SIZE_R, SIZE_R), CELL_R, [B_R, 0.0])
    add_unit(project, 1, "acquifero confinato", convertible=False,
             params={"kh": (K_R, "m/d"), "kv": (K_R, "m/d"), "ss": (1e-5, "1/m")})  # fmt: skip
    _fixed_head_outside(project, SIZE_R, CENTRE_R, RADIUS, HEAD_R)
    _well(project, CENTRE_R, B_R, 0.0, rate=Q_R, rate_unit="m3/d")
    return project


def _compare_steady_radial(ins: Inspection, folder: Path,
                           drawdown: Callable[[FloatArray], FloatArray]) -> Comparison:  # fmt: skip
    _, heads = _heads(folder)
    points, r = _radial_points(ins, CENTRE_R, 3 * CELL_R)
    top_layer = heads[0, 0]
    return Comparison(
        distance=r[points],
        simulated=HEAD_R - top_layer[points],
        expected=drawdown(r[points]),
    )


def _compare_thiem(ins: Inspection, folder: Path) -> Comparison:
    return _compare_steady_radial(
        ins, folder, lambda r: analytical.thiem(r, Q_R, K_R * B_R, RADIUS)
    )


TOP_D = 30.0


def _build_dupuit(root: Path) -> Project:
    project = _project(root, "Verifica Dupuit", "2020-01-02", (SIZE_R, SIZE_R), CELL_R)
    project.config.initial_heads = ConstantHeads(value_m=HEAD_R)
    project.save()
    _surfaces(project, (SIZE_R, SIZE_R), CELL_R, [TOP_D, 0.0])
    add_unit(project, 1, "acquifero freatico", convertible=True,
             params={"kh": (K_R, "m/d"), "kv": (K_R, "m/d"), "ss": (1e-5, "1/m"),
                     "sy": (0.2, "")})  # fmt: skip
    _fixed_head_outside(project, SIZE_R, CENTRE_R, RADIUS, HEAD_R)
    _well(project, CENTRE_R, HEAD_R, 0.0, rate=Q_R, rate_unit="m3/d")
    return project


def _compare_dupuit(ins: Inspection, folder: Path) -> Comparison:
    return _compare_steady_radial(
        ins, folder, lambda r: analytical.dupuit_thiem(r, Q_R, K_R, RADIUS, HEAD_R)
    )


# --- Theis --------------------------------------------------------------------------------

SIZE_T, CELL_T, RADIUS_T = 4020.0, 20.0, 1950.0
CENTRE_T = (X0 + SIZE_T / 2, Y0 + SIZE_T / 2)
SS_T = 1e-4  # S = Ss · b = 1e-3
PUMP_START = "2020-01-02"
MAX_R_T = 1000.0


def _build_theis(root: Path) -> Project:
    project = _project(root, "Verifica Theis", "2020-01-04", (SIZE_T, SIZE_T), CELL_T)
    project.config.initial_heads = ConstantHeads(value_m=HEAD_R)
    project.config.time.dt_initial_d = 0.001
    project.save()
    _surfaces(project, (SIZE_T, SIZE_T), CELL_T, [B_R, 0.0])
    add_unit(project, 1, "acquifero confinato", convertible=False,
             params={"kh": (K_R, "m/d"), "kv": (K_R, "m/d"), "ss": (SS_T, "1/m")})  # fmt: skip
    _fixed_head_outside(project, SIZE_T, CENTRE_T, RADIUS_T, HEAD_R)
    add_series(project, "Q", "discharge", "m3/d", [(f"{PUMP_START}T00:00:00", Q_R)])
    _well(project, CENTRE_T, B_R, 0.0, series_id="Q")
    return project


def _compare_theis(ins: Inspection, folder: Path) -> Comparison:
    assert ins.timeline is not None
    calendar = ins.timeline.calendar
    times, heads = _heads(folder)
    start = calendar.sim_time(datetime.fromisoformat(PUMP_START))
    points, r = _radial_points(ins, CENTRE_T, 3 * CELL_T)
    points &= r <= MAX_R_T
    distance, simulated, expected, when = [], [], [], []
    for i, t in enumerate(times):
        elapsed = t - start
        if elapsed <= 0:
            continue
        rr = r[points]
        distance.append(rr)
        simulated.append(HEAD_R - heads[i, 0][points])
        expected.append(analytical.theis(rr, np.full_like(rr, elapsed), Q_R, K_R * B_R,
                                         SS_T * B_R))  # fmt: skip
        when.append(np.full_like(rr, elapsed))
    return Comparison(
        distance=np.concatenate(distance),
        simulated=np.concatenate(simulated),
        expected=np.concatenate(expected),
        time=np.concatenate(when),
    )


CASES: dict[str, Case] = {
    c.name: c
    for c in (
        Case(
            "flow_1d",
            Localized("Flusso monodimensionale con ricarica", "One-dimensional flow with recharge"),
            Localized(
                "Falda confinata tra due linee a carico imposto (20 m e 15 m, distanza 990 m), "
                "T = 100 m²/d, ricarica 365,25 mm/anno; regime stazionario.",
                "Confined aquifer between two fixed-head lines (20 m and 15 m, 990 m apart), "
                "T = 100 m²/d, recharge 365.25 mm/year; steady state.",
            ),
            tolerance=1e-4,
            relative=False,
            build=_build_1d,
            compare=_compare_1d,
            parameters={"cella": "10 m", "celle": "100 × 10"},
        ),
        Case(
            "thiem",
            Localized(
                "Thiem: pozzo in falda confinata, stazionario", "Thiem: confined steady well"
            ),
            Localized(
                "Q = 500 m³/d, T = 100 m²/d, carico imposto 20 m oltre R = 900 m; punti di "
                "confronto ad almeno 3 celle dal pozzo.",
                "Q = 500 m³/d, T = 100 m²/d, fixed head 20 m beyond R = 900 m; comparison "
                "points at least 3 cells from the well.",
            ),
            tolerance=0.01,
            relative=True,
            build=_build_thiem,
            compare=_compare_thiem,
            parameters={"cella": "10 m", "celle": "201 × 201"},
        ),
        Case(
            "theis",
            Localized(
                "Theis: pozzo in falda confinata, transitorio", "Theis: confined transient well"
            ),
            Localized(
                "Q = 500 m³/d per 2 giorni, T = 100 m²/d, S = 10⁻³; punti tra 3 celle e 1000 m "
                "dal pozzo, a ogni passo; il contorno a 1950 m non è raggiunto dal cono.",
                "Q = 500 m³/d for 2 days, T = 100 m²/d, S = 1e-3; points between 3 cells and "
                "1000 m from the well, at every step; the cone does not reach the boundary at "
                "1950 m.",
            ),
            tolerance=0.03,
            relative=True,
            build=_build_theis,
            compare=_compare_theis,
            parameters={"cella": "20 m", "celle": "201 × 201", "primo passo": "0,001 d"},
        ),
        Case(
            "dupuit",
            Localized(
                "Dupuit: pozzo in falda freatica, stazionario", "Dupuit: unconfined steady well"
            ),
            Localized(
                "Q = 500 m³/d, K = 10 m/d, base a 0 m, carico imposto 20 m oltre R = 900 m, "
                "formulazione di Newton; punti ad almeno 3 celle dal pozzo.",
                "Q = 500 m³/d, K = 10 m/d, base at 0 m, fixed head 20 m beyond R = 900 m, "
                "Newton formulation; points at least 3 cells from the well.",
            ),
            tolerance=0.03,
            relative=True,
            build=_build_dupuit,
            compare=_compare_dupuit,
            parameters={"cella": "10 m", "celle": "201 × 201"},
        ),
    )
}


def reference(case: Case, comparison: Comparison) -> float:
    """s_max for the well cases (section 20), 1 m for the absolute tolerance."""
    if not case.relative:
        return 1.0
    return float(np.max(np.abs(comparison.expected)))


__all__ = ["CASES", "X0", "Y0", "Case", "Comparison", "reference"]
