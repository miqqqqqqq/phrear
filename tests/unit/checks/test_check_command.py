"""CLI command check."""

from __future__ import annotations

import io
import json

from phrear import cli
from phrear.project import Project

from ..boundaries.conftest import add_well, center
from ..sites import X0, Y0


def test_check_text_passes(model_site: Project) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["check", str(model_site.root)], text_stdout=out, stderr=err,
                    stdout=io.BytesIO())  # fmt: skip
    lines = out.getvalue().splitlines()
    assert code == 0
    assert lines[0].split() == ["Tempo", "ok"]
    assert lines[1].split() == ["Griglia", "ok,", "1", "avviso"]
    assert lines[5].startswith("Controlli del modello") and "(eseguiti 4 su 4)" in lines[5]
    assert lines[-1] == "Esito: nessun errore, 1 avviso."
    assert err.getvalue() == ""


def test_check_text_lists_every_error(model_site: Project) -> None:
    add_well(model_site, X0 + 100.0, Y0 + 100.0)
    add_well(model_site, *center(7, 4), screen_top=10.0, screen_bottom=45.0)
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["check", str(model_site.root)], text_stdout=out, stderr=err,
                    stdout=io.BytesIO())  # fmt: skip
    text = out.getvalue()
    assert code == 1
    assert "Condizioni al contorno  2 errori" in text
    assert "Errore [bc.outside_active] (wells, fid 2): " in text
    assert "Errore [bc.screen_order] (wells, fid 3, screen_bottom): " in text
    assert "Esito: 2 errori, 1 avviso." in text
    assert err.getvalue().startswith(
        "Errore [check.failed]: Il controllo ha trovato 2 errori bloccanti."
    )
    assert text.index("Errore [bc.outside_active]") < text.index("Avviso [geometry.thin_unit]")


def test_check_json(model_site: Project) -> None:
    add_well(model_site, X0 + 100.0, Y0 + 100.0)
    stdout = io.BytesIO()
    code = cli.main(["--json", "check", str(model_site.root)], stdout=stdout)
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert code == 1
    assert [e["event"] for e in events] == [
        "command_started",
        "error",
        "warning",
        "result",
        "command_failed",
    ]
    assert events[1]["problem"]["ref"]["layer"] == "wells"
    data = events[3]["data"]
    assert (data["errors"], data["warnings"]) == (1, 1)
    assert [s["status"] for s in data["stages"]] == ["ok", "ok", "ok", "ok", "errors", "ok"]
    assert data["stages"][4]["label"] == {
        "it": "Condizioni al contorno",
        "en": "Boundary conditions",
    }
    assert events[4]["error"]["code"] == "check.failed"
