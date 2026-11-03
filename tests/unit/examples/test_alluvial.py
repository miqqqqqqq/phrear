"""The example project: valid, runnable, with stable results (regression)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import flopy
import numpy as np
import pytest

from phrear import cli
from phrear.checks.inspection import inspect_project
from phrear.examples.alluvial import create_example
from phrear.modflow.pipeline import build_run, execute, outcome_error

#: Heads of layers 1-3 at three cells (row, col), steady state and end of 2024, MF6 6.8.1.
REFERENCE = {
    "P1 acquedotto": ((18, 30), (43.6715, 43.4635, 43.5456), (43.8830, 43.7382, 43.8206)),
    "P2 irriguo": ((24, 42), (42.3432, 42.1551, 42.1541), (42.6774, 42.5760, 42.5754)),
    "centro": ((18, 18), (45.3170, 45.1170, 45.1160), (45.4309, 45.2675, 45.2667)),
}


@pytest.fixture(scope="module")
def example(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("example") / "esempio"
    create_example(root)
    return root


def test_example_is_valid(example: Path) -> None:
    from phrear.project import Project

    ins = inspect_project(Project.open(example))
    assert ins.ok
    assert [p.code for p in ins.warnings] == ["geometry.thin_unit"]
    assert ins.grid is not None and ins.grid.summary()["active_cells"] == 5808
    assert ins.boundaries is not None
    counts = {p.package: (p.n_features, len(p.assignments)) for p in ins.boundaries.packages}
    assert counts == {"wel": (2, 4), "chd": (2, 166), "rch": (2, 2060)}
    assert [p.start.month for p in ins.timeline.calendar.periods] == [1, 1, 4]  # type: ignore[union-attr]


@pytest.mark.engine
def test_example_results_are_stable(example: Path) -> None:
    from phrear.project import Project

    run = build_run(inspect_project(Project.open(example)), "regressione")
    outcome = execute(run)
    assert outcome_error(run, outcome) is None
    assert abs(outcome.max_discrepancy[1]) < 1e-2  # type: ignore[index]
    heads = flopy.utils.HeadFile(str(run.folder / "gwf.hds"))
    times = heads.get_times()
    first, last = heads.get_data(totim=times[0]), heads.get_data(totim=times[-1])
    for name, ((r, c), steady, final) in REFERENCE.items():
        assert first[:, r, c] == pytest.approx(np.array(steady), abs=1e-3), name
        assert last[:, r, c] == pytest.approx(np.array(final), abs=1e-3), name


def test_example_command(tmp_path: Path) -> None:
    stdout = io.BytesIO()
    code = cli.main(["--json", "example", str(tmp_path / "es")], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 0 and events[1]["data"]["name"] == "Esempio - piana alluvionale"
    err = io.StringIO()
    code = cli.main(["example", str(tmp_path / "es")], stderr=err, text_stdout=io.StringIO(),
                    stdout=io.BytesIO())  # fmt: skip
    assert code == 1 and "[project.exists]" in err.getvalue()
