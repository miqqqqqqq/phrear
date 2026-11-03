"""CLI command bc."""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pyogrio
import shapely

from phrear import cli
from phrear.project import Project

from ..sites import X0, Y0
from .conftest import add_line, add_series, add_station, add_well, add_zone, center


def _site(project: Project) -> Project:
    add_series(project, "Q", "discharge", "l/s", [(datetime(2020, 4, 1), 5.0)])
    add_well(project, *center(7, 4))
    add_well(project, *center(7, 14), rate=None, series_id="Q")
    fid = add_line(project, [(X0 + 550.0, Y0 + 650.0), (X0 + 550.0, Y0 + 1850.0)])
    add_station(project, "fixed_head_lines", fid, X0 + 550.0, Y0 + 650.0, value=30.0)
    add_zone(project, shapely.box(X0, Y0, X0 + 3000, Y0 + 3000))
    return project


def test_bc_text_table(valid_site: Project) -> None:
    out = io.StringIO()
    code = cli.main(["bc", str(_site(valid_site).root)], text_stdout=out, stdout=io.BytesIO())
    lines = out.getvalue().splitlines()
    assert code == 0
    assert lines[0].split()[:3] == ["Pacchetto", "Tipo", "Feature"]
    wel = next(line for line in lines if line.startswith("WEL"))
    assert wel.split()[1:6] == ["Pozzi", "2", "5", "5", "1"]  # 3 + 2 screened layers
    assert lines[2].startswith("CHD") and lines[3].startswith("RCH")


def test_bc_json_and_export(valid_site: Project) -> None:
    stdout = io.BytesIO()
    root = _site(valid_site).root
    code = cli.main(["--json", "bc", str(root), "--export"], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 0
    assert [e["event"] for e in events] == ["command_started", "result", "command_completed"]
    data = events[1]["data"]
    wel = data["packages"][0]
    # steady, 2020-01-01, 2020-04-01: the series well starts with the third period
    assert wel["entries_per_period"] == [3, 3, 5]
    cells = pyogrio.read_dataframe(Path(data["export"]), layer="cells")
    assert len(cells) == sum(p["entries"] for p in data["packages"])
    assert set(cells["package"]) == {"wel", "chd", "rch"}


def test_bc_export_without_boundaries(valid_site: Project) -> None:
    stdout = io.BytesIO()
    code = cli.main(["--json", "bc", str(valid_site.root), "--export"], stdout=stdout)
    data = json.loads(stdout.getvalue().splitlines()[1])["data"]
    assert code == 0
    assert len(pyogrio.read_dataframe(Path(data["export"]), layer="cells")) == 0
