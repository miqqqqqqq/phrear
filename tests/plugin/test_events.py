"""Reading the events of the core and the outcome of a command."""

from __future__ import annotations

import json

from phrear_qgis.client.events import EventStream, Outcome, collect


def _line(event: dict[str, object]) -> bytes:
    return (json.dumps({"schema": "1", "time": "2026-11-04T08:00:00Z", **event}) + "\n").encode()


def test_lines_split_across_chunks_and_crlf() -> None:
    stream = EventStream()
    data = _line({"event": "command_started", "command": "env"}).replace(b"\n", b"\r\n")
    data += _line({"event": "result", "command": "env", "data": {"phrear": "0.1"}})
    first = stream.feed(data[:17])
    rest = stream.feed(data[17:])
    assert first == [] and [e["event"] for e in rest] == ["command_started", "result"]


def test_text_lines_are_kept_and_the_last_line_needs_no_newline() -> None:
    stream = EventStream()
    events = stream.feed(b"Pixi task (default): phrear\n[1, 2]\n")
    events += stream.feed(_line({"event": "command_completed", "command": "env"}).rstrip())
    assert events == []
    assert [e["event"] for e in stream.finish()] == ["command_completed"]
    assert stream.text == ["Pixi task (default): phrear", "[1, 2]"]


def test_unknown_schema_is_flagged() -> None:
    stream = EventStream()
    stream.feed(b'{"schema": "2", "event": "result"}\n')
    outcome = collect("env", [], 0, stream)
    assert outcome.wrong_schema == ("2",) and not outcome.ok


def test_outcome_of_a_failed_check() -> None:
    problem = {"code": "check.failed", "message": {"it": "Il controllo …", "en": "The check …"},
               "hint": {"it": "Correggi …", "en": "Fix …"}}  # fmt: skip
    events = [
        {"event": "warning", "problem": {"code": "geometry.thin_unit"}},
        {"event": "error", "problem": {"code": "bc.outside_active"}},
        {"event": "result", "data": {"errors": 1}},
        {"event": "command_failed", "error": problem},
    ]
    outcome = collect("check", events, 1, EventStream(), "  traceback text \n")
    assert not outcome.ok
    assert [p["code"] for p in outcome.warnings] == ["geometry.thin_unit"]
    assert [p["code"] for p in outcome.errors] == ["bc.outside_active"]
    assert outcome.result == {"errors": 1}
    assert outcome.failure_text("it") == "Il controllo …\nCorreggi …"
    assert outcome.failure_text("de") == "The check …\nFix …"
    assert outcome.output == "traceback text"


def test_cancelled_and_not_started() -> None:
    assert not Outcome("run", None, cancelled=True).ok
    assert not Outcome("run", None, start_error="not found").ok
    assert Outcome("env", 0).ok
