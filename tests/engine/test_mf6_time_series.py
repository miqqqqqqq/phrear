"""MODFLOW 6 reproduces the project series exactly (docs/SPEC.md, section 13).

A two-cell model with one well driven by a time series built from the calendar:
the volume extracted in each stress period, from the MF6 budget, must equal the
exact integral of the series over that period. This checks the calendar (periods,
time steps, simulation-time offset), the TS records and the MF6 averaging of
STEPWISE and LINEAR series over each time step.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import flopy
import numpy as np
import pytest

from phrear.project.config import ModelTime, TimeStepping
from phrear.timeline.calendar import Calendar, build_calendar
from phrear.timeline.mf6ts import steady_value, ts_records
from phrear.timeline.series import TimeSeries, days_between
from phrear.units import PhysicalQuantity

pytestmark = pytest.mark.engine

START = datetime(2020, 1, 1)
END = datetime(2020, 3, 1)


def _series(points: list[tuple[datetime, float]], linear: bool) -> TimeSeries:
    return TimeSeries(
        series_id="Q",
        quantity=PhysicalQuantity.DISCHARGE,
        unit="m3/d",
        factor=1.0,
        interpolation="linear" if linear else "stepwise",
        times=tuple(t for t, _ in points),
        values=np.array([v for _, v in points], dtype=np.float64),
    )


def _run(workspace: Path, series: TimeSeries, calendar: Calendar, model: ModelTime) -> np.ndarray:
    """Volume pumped in each transient period according to the MF6 budget."""
    sim = flopy.mf6.MFSimulation(sim_name="ts", sim_ws=str(workspace), exe_name="mf6")
    flopy.mf6.ModflowTdis(
        sim,
        nper=len(calendar.periods),
        perioddata=[(p.perlen_d, p.nstp, p.tsmult) for p in calendar.periods],
    )
    flopy.mf6.ModflowIms(sim, complexity="simple")
    gwf = flopy.mf6.ModflowGwf(sim, modelname="m", save_flows=True)
    flopy.mf6.ModflowGwfdis(gwf, nlay=1, nrow=1, ncol=2, delr=50.0, delc=50.0, top=10.0, botm=0.0)
    flopy.mf6.ModflowGwfic(gwf, strt=5.0)
    flopy.mf6.ModflowGwfnpf(gwf, k=10.0)
    flopy.mf6.ModflowGwfsto(gwf, ss=1e-5, steady_state={0: True}, transient={1: True})
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[((0, 0, 1), 5.0)])
    steady = steady_value(series, model)
    assert steady is not None
    records = ts_records(series, calendar, "q")
    wel = flopy.mf6.ModflowGwfwel(
        gwf, stress_period_data={0: [((0, 0, 0), steady)], 1: [((0, 0, 0), records.name)]}
    )
    wel.ts.initialize(
        filename="q.ts",
        timeseries=list(records.rows),
        time_series_namerecord=records.name,
        interpolation_methodrecord=records.method,
    )
    flopy.mf6.ModflowGwfoc(gwf, budget_filerecord="m.cbc", saverecord=[("BUDGET", "ALL")])
    sim.write_simulation(silent=True)
    success, output = sim.run_simulation(silent=True)
    assert success, "\n".join(output[-30:])

    cbc = gwf.output.budget()
    times = np.array(cbc.get_times())
    rates = np.array([cbc.get_data(text="WEL", totim=t)[0]["q"][0] for t in times])
    delt = np.diff(np.concatenate([[0.0], times]))
    kper = np.array([k for _, k in cbc.get_kstpkper()])
    return np.array(
        [
            np.sum(rates[kper == p.index - 1] * delt[kper == p.index - 1])
            for p in calendar.transient_periods
        ]
    )


@pytest.mark.parametrize("linear", [False, True], ids=["stepwise", "linear"])
def test_pumped_volume_equals_series_integral(tmp_path: Path, linear: bool) -> None:
    points = [
        (datetime(2019, 12, 1), -100.0),
        (datetime(2020, 1, 20, 6), -300.0),
        (datetime(2020, 2, 10), -50.0),
        (datetime(2020, 3, 5), -80.0),
    ]
    series = _series(points, linear)
    model = ModelTime(start_date=START, end_date=END, period_breaks=[datetime(2020, 2, 1)])
    stepping = TimeStepping(dt_initial_d=0.5, tsmult=1.3, dt_max_d=4.0)
    calendar = build_calendar(model, stepping, {"Q": series.start})
    volumes = _run(tmp_path, series, calendar, model)
    expected = np.array(
        [
            series.mean_over(p.start, p.end) * days_between(p.start, p.end)
            for p in calendar.transient_periods
        ]
    )
    np.testing.assert_allclose(volumes, expected, rtol=1e-9)
