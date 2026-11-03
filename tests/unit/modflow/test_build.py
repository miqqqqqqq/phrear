"""Build of a run: MF6 files, manifest, run folders, solver settings."""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pytest

from phrear import cli
from phrear.boundaries.base import Record
from phrear.checks.inspection import inspect_project
from phrear.errors import RunError
from phrear.modflow.manifest import read_manifest
from phrear.modflow.pipeline import build_run, step_ends, step_fractions
from phrear.modflow.runner import error_report
from phrear.modflow.simulation import _period_data, ims_options
from phrear.project import Project

from ..boundaries.conftest import add_series, add_well, center
from ..sites import X0, Y0


def test_build_writes_the_simulation_and_its_manifest(model_site: Project) -> None:
    ins = inspect_project(model_site)
    run = build_run(ins, "b1")
    assert run.folder == model_site.root / "runs" / "b1"
    assert {"mfsim.nam", "mfsim.tdis", "mfsim.ims", "gwf.dis", "gwf.ic", "gwf.npf", "gwf.sto",
            "gwf.wel", "gwf.chd", "gwf.rch", "gwf.oc"} <= set(run.simulation.files)  # fmt: skip
    assert (run.folder / "manifest.json").is_file()
    manifest = read_manifest(run.folder)
    assert manifest["run_id"] == "b1"
    assert manifest["run"] == {"status": "built"}
    assert manifest["project"]["hashes"] == model_site.content_hashes()
    assert manifest["model"]["entries"] == run.simulation.entries
    assert manifest["model"]["nlay"] == 3
    assert [w["code"] for w in manifest["warnings"]] == ["geometry.thin_unit"]
    assert manifest["settings"]["name"] == model_site.config.name


def test_series_go_to_time_series_files(model_site: Project) -> None:
    add_series(model_site, "Q", "discharge", "l/s", [(datetime(2020, 4, 1), 5.0)])
    add_well(model_site, *center(7, 14), rate=None, series_id="Q")
    run = build_run(inspect_project(model_site), "b1")
    assert "gwf.wel_001.ts" in run.simulation.files
    assert run.simulation.series == 1
    text = (run.folder / "gwf.wel").read_text(encoding="utf-8")
    assert "AUXMULTNAME  mult" in text and "BOUNDNAMES" in text
    assert text.count("BEGIN period") == 2  # steady, and the period where the series starts


def test_run_folders_are_never_reused(model_site: Project) -> None:
    ins = inspect_project(model_site)
    build_run(ins, "b1")
    with pytest.raises(RunError) as info:
        build_run(ins, "b1")
    assert info.value.code == "run.exists"
    with pytest.raises(RunError) as info:
        build_run(ins, "../fuori")
    assert info.value.code == "run.invalid_id"
    first, second = build_run(ins), build_run(ins)
    assert first.run_id != second.run_id


def test_build_stops_on_errors(model_site: Project) -> None:
    add_well(model_site, X0 + 100.0, Y0 + 100.0)
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["build", str(model_site.root)], text_stdout=out, stderr=err,
                    stdout=io.BytesIO())  # fmt: skip
    assert code == 1
    assert "Errore [bc.outside_active]" in out.getvalue()
    assert err.getvalue().startswith("Errore [check.failed]")
    assert list((model_site.root / "runs").iterdir()) == []


def test_build_command_json(model_site: Project) -> None:
    stdout = io.BytesIO()
    code = cli.main(["--json", "build", str(model_site.root), "--run-id", "b2"], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 0
    assert [e["event"] for e in events] == [
        "command_started", "warning", "result", "command_completed"
    ]  # fmt: skip
    assert Path(events[2]["data"]["folder"]).name == "b2"


def _rec(value: float | str) -> Record:
    return ((0, 0, 0), value, 1.0, "w")


def test_period_blocks_only_when_entries_change() -> None:
    records = [[], [_rec(1.0)], [_rec(1.0)], [_rec("s001")], [_rec("s001")]]
    assert list(_period_data(records, "wel")) == [1, 3]
    assert _period_data(records, "chd")[1] == [((0, 0, 0), 1.0, "w")]


def test_solver_presets(model_site: Project) -> None:
    config = model_site.config
    assert ims_options(config)["complexity"] == "moderate"
    assert ims_options(config)["linear_acceleration"] == "bicgstab"  # Newton on by default
    config.options.newton = False
    assert "linear_acceleration" not in ims_options(config)
    config.solver.preset = "robust"
    assert ims_options(config)["complexity"] == "complex"
    config.solver = config.solver.model_validate({"preset": "expert", "ims": {"outer_maximum": 7}})
    assert ims_options(config)["outer_maximum"] == 7


def test_step_times_follow_the_calendar(model_site: Project) -> None:
    calendar = inspect_project(model_site).timeline.calendar  # type: ignore[union-attr]
    ends = step_ends(calendar)
    total = sum(p.perlen_d for p in calendar.periods)
    assert max(ends.values()) == pytest.approx(total)
    assert step_fractions(calendar)[max(ends)] == pytest.approx(1.0)
    assert ends[(1, 1)] == pytest.approx(1.0)  # the steady period lasts one day


def test_error_report_of_the_listing() -> None:
    listing = """
ERROR REPORT:

  1. CHD BOUNDARY 1 HEAD (30.000000000000000) IS LESS THAN CELL BOTTOM
     (40.000000000000000) FOR CELL (1,1,1)

UNIT ERROR REPORT:

  1. ERROR OCCURRED WHILE READING FILE 'm.chd'
"""
    assert error_report(listing) == (
        "CHD BOUNDARY 1 HEAD (30.000000000000000) IS LESS THAN CELL BOTTOM "
        "(40.000000000000000) FOR CELL (1,1,1)",
    )


def test_missing_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import shutil
    import sys

    from phrear.modflow import engine

    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "prefix", str(tmp_path))
    with pytest.raises(RunError) as info:
        engine.mf6_executable()
    assert info.value.code == "run.engine_not_found"
