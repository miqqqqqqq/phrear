"""Runs with MODFLOW 6: the model reproduces the boundaries exactly."""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta

import flopy
import numpy as np
import pytest

from phrear import cli
from phrear.checks.inspection import inspect_project
from phrear.modflow.manifest import read_manifest
from phrear.modflow.pipeline import build_run, execute, outcome_error, step_ends
from phrear.project import Project, gpkg

from ..boundaries.conftest import add_series, add_station, add_well, center

pytestmark = pytest.mark.engine
LINES = "fixed_head_lines"


@pytest.fixture
def varying_site(model_site: Project) -> Project:
    """The model site with series at both ends of the line and a well driven by a series."""
    add_series(model_site, "HS", "length", "m",
               [(datetime(2020, 1, 1), 30.0), (datetime(2020, 6, 1), 32.0)])  # fmt: skip
    add_series(model_site, "HN", "length", "m",
               [(datetime(2020, 1, 1), 36.0), (datetime(2020, 9, 1), 34.0)])  # fmt: skip
    with gpkg.connect(model_site.gpkg_path) as conn:
        conn.execute('UPDATE "line_stations" SET value = NULL, series_id = ?', ("HS",))
        conn.execute('UPDATE "wells" SET screen_top = 38.0')
    add_station(model_site, LINES, 1, 680550.0, 4851850.0, series_id="HN")
    add_series(model_site, "Q", "discharge", "l/s", [(datetime(2020, 4, 1), 5.0)])
    add_well(model_site, *center(7, 14), rate=None, series_id="Q", screen_top=38.0)
    return model_site


def test_run_reproduces_heads_rates_and_recharge(varying_site: Project) -> None:
    ins = inspect_project(varying_site)
    assert ins.ok, [p.code for p in ins.errors]
    run = build_run(ins, "r1")
    outcome = execute(run)
    assert outcome_error(run, outcome) is None and outcome.success
    assert abs(outcome.max_discrepancy[1]) < 1e-2  # type: ignore[index]

    calendar = run.calendar
    heads = flopy.utils.HeadFile(str(run.folder / "gwf.hds"))
    budget = flopy.utils.CellBudgetFile(str(run.folder / "gwf.cbc"), precision="double")
    # step ends as computed by MF6, checked against the calendar
    keys = [(kper + 1, kstp + 1) for kstp, kper in heads.get_kstpkper()]
    ends = dict(zip(keys, heads.get_times(), strict=True))
    planned = step_ends(calendar)
    assert ends == pytest.approx(planned, rel=1e-9)

    def moment(t: float) -> datetime:
        return calendar.start + timedelta(days=t - calendar.offset_d)

    # fixed heads: steady value, then the exact mean of the cell series over each step
    assert ins.boundaries is not None
    chd = next(p for p in ins.boundaries.packages if p.package == "chd")
    for i, (period, step) in enumerate(keys):
        h = heads.get_data(kstpkper=(step - 1, period - 1))
        start = 0.0 if i == 0 else ends[keys[i - 1]]
        for a in chd.assignments:
            f = a.forcing
            if period == 1:
                expected = f.steady
            elif f.series is None:
                expected = f.constant
            else:
                expected = f.series.mean_over(moment(start), moment(ends[(period, step)]))
            assert h[a.cell] == pytest.approx(expected, abs=1e-9)

    # wells: shares of the rate per layer; the series well starts on 2020-04-01
    names = [n.strip() for n in budget.get_unique_record_names(decode=True)]
    assert "WEL" in names and "RCH" in names
    for period, step in keys:
        wel = budget.get_data(text="WEL", kstpkper=(step - 1, period - 1))[0]
        q: dict[int, float] = {}
        for node, rate in zip(wel["node"], wel["q"], strict=True):
            col = (node - 1) % 20
            q[col] = q.get(col, 0.0) + rate
        assert q[10] == pytest.approx(-5.0 * 86.4, rel=1e-9)
        if moment(ends[(period, step)]) > datetime(2020, 4, 1):
            assert q[14] == pytest.approx(-5.0 * 86.4, rel=1e-9)
        else:
            assert 14 not in q
        rch = budget.get_data(text="RCH", kstpkper=(step - 1, period - 1))[0]
        assert rch["q"].sum() == pytest.approx(0.2 / 365.25 * 300 * 100.0**2, rel=1e-9)
    assert read_manifest(run.folder)["run"]["status"] == "completed"


def test_run_command_events(model_site: Project) -> None:
    stdout = io.BytesIO()
    code = cli.main(["--json", "run", str(model_site.root), "--run-id", "r2"], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    kinds = [e["event"] for e in events]
    assert code == 0
    assert kinds[:3] == ["command_started", "warning", "run_started"]
    assert kinds[-3:] == ["run_completed", "result", "command_completed"]
    progress = [e for e in events if e["event"] == "progress"]
    assert progress and progress[-1]["fraction"] == pytest.approx(1.0)
    data = events[-2]["data"]
    assert data["run_id"] == "r2" and data["steps"] == len(progress)


def test_input_rejected_by_mf6_is_reported(model_site: Project) -> None:
    run = build_run(inspect_project(model_site), "r3")
    dis = run.folder / "gwf.dis"
    dis.write_text(dis.read_text(encoding="utf-8").replace("NLAY", "NLAYERS"), encoding="utf-8")
    outcome = execute(run)
    error = outcome_error(run, outcome)
    assert error is not None and error.code == "run.engine_error"
    manifest = read_manifest(run.folder)
    assert manifest["run"]["status"] == "failed"
    assert manifest["run"]["error"]["code"] == "run.engine_error"


def test_heads_are_not_all_equal(model_site: Project) -> None:
    run = build_run(inspect_project(model_site), "r4")
    assert execute(run).success
    h = flopy.utils.HeadFile(str(run.folder / "gwf.hds")).get_data()
    active = h[1][h[1] < 1e29]
    assert np.ptp(active) > 0.01  # the well and the recharge move the heads away from 30 m
