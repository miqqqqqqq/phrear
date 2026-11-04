"""CLI command params."""

from __future__ import annotations

import io
import json

import pytest

from phrear import cli
from phrear.project import Project, gpkg

from .conftest import AddParam


def test_params_text_table(valid_site: Project) -> None:
    out = io.StringIO()
    code = cli.main(["params", str(valid_site.root)], text_stdout=out, stdout=io.BytesIO())
    lines = out.getvalue().splitlines()
    assert code == 0
    assert lines[0].split() == [
        "Unità", "Parametro", "Valore", "Unità", "di", "misura", "Valore", "interno", "Origine"
    ]  # fmt: skip
    assert any(
        "1 (copertura)" in line and "0.0001" in line and "8.64 m/d" in line for line in lines
    )
    assert any("K verticale (da Kv/Kh)" in line and "0.864 m/d" in line for line in lines)
    assert any("Resa specifica" in line and "15" in line and "%" in line for line in lines)


def test_params_text_in_english(valid_site: Project) -> None:
    out = io.StringIO()
    cli.main(["--lang", "en", "params", str(valid_site.root)], text_stdout=out, stdout=io.BytesIO())
    assert out.getvalue().startswith("Unit ")


def test_params_json_error(valid_site: Project, add_param: AddParam) -> None:
    fid = add_param(2, "anisotropy", 0.1, "")
    stdout = io.BytesIO()
    code = cli.main(["--json", "params", str(valid_site.root)], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 1
    assert events[-1]["event"] == "command_failed"
    error = events[-1]["error"]
    assert error["code"] == "params.kv_and_anisotropy"
    ref = {k: error["ref"][k] for k in ("kind", "layer", "fid", "field")}
    assert ref == {"kind": "field", "layer": "param_values", "fid": fid, "field": "value"}


def test_params_json_result_and_warning(valid_site: Project) -> None:
    with gpkg.connect(valid_site.gpkg_path) as conn:
        conn.execute('UPDATE "param_values" SET value = 80 WHERE param = ?', ("kv",))
    stdout = io.BytesIO()
    code = cli.main(["--json", "params", str(valid_site.root)], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 0
    assert [e["event"] for e in events] == [
        "command_started",
        "warning",
        "result",
        "command_completed",
    ]
    assert events[1]["problem"]["code"] == "params.kv_above_kh"
    units = events[2]["data"]["units"]
    assert [u["position"] for u in units] == [1, 2]
    assert units[0]["kv_md"] == pytest.approx(0.864)
    kh = next(v for v in units[0]["values"] if v["param"] == "kh")
    assert kh["unit"] == "m/s" and kh["internal_unit"] == "m/d"
    assert kh["internal_value"] == pytest.approx(8.64)


def test_params_with_a_zone_and_the_export(valid_site: Project) -> None:
    import pyogrio

    from phrear.grid.model_grid import build_model_grid

    from .test_cells import add_zone, strip

    grid = build_model_grid(valid_site)
    zone = add_zone(valid_site, 2, strip(grid, 0.0, 550.0), {"kh": (432.0, "m/d")}, name="Lente")
    out = io.StringIO()
    code = cli.main(
        ["params", str(valid_site.root), "--export"], text_stdout=out, stdout=io.BytesIO()
    )
    assert code == 0
    assert any("zona «Lente»" in line and "432 m/d" in line for line in out.getvalue().splitlines())
    stdout = io.BytesIO()
    cli.main(["--json", "params", str(valid_site.root), "--export"], stdout=stdout)
    data = next(json.loads(x) for x in stdout.getvalue().splitlines() if b'"result"' in x)["data"]
    aquifer = data["units"][1]
    assert aquifer["zones"][0]["fid"] == zone and aquifer["zones"][0]["values"][0]["param"] == "kh"
    g = grid.geometry
    assert data["export_features"] == grid.nlay * g.nrow * g.ncol
    frame = pyogrio.read_dataframe(data["export"])
    row = g.nrow // 2 + 1
    cell = frame[(frame.layer == 3) & (frame.row == row) & (frame.col == 6)].iloc[0]
    assert cell["kh"] == pytest.approx((432.0 * 50.0) ** 0.5)
    assert cell["kh_ms"] == pytest.approx(cell["kh"] / 86400.0)
    assert (cell["origin_kh"], cell["zone_kh"], cell["share_kh"]) == ("zone", zone, 0.5)
    first = frame[(frame.layer == 1) & (frame.idomain > 0)]
    assert set(first.origin_kh) == {"uniform"} and set(first.origin_ne) == {"none"}
