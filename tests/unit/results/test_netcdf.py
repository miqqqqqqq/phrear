"""Export of the heads of a run as NetCDF UGRID."""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import flopy
import numpy as np
import pytest
import xarray as xr
import xugrid as xu

from phrear import cli
from phrear.checks.inspection import inspect_project
from phrear.errors import ResultsError
from phrear.grid.model_grid import build_model_grid
from phrear.modflow.manifest import read_manifest
from phrear.modflow.pipeline import build_run, execute
from phrear.project import Project
from phrear.results.netcdf import write_heads
from phrear.results.runs import completed_run

pytestmark = pytest.mark.engine


def _run(project: Project, run_id: str) -> Path:
    run = build_run(inspect_project(project), run_id)
    assert execute(run).success
    return run.folder


def _shoelace(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return 0.5 * np.sum(x * np.roll(y, -1, axis=1) - np.roll(x, -1, axis=1) * y, axis=1)


def test_heads_match_the_head_file(model_site: Project) -> None:
    folder = _run(model_site, "r1")
    path = write_heads(folder, read_manifest(folder), datetime(2026, 1, 1))
    ds = xr.open_dataset(path, decode_times=False)
    grid = xu.open_dataset(path).ugrid.grid
    assert grid.n_face == 15 * 20 and grid.n_node == 16 * 21
    assert ds.attrs["run_id"] == "r1" and ds.attrs["Conventions"] == "CF-1.8 UGRID-1.0"
    assert ds["time"].attrs["units"] == "days since 2020-01-01 00:00:00"
    assert float(ds["time"][0]) == 0.0  # the initial steady state, at the start date
    assert ds["projected_coordinate_system"].attrs["epsg"] == 7791

    head_file = flopy.utils.HeadFile(str(folder / "gwf.hds"))
    raw = head_file.get_alldata().reshape(len(ds["time"]), 3, 300)
    bottom = np.stack([ds[f"bottom_l{k}"].values for k in (1, 2, 3)])
    idomain = np.stack([ds[f"idomain_l{k}"].values for k in (1, 2, 3)])
    for k in (1, 2, 3):
        exported = ds[f"head_l{k}"].values
        wet = (idomain[k - 1] > 0)[None] & ((raw[:, k - 1] >= bottom[k - 1]) | (k > 1))
        assert np.allclose(exported[wet], raw[:, k - 1][wet], rtol=0, atol=1e-12)
        assert np.isnan(exported[~wet]).all()
    # layer 1 is pass-through east of the pinch-out and dry in the west (heads ~30 m < 40 m)
    assert np.isnan(ds["head_l1"].values).all()
    assert np.allclose(ds["head_upper"].values, ds["head_l2"].values, equal_nan=True)


@pytest.mark.parametrize("angrot", [0.0, 30.0])
def test_mesh_geometry(model_site: Project, angrot: float) -> None:
    model_site.config.grid.rotation_deg = angrot
    model_site.save()
    folder = _run(Project.open(model_site.root), "r1")
    ds = xr.open_dataset(write_heads(folder, read_manifest(folder), datetime(2026, 1, 1)))
    faces = ds["mesh2d_face_nodes"].values.astype(int)
    x, y = ds["mesh2d_node_x"].values[faces], ds["mesh2d_node_y"].values[faces]
    assert np.allclose(_shoelace(x, y), 100.0**2)  # counter-clockwise, 100 m cells
    cx, cy = build_model_grid(Project.open(model_site.root)).geometry.centers()
    assert np.allclose(ds["mesh2d_face_x"].values, cx.ravel())
    assert np.allclose(ds["mesh2d_face_y"].values, cy.ravel())
    assert np.allclose(x.mean(axis=1), cx.ravel()) and np.allclose(y.mean(axis=1), cy.ravel())


def test_run_exports_and_export_command(model_site: Project) -> None:
    stdout = io.BytesIO()
    assert cli.main(["--json", "run", str(model_site.root), "--run-id", "a"], stdout=stdout) == 0
    data = json.loads(stdout.getvalue().splitlines()[-2])["data"]
    assert Path(data["heads"]) == model_site.root / "runs" / "a" / "heads.nc"
    _run(model_site, "b")
    out = io.StringIO()
    assert cli.main(["export", str(model_site.root)], text_stdout=out, stdout=io.BytesIO()) == 0
    assert "run b" in out.getvalue()  # the latest completed run
    assert (model_site.root / "runs" / "b" / "heads.nc").is_file()


def test_run_lookup_errors(model_site: Project) -> None:
    with pytest.raises(ResultsError) as info:
        completed_run(model_site, None)
    assert info.value.code == "results.no_run"
    with pytest.raises(ResultsError) as info:
        completed_run(model_site, "nessuno")
    assert info.value.code == "results.run_not_found"
    build_run(inspect_project(model_site), "solo_build")
    with pytest.raises(ResultsError) as info:
        completed_run(model_site, "solo_build")
    assert info.value.code == "results.not_completed"


def test_locked_file(model_site: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _run(model_site, "r1")

    def locked(self: Path, target: Path) -> Path:
        raise PermissionError("in use")

    monkeypatch.setattr(Path, "replace", locked)
    with pytest.raises(ResultsError) as info:
        write_heads(folder, read_manifest(folder), datetime(2026, 1, 1))
    assert info.value.code == "results.file_locked"


def test_exporter_registry() -> None:
    from phrear.errors import Localized
    from phrear.results.exporters import EXPORTERS, Exporter, register

    assert list(EXPORTERS) == ["heads"] and EXPORTERS["heads"].filename == "heads.nc"
    clash = Exporter("heads", Localized("x", "x"), "x", "x.nc", EXPORTERS["heads"].write)
    with pytest.raises(ValueError, match="already registered"):
        register(clash)
