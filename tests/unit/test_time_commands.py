"""CLI command calendar."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from phrear import cli
from phrear.project import Project

from .timeline.conftest import add_series, add_well


def _project(tmp_path: Path) -> Project:
    root = tmp_path / "sito"
    cli.main(
        ["new", str(root), "--start", "2020-01-01", "--end", "2021-01-01"],
        text_stdout=io.StringIO(),
        stdout=io.BytesIO(),
    )
    project = Project.open(root)
    add_series(project, "Q1", [("2019-01-01", 10.0), ("2020-06-01", 20.0)], unit="l/s")
    add_well(project, "P1", "Q1")
    add_series(project, "Q2", [("2020-04-01", 5.0)], unit="l/s")
    add_well(project, "P2", "Q2")
    return project


def test_calendar_table_in_italian(tmp_path: Path) -> None:
    project = _project(tmp_path)
    out = io.StringIO()
    code = cli.main(["calendar", str(project.root)], text_stdout=out, stdout=io.BytesIO())
    text = out.getvalue()
    assert code == 0
    assert text.splitlines()[0].split()[:3] == ["Periodo", "Tipo", "Inizio"]
    assert "series:Q2" in text
    assert "staz." in text


def test_calendar_json_result(tmp_path: Path) -> None:
    project = _project(tmp_path)
    stdout = io.BytesIO()
    code = cli.main(["--json", "calendar", str(project.root)], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 0
    data = events[1]["data"]
    assert [p["kind"] for p in data["periods"]] == ["steady", "transient", "transient"]
    assert data["series"]["Q1"]["steady_value"] == pytest.approx(864.0)  # 10 l/s
    assert data["series"]["Q2"]["steady_value"] is None
    assert data["series"]["Q2"]["activation"] == "2020-04-01T00:00:00"


def test_calendar_reports_uncovered_series(tmp_path: Path) -> None:
    project = _project(tmp_path)
    add_series(
        project, "H", [("2019-01-01", 10.0), ("2020-06-01", 12.0)], quantity="length", unit="m",
        interpolation="linear",
    )  # fmt: skip
    add_well(project, "P3", "H")
    stdout = io.BytesIO()
    code = cli.main(["--json", "calendar", str(project.root)], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == cli.EXIT_INPUT_ERROR
    assert events[-1]["error"]["code"] == "series.not_covered"
