"""Listing the runs of a project (``phrear runs``) and the state of a run."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from phrear import cli
from phrear.checks.inspection import inspect_project
from phrear.errors import ResultsError
from phrear.grid.export import export_grid
from phrear.grid.model_grid import build_model_grid
from phrear.modflow import pipeline, runner
from phrear.modflow.manifest import read_manifest
from phrear.modflow.pipeline import build_run
from phrear.project import Project, gpkg
from phrear.results.runs import STATUS_LABELS, list_runs


def _runs(root: Path) -> dict[str, Any]:
    stdout = io.BytesIO()
    assert cli.main(["--json", "runs", str(root)], stdout=stdout) == 0
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    data: dict[str, Any] = next(e for e in events if e["event"] == "result")["data"]
    return data


def test_no_runs(model_site: Project) -> None:
    data = _runs(model_site.root)
    assert data["runs"] == [] and len(data["content_hash"]) == 64


def test_built_and_incomplete_runs(model_site: Project) -> None:
    build_run(inspect_project(model_site), "solo_build")
    (model_site.root / "runs" / "rotto").mkdir()
    runs = {r["run_id"]: r for r in list_runs(model_site)["runs"]}
    built = runs["solo_build"]
    assert built["status"] == "built" and built["same_project"] is True
    assert built["status_label"] == {"it": "costruito, non eseguito", "en": "built, not run"}
    assert built["products"] == {} and built["engine_version"]
    broken = runs["rotto"]
    assert broken["status"] == "incomplete" and broken["status_label"]["it"] == "incompleto"
    assert set(STATUS_LABELS) == {"built", "running", "completed", "failed", "incomplete"}


@pytest.mark.engine
def test_a_run_is_running_while_mf6_runs(
    model_site: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = build_run(inspect_project(model_site), "r")
    seen: dict[str, Any] = {}
    real = runner.run_mf6

    def spy(folder: Path, *args: Any, **kwargs: Any) -> Any:
        seen.update(read_manifest(folder)["run"])
        return real(folder, *args, **kwargs)

    monkeypatch.setattr(pipeline, "run_mf6", spy)
    pipeline.execute(run)
    assert seen["status"] == "running" and seen["started"]
    assert read_manifest(run.folder)["run"]["status"] == "completed"


@pytest.mark.engine
def test_completed_run_with_heads_and_changed_project(model_site: Project) -> None:
    assert cli.main(["--json", "run", str(model_site.root), "--run-id", "base"],
                    stdout=io.BytesIO()) == 0  # fmt: skip
    run = _runs(model_site.root)["runs"][0]
    assert run["run_id"] == "base" and run["status"] == "completed"
    assert Path(run["products"]["heads"]).name == "heads.nc"
    assert run["same_project"] is True and run["duration_s"] > 0
    with gpkg.connect(model_site.gpkg_path) as conn:
        conn.execute("UPDATE wells SET rate = rate * 2")
    assert _runs(model_site.root)["runs"][0]["same_project"] is False
    out = io.StringIO()
    assert cli.main(["runs", str(model_site.root)], text_stdout=out, stdout=io.BytesIO()) == 0
    assert "base" in out.getvalue() and "progetto modificato dopo il run" in out.getvalue()


def test_runs_are_listed_newest_first(model_site: Project) -> None:
    build_run(inspect_project(model_site), "a")
    second = build_run(inspect_project(model_site), "b")
    manifest = read_manifest(second.folder)
    manifest["created"] = "2999-01-01T00:00:00+01:00"
    (second.folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert [r["run_id"] for r in list_runs(model_site)["runs"]] == ["b", "a"]


def test_export_of_an_open_file_is_reported(
    model_site: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "grid.gpkg"
    grid = build_model_grid(model_site)
    export_grid(grid, target, 7791)

    def locked(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(32, "in use")

    monkeypatch.setattr(Path, "unlink", locked)
    with pytest.raises(ResultsError) as error:
        export_grid(grid, target, 7791)
    assert error.value.code == "results.file_locked"
