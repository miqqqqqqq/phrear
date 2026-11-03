"""MODFLOW 6 input files of an inspected project, written with FloPy.

The simulation has one GWF model on a DIS grid, with the MF6 conventions used
everywhere in the core (ADR 0010): lengths in metres, time in days, origin at
the lower-left corner, counter-clockwise rotation. Boundary packages come from
the registered boundary types; their time series go to TS files grouped by
shared dates. A period block is written only when its entries differ from the
previous period, because MF6 keeps the last block in force.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

import flopy

from phrear.boundaries.base import PackageInput, Record
from phrear.checks.base import Inspection
from phrear.project.config import ProjectConfig
from phrear.timeline.calendar import Calendar
from phrear.timeline.mf6ts import TsRecords

SIM_NAME: Final = "mfsim"
MODEL: Final = "gwf"
HEAD_FILE: Final = f"{MODEL}.hds"
BUDGET_FILE: Final = f"{MODEL}.cbc"
BUDGET_CSV: Final = f"{MODEL}.bud.csv"
MODEL_LISTING: Final = f"{MODEL}.lst"
SIM_LISTING: Final = "mfsim.lst"
SOLVER_CSV: Final = "ims_outer.csv"
FLOAT_PRECISION: Final = 15

#: Tolerances shared by the presets: head change (m) and residual (m³/d).
TOLERANCES: Final[dict[str, Any]] = {
    "outer_dvclose": 1e-4,
    "inner_dvclose": 1e-5,
    "rcloserecord": [1e-3, "strict"],
}
PRESETS: Final[dict[str, dict[str, Any]]] = {
    "standard": {"complexity": "moderate", "outer_maximum": 100, "inner_maximum": 300},
    "robust": {"complexity": "complex", "outer_maximum": 500, "inner_maximum": 500},
    "expert": {"complexity": "moderate", "outer_maximum": 100, "inner_maximum": 300},
}

_CLASSES: Final = {
    "wel": flopy.mf6.ModflowGwfwel,
    "chd": flopy.mf6.ModflowGwfchd,
    "rch": flopy.mf6.ModflowGwfrch,
}
_WITH_MULT: Final = {"wel", "rch"}


@dataclass(frozen=True)
class Simulation:
    workspace: Path
    files: tuple[str, ...]
    entries: dict[str, int]
    """Entries of each boundary package in the last stress period."""
    series: int
    """Time series written."""


def ims_options(config: ProjectConfig) -> dict[str, Any]:
    """IMS settings of the solver preset (docs/SPEC.md, section 8.1)."""
    options: dict[str, Any] = {**PRESETS[config.solver.preset], **TOLERANCES}
    if config.options.newton or config.options.xt3d == "on":
        options["linear_acceleration"] = "bicgstab"
    if config.solver.preset == "expert":
        options.update(config.solver.ims)
    return options


def _row(package: str, record: Record) -> tuple[Any, ...]:
    cell, value, mult, boundname = record
    if package in _WITH_MULT:
        return (cell, value, mult, boundname)
    return (cell, value, boundname)


def _period_data(records: list[list[Record]], package: str) -> dict[int, list[tuple[Any, ...]]]:
    data: dict[int, list[tuple[Any, ...]]] = {}
    previous: list[Record] | None = None
    for kper, rows in enumerate(records):
        if rows == previous or (not rows and previous is None):
            continue
        data[kper] = [_row(package, r) for r in rows]
        previous = rows
    return data


def _write_series(package: Any, name: str, records: list[TsRecords]) -> None:
    groups: dict[tuple[str, tuple[float, ...]], list[TsRecords]] = {}
    for r in records:
        groups.setdefault((r.method, tuple(t for t, _ in r.rows)), []).append(r)
    for i, ((method, times), members) in enumerate(groups.items(), start=1):
        rows = [(t, *(m.rows[j][1] for m in members)) for j, t in enumerate(times)]
        options = {
            "filename": f"{MODEL}.{name}_{i:03d}.ts",
            "timeseries": rows,
            "time_series_namerecord": [m.name for m in members],
            "interpolation_methodrecord": [method] * len(members),
        }
        if i == 1:
            package.ts.initialize(**options)
        else:
            package.ts.append_package(**options)


def _write_boundary(
    gwf: Any, package: PackageInput, calendar: Calendar, names: dict[str, str]
) -> tuple[int, int]:
    records = package.period_records(calendar, names)
    options: dict[str, Any] = {
        "stress_period_data": _period_data(records, package.package),
        "boundnames": True,
        "save_flows": True,
        "pname": package.package,
        "filename": f"{MODEL}.{package.package}",
    }
    if package.package in _WITH_MULT:
        options |= {"auxiliary": ["mult"], "auxmultname": "mult"}
    written = _CLASSES[package.package](gwf, **options)
    series = package.ts_records(calendar, names)
    if series:
        _write_series(written, package.package, series)
    return len(records[-1]), len(series)


def write_simulation(ins: Inspection, workspace: Path) -> Simulation:
    """Write the MF6 input of an inspection without errors into ``workspace``."""
    grid, layers, heads = ins.grid, ins.layers, ins.heads
    timeline, boundaries = ins.timeline, ins.boundaries
    if not ins.ok or None in (grid, layers, heads, timeline, boundaries):
        raise ValueError("the inspection has errors or is incomplete")
    assert grid and layers and heads and timeline and boundaries
    config = ins.project.config
    calendar = timeline.calendar
    workspace.mkdir(parents=True, exist_ok=True)

    sim = flopy.mf6.MFSimulation(
        sim_name=SIM_NAME, sim_ws=str(workspace), exe_name="mf6", verbosity_level=0
    )
    # 15 significant digits, so that time series, step multipliers and arrays are
    # written without loss (FloPy defaults to 8)
    sim.simulation_data.float_precision = FLOAT_PRECISION
    sim.simulation_data.float_characters = FLOAT_PRECISION + 9
    zero = calendar.start - timedelta(days=calendar.offset_d)
    flopy.mf6.ModflowTdis(
        sim,
        time_units="days",
        start_date_time=zero.isoformat(),
        nper=len(calendar.periods),
        perioddata=[(p.perlen_d, p.nstp, p.tsmult) for p in calendar.periods],
    )
    flopy.mf6.ModflowIms(
        sim, print_option="summary", csv_outer_output_filerecord=SOLVER_CSV, **ims_options(config)
    )
    gwf = flopy.mf6.ModflowGwf(
        sim,
        modelname=MODEL,
        save_flows=True,
        newtonoptions="under_relaxation" if config.options.newton else None,
    )
    g = grid.geometry
    flopy.mf6.ModflowGwfdis(
        gwf,
        length_units="meters",
        nlay=grid.nlay,
        nrow=g.nrow,
        ncol=g.ncol,
        delr=g.cell_size,
        delc=g.cell_size,
        top=grid.top,
        botm=grid.botm,
        idomain=grid.idomain,
        xorigin=g.xorigin,
        yorigin=g.yorigin,
        angrot=g.angrot,
    )
    flopy.mf6.ModflowGwfic(gwf, strt=heads.strt)
    flopy.mf6.ModflowGwfnpf(
        gwf,
        icelltype=layers.icelltype,
        k=layers.k,
        k33=layers.k33,
        save_specific_discharge=True,
        xt3doptions=True if config.options.xt3d == "on" else None,
    )
    steady = {p.index - 1: True for p in calendar.periods if p.kind == "steady"}
    transient = {p.index - 1: True for p in calendar.periods if p.kind == "transient"}
    first_transient = min(transient) if transient else None
    flopy.mf6.ModflowGwfsto(
        gwf,
        iconvert=layers.icelltype,
        ss=layers.ss,
        sy=layers.sy,
        steady_state={k: True for k in steady},
        transient={first_transient: True} if first_transient is not None else None,
    )
    names = boundaries.ts_names()
    entries: dict[str, int] = {}
    n_series = 0
    for package in boundaries.packages:
        if package.assignments:
            entries[package.package], written = _write_boundary(gwf, package, calendar, names)
            n_series += written
    flopy.mf6.ModflowGwfoc(
        gwf,
        head_filerecord=HEAD_FILE,
        budget_filerecord=BUDGET_FILE,
        budgetcsv_filerecord=BUDGET_CSV,
        saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")],
        printrecord=[("BUDGET", "LAST")],
    )
    sim.write_simulation(silent=True)
    files = tuple(sorted(p.name for p in workspace.iterdir() if p.is_file()))
    return Simulation(workspace=workspace, files=files, entries=entries, series=n_series)
