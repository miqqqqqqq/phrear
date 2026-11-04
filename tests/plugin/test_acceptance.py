"""Acceptance of M1b: the example run from the plugin equals the run from the CLI.

The plugin computes nothing: it runs the core with the command it builds
(``core_command``), through pixi, in the environment it cleans of the QGIS
variables. This test takes exactly that path for one run and the command line
for the other, on the example project, and compares the results exactly.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from compare_runs import compare_runs
from phrear import cli
from phrear.examples.alluvial import create_example
from phrear.project import gpkg
from phrear_qgis.client.command import CoreLocation, clean_environment, core_command, find_pixi
from phrear_qgis.client.events import EventStream, collect
from phrear_qgis.client.runs import run_args, run_summary

from .conftest import REPO


def plugin_run(root: Path, run_id: str) -> Path:
    pixi = find_pixi(os.environ, Path.home())
    if pixi is None:
        pytest.skip("pixi not on PATH")
    environment = clean_environment({**os.environ, "PYTHONPATH": "/broken", "GDAL_DATA": "/x"})
    completed = subprocess.run(
        core_command(CoreLocation(REPO, pixi), run_args(root, run_id), "it"),
        capture_output=True,
        env=environment,
        cwd=REPO,
        check=False,
        timeout=600,
    )
    stream = EventStream()
    events = stream.feed(completed.stdout) + stream.finish()
    outcome = collect("run", events, completed.returncode, stream, completed.stderr.decode())
    assert outcome.ok, outcome.output
    summary = run_summary(outcome.result)
    assert summary is not None and summary.run_id == run_id
    return Path(summary.folder)


@pytest.mark.engine
def test_plugin_and_cli_give_identical_results(tmp_path: Path) -> None:
    root = tmp_path / "esempio"
    create_example(root)
    assert cli.main(["run", str(root), "--run-id", "cli"], stdout=io.BytesIO()) == 0
    from_plugin = plugin_run(root, "plugin")
    result = compare_runs(root / "runs" / "cli", from_plugin)
    assert result.identical, result.differences
    assert result.values > 0 and "head_upper" in result.variables
    assert {"gwf.wel", "gwf.chd", "gwf.rch", "mfsim.tdis"} <= set(result.input_files)

    # A different project gives different results: the comparison is not blind.
    other = tmp_path / "altro"
    shutil.copytree(root, other, ignore=shutil.ignore_patterns("runs"))
    with gpkg.connect(other / "model.gpkg") as conn:
        conn.execute("UPDATE wells SET rate = 30 WHERE rate = 15")
    assert cli.main(["run", str(other), "--run-id", "cli"], stdout=io.BytesIO()) == 0
    changed = compare_runs(root / "runs" / "cli", other / "runs" / "cli")
    assert not changed.identical
    assert any("head_upper" in d for d in changed.differences)
    assert "gwf.wel" in " ".join(changed.differences)
