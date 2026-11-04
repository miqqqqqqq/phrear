"""Runs and result layers in the plugin, from the output of ``phrear runs``."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from phrear import cli
from phrear.examples.alluvial import create_example
from phrear.modflow.manifest import read_manifest
from phrear.results.netcdf import HEAD_UPPER_NAME
from phrear_qgis.client.forms import rgba
from phrear_qgis.client.results import (
    cell_categories,
    default_heads,
    export_args,
    heads_group,
    mesh_uri,
    run_rows,
    runs_args,
)


def core(args: list[str]) -> dict[str, Any]:
    stdout = io.BytesIO()
    assert cli.main(["--json", *args], stdout=stdout) == 0
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    data: dict[str, Any] = next(e for e in events if e["event"] == "result")["data"]
    return data


@pytest.fixture(scope="module")
def example(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("results") / "esempio"
    create_example(root)
    return root


def test_arguments() -> None:
    root = Path("C:/p")
    assert runs_args(root) == ["runs", str(root)]
    assert export_args("grid", root) == ["grid", str(root), "--export"]
    assert export_args("bc", root) == ["bc", str(root), "--export"]


def test_rows_of_built_and_broken_runs(example: Path) -> None:
    assert cli.main(["--json", "build", str(example), "--run-id", "solo"], stdout=io.BytesIO()) == 0
    (example / "runs" / "rotto").mkdir()
    rows = {r.run_id: r for r in run_rows(core(runs_args(example)), "it")}
    assert rows["solo"].status == "built" and rows["solo"].status_label == "costruito, non eseguito"
    assert not rows["solo"].can_load and rows["solo"].same_project is True
    assert len(rows["solo"].created) == 16
    assert rows["rotto"].status == "incomplete" and not rows["rotto"].can_load
    assert read_manifest(example / "runs" / "solo")["run"]["status"] == "built"


@pytest.mark.engine
def test_completed_run_and_default_heads(example: Path) -> None:
    result = core(["run", str(example), "--run-id", "base"])
    assert default_heads(result) == HEAD_UPPER_NAME
    listing = core(runs_args(example))
    assert default_heads(listing) == HEAD_UPPER_NAME
    base = next(r for r in run_rows(listing, "en") if r.run_id == "base")
    assert base.can_load and base.heads == result["heads"] and base.status_label == "completed"
    assert base.duration_s is not None and base.budget_pct is not None


def test_heads_group() -> None:
    names = ["Bottom of layer 1", "Head in layer 1", HEAD_UPPER_NAME, "Top of the model"]
    temporal = [False, True, True, False]
    assert heads_group(names, temporal, HEAD_UPPER_NAME) == 2
    assert heads_group(names, temporal, "") == 1
    assert heads_group(names, [False] * 4, "missing") == 0
    assert default_heads(None) == ""


def test_cell_categories_take_the_colour_of_their_layer(schema: dict[str, Any]) -> None:
    categories = cell_categories(schema, "it", ["recharge_zones", "wells", "wells", "unknown"])
    assert [c.value for c in categories] == ["wells", "recharge_zones", "unknown"]
    wells = next(t for t in schema["project"]["tables"] if t["name"] == "wells")
    assert categories[0].label == wells["label"]["it"]
    assert categories[0].outline == rgba(wells["style"]["color"])
    assert categories[2].label == "unknown" and categories[2].fill.startswith("128,128,128")


def test_heads_are_opened_with_the_ugrid_driver() -> None:
    assert mesh_uri("C:\\p\\runs\\base\\heads.nc") == 'Ugrid:"C:/p/runs/base/heads.nc"'
    assert mesh_uri(Path("/p/runs/base/heads.nc")) == 'Ugrid:"/p/runs/base/heads.nc"'
