"""Check and run in the plugin: problems, stages and log entries from real core events."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from phrear import cli
from phrear.examples.alluvial import create_example
from phrear.project import gpkg
from phrear_qgis.client.events import EventStream, collect
from phrear_qgis.client.runs import (
    Labels,
    check_args,
    counts,
    local_time,
    log_entry,
    problem_row,
    problem_rows,
    progress,
    run_args,
    run_summary,
    stage_rows,
)


def core(args: list[str]) -> tuple[int, list[dict[str, Any]]]:
    stdout = io.BytesIO()
    code = cli.main(["--json", *args], stdout=stdout)
    return code, [json.loads(line) for line in stdout.getvalue().splitlines()]


@pytest.fixture(scope="module")
def broken(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The example with a negative K: one error in the parameters."""
    root = tmp_path_factory.mktemp("broken") / "esempio"
    create_example(root)
    with gpkg.connect(root / "model.gpkg") as conn:
        conn.execute("UPDATE param_values SET value = -1 WHERE param = 'kh' AND object_id = 2")
    return root


def test_arguments() -> None:
    root = Path("C:/p")
    assert check_args(root) == ["check", str(root)]
    assert run_args(root) == ["run", str(root)]
    assert run_args(root, "  ") == ["run", str(root)]
    assert run_args(root, " base ") == ["run", str(root), "--run-id", "base"]


def test_problems_of_a_failed_check(broken: Path, schema: dict[str, Any]) -> None:
    code, events = core(["check", str(broken)])
    assert code == 1
    stream = EventStream()
    outcome = collect("check", events, code, stream)
    rows = problem_rows(outcome.errors, outcome.warnings, outcome.failure, "it", schema)
    assert counts(rows) == (len(outcome.errors), len(outcome.warnings))
    first = rows[0]
    assert first.severity == "error" and first.code == "params.not_positive"
    assert (first.table, first.field) == ("param_values", "value") and first.fid is not None
    table = next(t for t in schema["project"]["tables"] if t["name"] == "param_values")
    assert first.table_label == table["label"]["it"]
    assert first.field_label == "Valore"
    assert first.locatable and first.hint
    # The summary failure of check is not repeated as a row.
    assert all(r.code != "check.failed" for r in rows)
    severities = [r.severity for r in rows]
    assert severities == sorted(severities, key=lambda s: s != "error")


def test_stages_of_a_failed_check(broken: Path) -> None:
    _, events = core(["--lang", "it", "check", str(broken)])
    result = next(e for e in events if e["event"] == "result")["data"]
    stages = {s.label: s for s in stage_rows(result, "it")}
    assert stages["Parametri"].status == "errors" and stages["Parametri"].errors == 1
    assert stages["Condizioni al contorno"].status == "skipped"
    assert stages["Condizioni al contorno"].skipped_for == ("Parametri",)
    assert stage_rows(result, "en")[0].label == "Time"


def test_failure_rows_when_the_run_cannot_start() -> None:
    failure = {
        "code": "run.exists",
        "message": {"it": "Il run base esiste già.", "en": "Run base already exists."},
        "hint": {"it": "Scegli un altro nome.", "en": "Choose another name."},
        "ref": None,
    }
    rows = problem_rows([], [], failure, "it")
    assert len(rows) == 1 and rows[0].message == "Il run base esiste già." and not rows[0].locatable
    assert problem_rows([], [], {"code": "check.failed", "message": {}}, "it") == []


def test_cells_are_shown_from_one() -> None:
    row = problem_row({"code": "x", "ref": {"kind": "cell", "cell": [0, 4, 9]}}, "warning", "en")
    assert row.cell == (1, 5, 10) and not row.locatable


def test_labels_fall_back_to_names() -> None:
    labels = Labels(None, "it")
    assert labels.table("wells") == "wells" and labels.field("wells", "rate") == "rate"
    assert labels.field("wells", None) == ""


def test_log_and_progress() -> None:
    started = {"event": "command_started", "command": "run", "time": "2026-11-04T11:30:54.4Z"}
    entry = log_entry(started, "it")
    assert (
        entry is not None and entry.key == "command_started" and entry.values == {"command": "run"}
    )
    assert len(entry.time) == 8 and entry.time.count(":") == 2
    warning = {
        "event": "warning",
        "time": "2026-11-04T11:30:54Z",
        "problem": {"code": "geometry.thin_unit", "message": {"it": "Sottile", "en": "Thin"}},
    }
    entry = log_entry(warning, "en")
    assert entry is not None and entry.level == "warning" and entry.values["message"] == "Thin"
    failed = {"event": "run_failed", "run_id": "base", "error": {"message": {"it": "Divergenza"}}}
    entry = log_entry(failed, "it")
    assert entry is not None and entry.level == "error" and entry.values["message"] == "Divergenza"
    step = {"event": "progress", "fraction": 0.5, "message": {"it": "Periodo 1 di 3, passo 1"}}
    assert log_entry(step, "it") is None
    assert progress(step, "it") == (0.5, "Periodo 1 di 3, passo 1")
    assert progress({"event": "progress", "stage": "run"}, "it") == (None, "")
    assert progress(started, "it") is None
    assert local_time("not a time") == "" and local_time(None) == ""


def test_run_summary() -> None:
    result = {
        "run_id": "base",
        "folder": "C:/p/runs/base",
        "heads": "C:/p/runs/base/heads.nc",
        "duration_s": 0.8,
        "steps": 50,
        "max_budget_discrepancy": {"period": 2, "step": 3, "pct": 1e-6},
    }
    summary = run_summary(result)
    assert summary is not None and summary.run_id == "base" and summary.steps == 50
    assert (summary.worst_budget_pct, summary.worst_period, summary.worst_step) == (1e-6, 2, 3)
    assert run_summary({**result, "max_budget_discrepancy": None}) is not None
    assert run_summary(None) is None
