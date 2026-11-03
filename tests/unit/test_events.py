"""Event protocol, version 1."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from phrear.errors import ObjectRef, UnitError
from phrear.events import (
    SCHEMA_VERSION,
    CommandStarted,
    ErrorEvent,
    FlowReduced,
    JsonLinesSink,
    MemorySink,
    Problem,
    Progress,
    TimestepCompleted,
    dump_event,
    event_json_schema,
    parse_event,
)


def test_dump_uses_schema_alias_and_utc_time() -> None:
    data = json.loads(dump_event(CommandStarted(command="build")))
    assert data["schema"] == SCHEMA_VERSION
    assert data["event"] == "command_started"
    assert data["time"].endswith("Z")


def test_roundtrip_through_json_line() -> None:
    event = TimestepCompleted(
        run_id="r1",
        period=2,
        step=5,
        time_d=12.5,
        iterations=7,
        max_head_change_m=1e-4,
        budget_error_pct=0.01,
    )
    parsed = parse_event(dump_event(event))
    assert isinstance(parsed, TimestepCompleted)
    assert parsed == event


def test_parse_dispatches_on_event_field() -> None:
    line = json.dumps(
        {
            "schema": "1",
            "event": "progress",
            "time": "2026-11-03T12:00:00Z",
            "stage": "grid",
            "fraction": 0.5,
        }
    )
    assert isinstance(parse_event(line), Progress)


def test_unknown_schema_version_is_rejected() -> None:
    line = json.dumps(
        {"schema": "2", "event": "progress", "time": "2026-11-03T12:00:00Z", "stage": "x"}
    )
    with pytest.raises(ValidationError):
        parse_event(line)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Progress.model_validate({"stage": "x", "unexpected": 1})


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Progress(stage="x", time=datetime(2026, 11, 3, 12, 0))


def test_problem_from_error_carries_both_languages_and_ref() -> None:
    error = UnitError(
        "unit.unknown", unit="pippo/s", ref=ObjectRef(kind="field", layer="wells", fid=1)
    )
    problem = Problem.from_error(error)
    assert problem.code == "unit.unknown"
    assert "pippo/s" in problem.message.it and "pippo/s" in problem.message.en
    assert problem.hint.it and problem.hint.en
    assert problem.ref is not None and problem.ref.layer == "wells"


def test_json_lines_sink_writes_utf8_one_line_per_event() -> None:
    stream = io.BytesIO()
    sink = JsonLinesSink(stream)
    problem = Problem.from_code("unit.unknown", {"unit": "m³/anno?"})
    sink.emit(ErrorEvent(problem=problem))
    sink.emit(CommandStarted(command="check", time=datetime(2026, 11, 3, tzinfo=UTC)))
    raw = stream.getvalue()
    lines = raw.split(b"\n")
    assert lines[-1] == b"" and len(lines) == 3
    first = json.loads(lines[0].decode("utf-8"))
    assert "m³/anno?" in first["problem"]["message"]["it"]
    assert "«" in first["problem"]["message"]["it"]


def test_memory_sink_keeps_order() -> None:
    sink = MemorySink()
    sink.emit(CommandStarted(command="a"))
    sink.emit(CommandStarted(command="b"))
    assert [e.command for e in sink.events if isinstance(e, CommandStarted)] == ["a", "b"]


def test_flow_reduced_requires_well_reference() -> None:
    event = FlowReduced(
        run_id="r1",
        period=1,
        step=1,
        well=ObjectRef(kind="feature", layer="wells", fid=4),
        design_rate_m3d=-864.0,
        actual_rate_m3d=-600.0,
    )
    assert parse_event(dump_event(event)) == event


def test_json_schema_lists_every_event_type() -> None:
    text = json.dumps(event_json_schema())
    for name in (
        "command_started",
        "command_completed",
        "command_failed",
        "progress",
        "warning",
        "error",
        "run_started",
        "period_started",
        "timestep_completed",
        "snapshot_written",
        "flow_reduced",
        "run_completed",
        "run_failed",
    ):
        assert f'"{name}"' in text, name
