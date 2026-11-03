"""CLI command grid."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pyogrio

from phrear import cli


def _copy(template: Path, tmp_path: Path) -> Path:
    target = tmp_path / "site"
    shutil.copytree(template, target)
    return target


def test_grid_text_summary_and_warning(site_template: Path, tmp_path: Path) -> None:
    root = _copy(site_template, tmp_path)
    out = io.StringIO()
    code = cli.main(["grid", str(root)], text_stdout=out, stdout=io.BytesIO())
    text = out.getvalue()
    assert code == 0
    assert "Avviso [geometry.thin_unit]" in text
    assert "Griglia DIS: 3 layer × 15 righe × 20 colonne" in text


def test_grid_json_and_export(site_template: Path, tmp_path: Path) -> None:
    root = _copy(site_template, tmp_path)
    stdout = io.BytesIO()
    code = cli.main(["--json", "grid", str(root), "--export"], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 0
    assert [e["event"] for e in events] == [
        "command_started",
        "warning",
        "result",
        "command_completed",
    ]
    data = events[2]["data"]
    assert data["nlay"] == 3 and data["active_cells"] > 0
    assert (
        len(pyogrio.read_dataframe(Path(data["export"]), layer="cells"))
        == data["nrow"] * data["ncol"]
    )
