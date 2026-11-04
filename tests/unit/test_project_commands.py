"""CLI commands new, info, schema, migrate."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from phrear import cli
from phrear.project.schema import SCHEMA_VERSION


def _json_events(argv: list[str]) -> tuple[int, list[dict[str, Any]]]:
    stdout = io.BytesIO()
    code = cli.main(["--json", *argv], stdout=stdout, stderr=io.StringIO())
    return code, [json.loads(line) for line in stdout.getvalue().splitlines()]


def _text(argv: list[str], lang: str = "it") -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["--lang", lang, *argv], text_stdout=out, stderr=err, stdout=io.BytesIO())
    return code, out.getvalue(), err.getvalue()


def test_new_then_info_in_json_mode(tmp_path: Path) -> None:
    root = tmp_path / "sito"
    code, events = _json_events(["new", str(root), "--start", "2020-01-01", "--end", "2021-01-01"])
    assert code == cli.EXIT_OK
    assert [e["event"] for e in events] == ["command_started", "result", "command_completed"]
    assert events[1]["data"]["name"] == "sito"

    code, events = _json_events(["info", str(root)])
    assert code == cli.EXIT_OK
    data = events[1]["data"]
    assert data["crs"]["epsg"] == 7791
    assert data["tables"]["domain"] == 0
    assert len(data["content_hash"]) == 64


def test_info_text_in_both_languages(tmp_path: Path) -> None:
    root = tmp_path / "sito"
    assert _text(["new", str(root), "--start", "2020-01-01", "--end", "2021-06-30"])[0] == 0
    code, out, _ = _text(["info", str(root)], "it")
    assert code == 0 and "Sistema di riferimento: EPSG:7791" in out
    code, out, _ = _text(["info", str(root)], "en")
    assert code == 0 and "Coordinate reference system: EPSG:7791" in out


def test_info_on_missing_project_is_an_input_error(tmp_path: Path) -> None:
    code, events = _json_events(["info", str(tmp_path)])
    assert code == cli.EXIT_INPUT_ERROR
    assert events[-1]["event"] == "command_failed"
    assert events[-1]["error"]["code"] == "project.not_found"


def test_bad_date_is_a_usage_error(tmp_path: Path) -> None:
    code, _, err = _text(
        ["new", str(tmp_path / "x"), "--start", "01/01/2020", "--end", "2021-01-01"]
    )
    assert code == cli.EXIT_USAGE
    assert "cli.usage" in err


def test_schema_document_includes_tables_and_events(tmp_path: Path) -> None:
    code, out, _ = _text(["schema"])
    assert code == 0
    document = json.loads(out)
    assert {t["name"] for t in document["project"]["tables"]} >= {"wells", "domain"}
    assert document["events"]["schema_version"] == "1"
    target = tmp_path / "schema.json"
    code, out, _ = _text(["schema", "--output", str(target)])
    assert code == 0 and json.loads(target.read_text(encoding="utf-8")) == document


def test_migrate_current_project(tmp_path: Path) -> None:
    root = tmp_path / "sito"
    _text(["new", str(root), "--start", "2020-01-01", "--end", "2021-01-01"])
    code, out, _ = _text(["migrate", str(root)])
    assert code == 0 and f"già allo schema {SCHEMA_VERSION}" in out
