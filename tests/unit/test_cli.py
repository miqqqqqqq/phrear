"""Command line interface entry point."""

from __future__ import annotations

import argparse
import io
import json

import pytest

from phrear import __version__, cli
from phrear.commands import Context
from phrear.errors import UnitError
from phrear.events import MemorySink


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"phrear {__version__}"


def test_no_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == cli.EXIT_OK
    assert "usage: phrear" in capsys.readouterr().out


def test_usage_error_in_text_mode_goes_to_stderr() -> None:
    stderr = io.StringIO()
    code = cli.main(["--unknown-option"], stderr=stderr, stdout=io.BytesIO())
    assert code == cli.EXIT_USAGE
    assert "Errore [cli.usage]" in stderr.getvalue()


def test_usage_error_in_text_mode_english() -> None:
    stderr = io.StringIO()
    cli.main(["--lang", "en", "--unknown-option"], stderr=stderr, stdout=io.BytesIO())
    assert "Error [cli.usage]: Invalid command." in stderr.getvalue()


def test_usage_error_in_json_mode_is_an_event() -> None:
    stdout = io.BytesIO()
    code = cli.main(["--json", "--unknown-option"], stdout=stdout, stderr=io.StringIO())
    assert code == cli.EXIT_USAGE
    (line,) = stdout.getvalue().splitlines()
    data = json.loads(line)
    assert data["event"] == "error"
    assert data["problem"]["code"] == "cli.usage"


def _register(monkeypatch: pytest.MonkeyPatch, handler: cli.Handler) -> None:
    spec = cli.CommandSpec("probe", "test command", lambda parser: None, handler)
    monkeypatch.setattr(cli, "COMMANDS", [spec])


def test_command_events_wrap_a_successful_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(args: argparse.Namespace, ctx: Context) -> int:
        return cli.EXIT_OK

    _register(monkeypatch, handler)
    stdout = io.BytesIO()
    assert cli.main(["--json", "probe"], stdout=stdout) == cli.EXIT_OK
    events = [json.loads(line)["event"] for line in stdout.getvalue().splitlines()]
    assert events == ["command_started", "command_completed"]


def test_input_error_becomes_command_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(args: argparse.Namespace, ctx: Context) -> int:
        raise UnitError("unit.unknown", unit="xyz")

    _register(monkeypatch, handler)
    stdout = io.BytesIO()
    assert cli.main(["--json", "probe"], stdout=stdout) == cli.EXIT_INPUT_ERROR
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [e["event"] for e in events] == ["command_started", "command_failed"]
    assert events[-1]["error"]["code"] == "unit.unknown"


def test_unexpected_exception_is_internal_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(args: argparse.Namespace, ctx: Context) -> int:
        raise RuntimeError("boom")

    _register(monkeypatch, handler)
    stderr = io.StringIO()
    assert cli.main(["probe"], stderr=stderr, stdout=io.BytesIO()) == cli.EXIT_INTERNAL
    assert "internal.unexpected" in stderr.getvalue()


def test_run_command_without_sink_returns_handler_code() -> None:
    def handler(args: argparse.Namespace, ctx: Context) -> int:
        return 7

    text_ctx = Context(sink=None, lang="it", out=io.StringIO())
    assert cli.run_command("x", handler, argparse.Namespace(), text_ctx) == 7
    sink = MemorySink()
    json_ctx = Context(sink=sink, lang="it", out=io.StringIO())
    assert cli.run_command("x", handler, argparse.Namespace(), json_ctx) == 7
    assert len(sink.events) == 2
