"""Verification cases with MODFLOW 6, within the tolerances of docs/SPEC.md, section 20."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from phrear import cli
from phrear.verification.cases import CASES
from phrear.verification.runner import run_case

pytestmark = pytest.mark.engine


@pytest.mark.parametrize("name", list(CASES))
def test_case_within_tolerance(name: str, tmp_path: Path) -> None:
    result = run_case(CASES[name], tmp_path)
    assert result.points > 0
    assert result.passed, f"{name}: {result.measure:.4g} > {result.case.tolerance}"


def test_well_cases_compare_at_least_three_cells_from_the_well(tmp_path: Path) -> None:
    result = run_case(CASES["thiem"], tmp_path)
    assert result.comparison.distance.min() >= 3 * 10.0


def test_verify_command_writes_the_report(tmp_path: Path) -> None:
    output = tmp_path / "report"
    stdout = io.BytesIO()
    code = cli.main(["--json", "verify", "--case", "flow_1d", "--output", str(output), "--keep"],
                    stdout=stdout)  # fmt: skip
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 0
    assert [e["event"] for e in events] == [
        "command_started", "progress", "result", "command_completed"
    ]  # fmt: skip
    data = events[2]["data"]
    assert [c["name"] for c in data["cases"]] == ["flow_1d"] and data["cases"][0]["passed"]
    assert {p.name for p in output.iterdir()} == {"report.md", "results.json", "flow_1d.png",
                                                  "cases"}  # fmt: skip
    assert "| Flusso monodimensionale con ricarica |" in (output / "report.md").read_text("utf-8")


def test_verify_refuses_a_used_folder_and_unknown_cases(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    err = io.StringIO()
    code = cli.main(["verify", "--output", str(tmp_path)], stderr=err, text_stdout=io.StringIO(),
                    stdout=io.BytesIO())  # fmt: skip
    assert code == 1 and "[verify.output_exists]" in err.getvalue()
    err = io.StringIO()
    code = cli.main(["verify", "--case", "boh", "--output", str(tmp_path / "n")], stderr=err,
                    text_stdout=io.StringIO(), stdout=io.BytesIO())  # fmt: skip
    assert code == 1 and "[verify.unknown_case]" in err.getvalue()
